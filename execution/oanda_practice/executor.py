"""Submit one authorised practice order, or refuse; resolve, never resubmit.

THE ORDER OF OPERATIONS IS THE SAFETY ARGUMENT

  1. kill switch           -> refuse (nothing read, nothing sent)
  2. authorization         -> account, validity window, not already used
  3. halts / open intents  -> refuse until reconcile or the operator clears them
  4. broker reads          -> account, quote, open trades; a failed read refuses
  5. risk                  -> every check, every code reported
  6. build the request     -> deterministic client id; mandatory stop; FOK; bound
  7. dry run stops here    -> returns the request; writes nothing
  8. reserve (journal)     -> SUBMITTING committed to disk BEFORE sending
  9. kill switch again     -> ABORTED_BEFORE_SEND (provably unsent)
 10. send                  -> FILLED / CANCELLED / REJECTED on the broker's own
                              evidence; anything else is UNCERTAIN

An UNCERTAIN or SUBMITTING intent is never retried. reconcile() asks the broker
what happened (order by client id, plus transactions since the id recorded in
step 4) and moves it only on proof. Until then, step 3 blocks every new order.
"""
import json
import os

from . import authorization as authz
from . import config as cfg
from . import journal as jn
from . import risk
from . import timeutil
from .adapter import BrokerAdapter, FILLED, UNCERTAIN
from .errors import AuthorizationRefused, BrokerReadFailed, NotSent, OrderRefused, PracticeExecutionError
from .kill import KillSwitch

REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
#: The executor's state may never live where research or simulated-paper evidence lives.
_FORBIDDEN_STATE_ROOTS = (os.path.join(REPO_ROOT, "docs"), os.path.join(REPO_ROOT, "evidence"))
ORDER_TAG = "MOGO_BROKER_PRACTICE"


def check_state_dir(state_dir):
    real = os.path.realpath(state_dir)
    for root in _FORBIDDEN_STATE_ROOTS:
        if real == root or real.startswith(root + os.sep):
            raise PracticeExecutionError("practice state may not live under %s" % os.path.relpath(root, REPO_ROOT))
    if not os.path.isdir(real):
        raise PracticeExecutionError("state directory does not exist")
    return real


def build_order_body(auth, bound):
    return {"order": {
        "type": "MARKET",
        "instrument": auth.instrument,
        "units": str(auth.signed_units),
        "timeInForce": "FOK",
        "positionFill": "OPEN_ONLY",
        "priceBound": str(bound),
        "stopLossOnFill": {"price": str(auth.stop_loss_price), "timeInForce": "GTC"},
        "clientExtensions": {"id": auth.client_order_id, "tag": ORDER_TAG,
                             "comment": auth.authorization_id},
        "tradeClientExtensions": {"id": auth.client_order_id, "tag": ORDER_TAG},
    }}


def _require_stop(body):
    stop = body["order"].get("stopLossOnFill") or {}
    if not stop.get("price"):
        raise OrderRefused(["STOP_LOSS_MISSING"])


