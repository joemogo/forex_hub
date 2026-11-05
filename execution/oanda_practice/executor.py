"""Submit one authorised practice order, or refuse; resolve, never resubmit.

THE ORDER OF OPERATIONS IS THE SAFETY ARGUMENT

  1. kill switch           -> refuse (nothing read, nothing sent)
  2. authorization         -> account, validity window, not already used
  3. halts / open intents  -> refuse until reconcile or the operator clears them
  4. broker reads          -> account, quote, open trades, instrument constraints;
                              a failed read refuses
  5. risk                  -> every check, every code reported (M4 adds pending orders
                              and the broker's size, precision and stop-distance limits)
  6. build the request     -> deterministic client id; mandatory stop; FOK; bound
  7. dry run stops here    -> returns the request; writes nothing
  8. reserve (journal)     -> SUBMITTING committed to disk BEFORE sending
  9. kill switch again     -> ABORTED_BEFORE_SEND (provably unsent)
 10. send                  -> FILLED / CANCELLED / REJECTED on the broker's own
                              evidence; anything else is UNCERTAIN

An UNCERTAIN or SUBMITTING intent is never retried. reconcile() asks the broker
what happened (order by client id, plus transactions since the id recorded in
step 4) and moves it only on proof. Until then, step 3 blocks every new order.

THE POSITION (M2). A FILLED entry opens a position. reconcile() verifies its
protection at the broker: the trade carries a PENDING stop-loss order at
exactly the authorised price, and the transaction stream holds the
STOP_LOSS_ORDER that created it. Only then is the position PROTECTED. A missing
or different stop is a halt. close_position() is write-ahead, like the entry:
CLOSING is committed before the request, and an unknown outcome is
CLOSE_UNCERTAIN, never retried. M4: a close needs its own operator
authorization naming this exact trade (client order id AND broker trade id),
consumed in the same journal transaction that records CLOSING. Once the broker shows the trade CLOSED,
accounting.reconcile_trade() must agree on every figure before the position
becomes RECONCILED and the exposure is released. A closed trade whose
accounting disagrees halts and keeps blocking. Exit price and P&L come only
from broker fills (see accounting.py).
"""
from decimal import Decimal
import json
import os