class Executor(object):
    def __init__(self, config, adapter, state_dir, clock=timeutil.utc_now):
        if not isinstance(config, cfg.PracticeConfig):
            raise PracticeExecutionError("executor requires a PracticeConfig")
        if not isinstance(adapter, BrokerAdapter):
            raise PracticeExecutionError("executor requires a BrokerAdapter")
        self.config = config
        self.adapter = adapter
        self.state_dir = check_state_dir(state_dir)
        self.kill = KillSwitch(self.state_dir)
        self.journal = jn.Journal(os.path.join(self.state_dir, "journal.sqlite3"), clock=clock)
        self._clock = clock

    def close(self):
        self.journal.close()

    def _refuse(self, auth_id, codes):
        self.journal.record_refusal(auth_id, codes)
        raise OrderRefused(codes)

    def submit(self, auth, dry_run=False):
        auth_id = getattr(auth, "authorization_id", None)
        if self.kill.engaged():
            self._refuse(auth_id, ["KILL_SWITCH_ENGAGED"])
        now = self._clock()
        try:
            authz.check_current(auth, self.config, now)
        except AuthorizationRefused as exc:
            self._refuse(auth_id, ["AUTHORIZATION_REFUSED:" + str(exc)])
        gate = []
        if self.journal.authorization_used(auth_id):
            gate.append("AUTHORIZATION_ALREADY_USED")
        if self.journal.active_halts():
            gate.append("HALT_ACTIVE")
        if self.journal.intents(jn.UNRESOLVED_STATES):
            gate.append("UNRESOLVED_INTENT_RECONCILE_FIRST")
        if gate:
            self._refuse(auth_id, gate)

        try:
            account = self.adapter.account_summary()
            quote = self.adapter.quote(auth.instrument)
            broker_trades = self.adapter.open_trades()
        except BrokerReadFailed:
            self._refuse(auth_id, ["BROKER_READ_FAILED"])
        if account.account_id not in (None, self.config.account_id):
            self._refuse(auth_id, ["BROKER_RETURNED_ANOTHER_ACCOUNT"])

        codes = risk.assess(auth, quote, account, broker_trades, self.journal.has_open_exposure(), now)
        if codes:
            self._refuse(auth_id, codes)
        bound = risk.price_bound(auth, quote)
        body = build_order_body(auth, bound)
        _require_stop(body)
        request_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

        if dry_run:
            return {"dryRun": True, "clientOrderId": auth.client_order_id, "request": body,
                    "worstCaseLoss": str(risk.worst_case_loss(auth, quote)),
                    "lastTransactionIdBefore": account.last_transaction_id, "journalWrites": 0}

        try:
            self.journal.reserve(auth, auth.signed_units, bound, account.last_transaction_id,
                                 request_bytes, [account.raw, quote.raw])
        except jn.JournalRefused as exc:
            self._refuse(auth_id, exc.codes)

        if self.kill.engaged():
            self.journal.transition(auth.intent_id, jn.ABORTED_BEFORE_SEND, reason="KILL_SWITCH_ENGAGED_BEFORE_SEND")
            raise OrderRefused(["KILL_SWITCH_ENGAGED_BEFORE_SEND"])
        try:
            outcome = self.adapter.submit_market_order(body, auth.client_order_id, auth.units)
        except NotSent as exc:
            self.journal.transition(auth.intent_id, jn.ABORTED_BEFORE_SEND, reason="NOT_SENT:" + str(exc))
            raise OrderRefused(["NOT_SENT"])
        return self._apply(auth.intent_id, outcome)

    def _apply(self, intent_id, outcome):
        fields = {}
        if outcome.kind in (FILLED, UNCERTAIN):
            fields = {"broker_trade_id": outcome.trade_id, "fill_price": outcome.fill_price,
                      "fill_units": outcome.fill_units}
        if outcome.order_id is not None:
            fields["broker_order_id"] = outcome.order_id
        to_state = {"ABSENT": jn.NOT_SUBMITTED}.get(outcome.kind, outcome.kind)
        return self.journal.transition(intent_id, to_state, reason=outcome.reason, raw=outcome.raw, **fields)

    def reconcile(self):
        """Resolve every unresolved intent on broker evidence; halt on unknown MOGO trades."""
        report = {"resolved": [], "unresolved": [], "halted": []}
        for row in self.journal.intents(jn.UNRESOLVED_STATES):
            units = abs(row["signed_units"])
            try:
                outcome = self.adapter.resolve_client_order(row["client_order_id"],
                                                            row["last_transaction_id_before"], units)
            except BrokerReadFailed as exc:
                report["unresolved"].append({"intentId": row["intent_id"], "reason": str(exc)})
                continue
            new = self._apply(row["intent_id"], outcome)
            (report["unresolved"] if new["state"] == jn.UNCERTAIN else report["resolved"]).append(
                {"intentId": row["intent_id"], "state": new["state"], "reason": new["reason"]})
        try:
            trades = self.adapter.open_trades()
        except BrokerReadFailed as exc:
            report["unresolved"].append({"intentId": None, "reason": "open trades: %s" % exc})
            return report
        known = {r["broker_trade_id"] for r in self.journal.intents([jn.FILLED]) if r["broker_trade_id"]}
        for trade in trades:
            tag_id = ((trade or {}).get("clientExtensions") or {}).get("id") or ""
            if tag_id.startswith("MOGO-") and trade.get("id") not in known:
                reason = "UNKNOWN_MOGO_BROKER_TRADE %s" % trade.get("id")
                self.journal.halt(reason)
                report["halted"].append(reason)
        return report

    def status(self):
        return {"mode": cfg.MODE, "host": cfg.PRACTICE_HOST, "killSwitch": self.kill.engaged(),
                "activeHalts": self.journal.active_halts(),
                "intents": [{k: r[k] for k in ("intent_id", "state", "reason", "instrument", "signed_units")}
                            for r in self.journal.intents()]}