from . import accounting
from . import authorization as authz
from . import config as cfg
from . import journal as jn
from . import risk
from . import timeutil
from .adapter import BrokerAdapter, CANCELLED, FILLED, REJECTED, UNCERTAIN, closing_entry, classify_close_fill
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
            spec = self.adapter.instrument_spec(auth.instrument)
        except BrokerReadFailed:
            self._refuse(auth_id, ["BROKER_READ_FAILED"])
        if account.account_id not in (None, self.config.account_id):
            self._refuse(auth_id, ["BROKER_RETURNED_ANOTHER_ACCOUNT"])

        codes = risk.assess(auth, quote, account, broker_trades, self.journal.has_open_exposure(), now)
        codes += risk.assess_constraints(auth, quote, account, spec)
        if codes:
            self._refuse(auth_id, codes)
        bound = risk.price_bound(auth, quote)
        body = build_order_body(auth, bound)
        _require_stop(body)
        request_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

        if dry_run:
            return {"dryRun": True, "clientOrderId": auth.client_order_id, "request": body,
                    "worstCaseLoss": str(risk.worst_case_loss(auth, quote)),
                    "quote": {"bid": str(quote.bid), "ask": str(quote.ask), "time": quote.time.isoformat(),
                              "tradeable": quote.tradeable},
                    "brokerConstraints": {"minimumTradeSize": str(spec.minimum_trade_size),
                                          "maximumOrderUnits": str(spec.maximum_order_units),
                                          "displayPrecision": spec.display_precision,
                                          "pipLocation": spec.pip_location},
                    "lastTransactionIdBefore": account.last_transaction_id, "journalWrites": 0}

        try:
            self.journal.reserve(auth, auth.signed_units, bound, account.last_transaction_id,
                                 request_bytes, [account.raw, quote.raw], balance_before=account.balance)
        except jn.JournalRefused as exc:
            self._refuse(auth_id, exc.codes)

        if self.kill.engaged():
            self.journal.transition(auth.intent_id, jn.ABORTED_BEFORE_SEND, reason="KILL_SWITCH_ENGAGED_BEFORE_SEND")
            raise OrderRefused(["KILL_SWITCH_ENGAGED_BEFORE_SEND"])
        try:
            outcome = self.adapter.submit_market_order(body, auth.client_order_id, auth.signed_units)
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
        row = self.journal.transition(intent_id, to_state, reason=outcome.reason, raw=outcome.raw, **fields)
        if to_state == FILLED:
            self.journal.open_position(intent_id, row["broker_trade_id"], row["instrument"],
                                       row["signed_units"], row["stop_loss_price"])
        return row

    def reconcile(self):
        """Resolve every unresolved intent on broker evidence; halt on unknown MOGO trades."""
        report = {"resolved": [], "unresolved": [], "halted": []}
        for row in self.journal.intents(jn.UNRESOLVED_STATES):
            units = row["signed_units"]
            try:
                outcome = self.adapter.resolve_client_order(row["client_order_id"],
                                                            row["last_transaction_id_before"], units)
            except BrokerReadFailed as exc:
                report["unresolved"].append({"intentId": row["intent_id"], "reason": str(exc)})
                continue
            new = self._apply(row["intent_id"], outcome)
            (report["unresolved"] if new["state"] == jn.UNCERTAIN else report["resolved"]).append(
                {"intentId": row["intent_id"], "state": new["state"], "reason": new["reason"]})
        for row in self.journal.intents([jn.FILLED]):
            if self.journal.position(row["intent_id"]) is None:          # e.g. an M1 journal
                self.journal.open_position(row["intent_id"], row["broker_trade_id"], row["instrument"],
                                           row["signed_units"], row["stop_loss_price"])
        for pos in self.journal.positions():
            if pos["state"] != jn.RECONCILED:
                self._reconcile_position(pos, report)
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

    # ---- M2: the position ---------------------------------------------------------------
    def _halt(self, report, reason):
        self.journal.halt_once(reason)
        report["halted"].append(reason)

    @staticmethod
    def _stop_is_in_place(pos, trade, txns):
        stop = trade.stop_order
        want = Decimal(pos["stop_loss_price"])
        if not stop or stop.get("state") != "PENDING" or stop.get("price") != want \
                or stop.get("tradeID") not in (None, pos["trade_id"]):
            return None
        created = [t for t in txns if t.get("type") == "STOP_LOSS_ORDER" and t.get("id") == stop.get("id")
                   and t.get("tradeID") == pos["trade_id"] and accounting._dec(t.get("price")) == want]
        return stop.get("id") if len(created) == 1 else None

    def _reconcile_position(self, pos, report):
        intent = self.journal.intent(pos["intent_id"])
        entry = {"intentId": pos["intent_id"], "tradeId": pos["trade_id"]}
        try:
            summary = self.adapter.account_summary()
            trade = self.adapter.trade(pos["trade_id"])
            window = self.adapter.transactions_since(intent["last_transaction_id_before"])
        except BrokerReadFailed as exc:
            report["unresolved"].append(dict(entry, reason=str(exc)))
            return
        rewritten = self.journal.ingest_transactions(window.transactions)
        if rewritten:
            return self._halt(report, "TRANSACTION_REWRITTEN %s" % ",".join(rewritten))
        if trade is None:
            return self._halt(report, "TRADE_MISSING_AT_BROKER %s" % pos["trade_id"])
        txns = window.transactions
        state = pos["state"]
        if trade.state == "OPEN":
            if state in (jn.CLOSING, jn.CLOSE_UNCERTAIN):
                if any(closing_entry(t, pos["trade_id"])[0] for t in txns if t.get("type") == "ORDER_FILL"):
                    return self._halt(report, "TRADE_OPEN_BUT_CLOSE_FILL_PRESENT %s" % pos["trade_id"])
                pos = self.journal.transition_position(pos["intent_id"], jn.OPEN_UNVERIFIED,
                                                       reason="CLOSE_NOT_EXECUTED")
                state = pos["state"]
            if trade.current_units != Decimal(pos["signed_units"]):
                return self._halt(report, "UNITS_CHANGED %s" % pos["trade_id"])
            stop_id = self._stop_is_in_place(pos, trade, txns)
            if stop_id is None:
                return self._halt(report, "UNPROTECTED_POSITION %s" % pos["trade_id"])
            if state == jn.OPEN_UNVERIFIED:
                self.journal.transition_position(pos["intent_id"], jn.PROTECTED, reason="STOP_VERIFIED",
                                                 raw=trade.raw, stop_order_id=stop_id)
            report["resolved"].append(dict(entry, state=jn.PROTECTED))
            return
        if trade.state != "CLOSED":
            report["unresolved"].append(dict(entry, reason="TRADE_STATE_%s" % trade.state))
            return
        closes = [t for t in txns if t.get("type") == "ORDER_FILL" and closing_entry(t, pos["trade_id"])[0]]
        if not closes:
            return self._halt(report, "MISSING_CLOSE_EVIDENCE %s" % pos["trade_id"])
        if len(closes) != 1:
            return self._halt(report, "MULTIPLE_CLOSE_FILLS %s" % pos["trade_id"])
        outcome = classify_close_fill(closes[0], pos["trade_id"], pos["signed_units"], None)
        if outcome.kind != "CLOSED":
            return self._halt(report, "CLOSE_EVIDENCE_INVALID %s %s" % (pos["trade_id"], outcome.reason))
        if state != jn.CLOSED:
            pos = self.journal.transition_position(
                pos["intent_id"], jn.CLOSED, reason="BROKER_CLOSE_FILL", raw=trade.raw,
                exit_price=outcome.fill_price, close_fill_id=closes[0].get("id"), close_reason=outcome.reason)
        before = intent.get("account_balance_before")
        result = accounting.reconcile_trade(pos["trade_id"], pos["signed_units"],
                                            Decimal(before) if before else None, txns, summary.balance,
                                            summary.last_transaction_id, window.last_id)
        if result.codes == ["SUMMARY_AND_WINDOW_AT_DIFFERENT_TRANSACTIONS"]:
            report["unresolved"].append(dict(entry, reason=result.codes[0]))   # a race: read again
            return
        if not result.ok:
            return self._halt(report, "ACCOUNTING_MISMATCH %s %s" % (pos["trade_id"], ",".join(result.codes)))
        f = result.figures
        self.journal.transition_position(
            pos["intent_id"], jn.RECONCILED, reason="FILLS_STREAM_AND_BALANCE_AGREE",
            entry_fill_id=f["entry_fill_id"], entry_price=f["entry_price"], realized_pl=f["realized_pl"],
            close_fill_id=f["close_fill_id"],
            financing=f["financing"], commission=f["commission"], fees=f["fees"], net_pl=f["net_pl"],
            balance_after=f["balance_after"])
        report["resolved"].append(dict(entry, state=jn.RECONCILED, netPl=str(f["net_pl"])))

    def close_position(self, intent_id, close_auth):
        """Close one open position, write-ahead, under its own close authorization.

        Allowed under the kill switch and under a halt: closing reduces risk, and an
        UNPROTECTED_POSITION halt is exactly when a close is needed.
        """
        pos = self.journal.position(intent_id)
        if pos is None or pos["state"] not in jn.POSITION_OPEN_STATES:
            raise OrderRefused(["POSITION_NOT_OPEN"])
        intent = self.journal.intent(intent_id)
        try:
            authz.check_close_current(close_auth, self.config, self._clock(), pos, intent["client_order_id"])
        except AuthorizationRefused as exc:
            raise OrderRefused(["CLOSE_AUTHORIZATION_REFUSED:" + str(exc)])
        if self.journal.close_authorization_used(close_auth.close_authorization_id):
            raise OrderRefused(["CLOSE_AUTHORIZATION_ALREADY_USED"])
        try:
            summary = self.adapter.account_summary()
        except BrokerReadFailed:
            raise OrderRefused(["BROKER_READ_FAILED"])
        prior = pos["state"]
        request = json.dumps({"units": "ALL"}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            self.journal.transition_position(intent_id, jn.CLOSING, reason="CLOSE_REQUESTED", raw=request,
                                             consume_close=close_auth,
                                             last_transaction_id_before_close=summary.last_transaction_id,
                                             close_request_sha256=self.journal.store_raw(request))
        except jn.JournalRefused as exc:
            raise OrderRefused(exc.codes)
        try:
            outcome = self.adapter.close_trade(pos["trade_id"], pos["signed_units"])
        except NotSent as exc:
            self.journal.transition_position(intent_id, prior, reason="CLOSE_NOT_SENT:" + str(exc))
            raise OrderRefused(["NOT_SENT"])
        if outcome.kind == "CLOSED":
            return self.journal.transition_position(
                intent_id, jn.CLOSED, reason="CLOSE_FILLED", raw=outcome.raw,
                exit_price=outcome.fill_price, close_reason=outcome.reason)
        if outcome.kind in (CANCELLED, REJECTED):
            return self.journal.transition_position(intent_id, prior, reason="CLOSE_REFUSED:%s" % outcome.reason,
                                                    raw=outcome.raw)
        return self.journal.transition_position(intent_id, jn.CLOSE_UNCERTAIN, reason=outcome.reason,
                                                raw=outcome.raw)

    def status(self):
        return {"mode": cfg.MODE, "host": cfg.PRACTICE_HOST, "killSwitch": self.kill.engaged(),
                "activeHalts": self.journal.active_halts(),
                "intents": [{k: r[k] for k in ("intent_id", "state", "reason", "instrument", "signed_units")}
                            for r in self.journal.intents()],
                "positions": [{k: r[k] for k in ("intent_id", "trade_id", "state", "reason", "exit_price",
                                                 "net_pl", "balance_after")}
                              for r in self.journal.positions()]}
