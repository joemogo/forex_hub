"""The write-ahead order journal (SQLite, synchronous=FULL).

An order is recorded as SUBMITTING, and that record is committed to disk,
BEFORE the request is handed to the transport. So a crash at any instant
leaves either no record (nothing was sent) or a SUBMITTING record that
reconcile must resolve before anything else can be submitted.

DUPLICATE PROTECTION IS STRUCTURAL. reserve() runs inside BEGIN IMMEDIATE (one
writer at a time, across processes) and refuses when the authorization has
been used, when any intent is still open or unresolved, or when a halt is
active. authorizationId and clientOrderId are UNIQUE columns, so even a code
path that skipped those checks could not insert a second order for one
authorization.

APPEND-ONLY. Triggers forbid UPDATE and DELETE on events, raw responses,
refusals and halts (a halt is cleared by inserting a clearance, not by
editing it), and DELETE on intents. The intent row's state changes only
through transition(), which writes the event in the same transaction and
validates the move against TRANSITIONS.
"""
import hashlib
import json
import os
import sqlite3

from . import timeutil

SUBMITTING, UNCERTAIN, FILLED = "SUBMITTING", "UNCERTAIN", "FILLED"
CANCELLED, REJECTED = "CANCELLED", "REJECTED"
ABORTED_BEFORE_SEND, NOT_SUBMITTED = "ABORTED_BEFORE_SEND", "NOT_SUBMITTED"

TRANSITIONS = {
    SUBMITTING: {FILLED, CANCELLED, REJECTED, UNCERTAIN, ABORTED_BEFORE_SEND, NOT_SUBMITTED},
    UNCERTAIN: {FILLED, CANCELLED, NOT_SUBMITTED, UNCERTAIN},
}
#: States that hold, or may hold, broker exposure. Any one of them blocks a new order.
OPEN_EXPOSURE_STATES = (SUBMITTING, UNCERTAIN, FILLED)
UNRESOLVED_STATES = (SUBMITTING, UNCERTAIN)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS intents (
  intent_id TEXT PRIMARY KEY,
  authorization_id TEXT NOT NULL UNIQUE,
  client_order_id TEXT NOT NULL UNIQUE,
  authorization_sha256 TEXT NOT NULL,
  instrument TEXT NOT NULL,
  signed_units INTEGER NOT NULL,
  stop_loss_price TEXT NOT NULL,
  price_bound TEXT NOT NULL,
  last_transaction_id_before TEXT NOT NULL,
  request_sha256 TEXT NOT NULL,
  state TEXT NOT NULL,
  reason TEXT,
  broker_order_id TEXT,
  broker_trade_id TEXT,
  fill_price TEXT,
  fill_units TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  intent_id TEXT NOT NULL,
  from_state TEXT,
  to_state TEXT NOT NULL,
  reason TEXT,
  raw_sha256 TEXT,
  at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS raw (sha256 TEXT PRIMARY KEY, bytes BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS refusals (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, authorization_id TEXT, codes TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS halts (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, halt_seq INTEGER,
  reason TEXT NOT NULL, by TEXT, at TEXT NOT NULL);
"""
_APPEND_ONLY = ("events", "raw", "refusals", "halts")


class JournalRefused(Exception):
    def __init__(self, codes):
        self.codes = list(codes)
        super().__init__("journal refused: " + ", ".join(self.codes))


class Journal(object):
    def __init__(self, path, clock=timeutil.utc_now):
        self.path = path
        self._clock = clock
        self._db = sqlite3.connect(path, isolation_level=None, timeout=30)
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(_SCHEMA)
        for table in _APPEND_ONLY:
            for verb in ("UPDATE", "DELETE"):
                self._db.execute(
                    "CREATE TRIGGER IF NOT EXISTS %s_no_%s BEFORE %s ON %s BEGIN "
                    "SELECT RAISE(ABORT, '%s is append-only'); END"
                    % (table, verb.lower(), verb, table, table))
        self._db.execute("CREATE TRIGGER IF NOT EXISTS intents_no_delete BEFORE DELETE ON intents "
                         "BEGIN SELECT RAISE(ABORT, 'intents are never deleted'); END")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def close(self):
        self._db.close()

    def _now(self):
        return self._clock().isoformat()

    # ---- reads -------------------------------------------------------------
    def intent(self, intent_id):
        cur = self._db.execute("SELECT * FROM intents WHERE intent_id=?", (intent_id,))
        row = cur.fetchone()
        return dict(zip([c[0] for c in cur.description], row)) if row else None

    def intents(self, states=None):
        sql, args = "SELECT * FROM intents", ()
        if states:
            sql += " WHERE state IN (%s)" % ",".join("?" * len(states))
            args = tuple(states)
        cur = self._db.execute(sql + " ORDER BY created_at", args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def events(self, intent_id=None):
        sql = "SELECT intent_id, from_state, to_state, reason, raw_sha256 FROM events"
        args = ()
        if intent_id:
            sql, args = sql + " WHERE intent_id=?", (intent_id,)
        return [dict(zip(("intent_id", "from_state", "to_state", "reason", "raw_sha256"), r))
                for r in self._db.execute(sql + " ORDER BY seq", args)]

    def authorization_used(self, authorization_id):
        return self._db.execute("SELECT 1 FROM intents WHERE authorization_id=?",
                                (authorization_id,)).fetchone() is not None

    def has_open_exposure(self):
        q = "SELECT 1 FROM intents WHERE state IN (%s)" % ",".join("?" * len(OPEN_EXPOSURE_STATES))
        return self._db.execute(q, OPEN_EXPOSURE_STATES).fetchone() is not None

    def active_halts(self):
        rows = self._db.execute("SELECT seq, kind, halt_seq, reason FROM halts ORDER BY seq").fetchall()
        cleared = {r[2] for r in rows if r[1] == "CLEAR"}
        return [{"seq": r[0], "reason": r[3]} for r in rows if r[1] == "HALT" and r[0] not in cleared]

    def refusals(self):
        return [{"authorization_id": r[0], "codes": json.loads(r[1])}
                for r in self._db.execute("SELECT authorization_id, codes FROM refusals ORDER BY seq")]

    # ---- writes ------------------------------------------------------------
    def store_raw(self, raw):
        if raw is None:
            return None
        digest = hashlib.sha256(raw).hexdigest()
        self._db.execute("INSERT OR IGNORE INTO raw (sha256, bytes) VALUES (?, ?)", (digest, raw))
        return digest

    def record_refusal(self, authorization_id, codes):
        self._db.execute("INSERT INTO refusals (authorization_id, codes, at) VALUES (?, ?, ?)",
                         (authorization_id, json.dumps(sorted(codes)), self._now()))

    def halt(self, reason):
        self._db.execute("INSERT INTO halts (kind, reason, at) VALUES ('HALT', ?, ?)", (reason, self._now()))

    def clear_halt(self, halt_seq, by, reason):
        if not by or not reason:
            raise ValueError("clearing a halt requires who and why")
        self._db.execute("INSERT INTO halts (kind, halt_seq, reason, by, at) VALUES ('CLEAR', ?, ?, ?, ?)",
                         (halt_seq, reason, by, self._now()))

    def reserve(self, auth, signed_units, price_bound, last_transaction_id, request_bytes, raw_reads):
        """Atomically re-check and record SUBMITTING. Returns the intent row."""
        now = self._now()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            codes = []
            if self.authorization_used(auth.authorization_id):
                codes.append("AUTHORIZATION_ALREADY_USED")
            if self.has_open_exposure():
                codes.append("JOURNAL_HAS_OPEN_OR_UNRESOLVED_INTENT")
            if self.active_halts():
                codes.append("HALT_ACTIVE")
            if codes:
                raise JournalRefused(codes)
            for raw in raw_reads:
                self.store_raw(raw)
            request_sha = self.store_raw(request_bytes)
            self._db.execute(
                "INSERT INTO intents (intent_id, authorization_id, client_order_id, authorization_sha256,"
                " instrument, signed_units, stop_loss_price, price_bound, last_transaction_id_before,"
                " request_sha256, state, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (auth.intent_id, auth.authorization_id, auth.client_order_id, auth.raw_sha256,
                 auth.instrument, signed_units, str(auth.stop_loss_price), str(price_bound),
                 last_transaction_id, request_sha, SUBMITTING, now, now))
            self._db.execute("INSERT INTO events (intent_id, from_state, to_state, reason, raw_sha256, at)"
                             " VALUES (?, NULL, ?, 'RESERVED', ?, ?)",
                             (auth.intent_id, SUBMITTING, request_sha, now))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        return self.intent(auth.intent_id)

    def transition(self, intent_id, to_state, reason=None, raw=None, **fields):
        allowed_fields = {"broker_order_id", "broker_trade_id", "fill_price", "fill_units"}
        if set(fields) - allowed_fields:
            raise ValueError("unknown intent fields %s" % sorted(set(fields) - allowed_fields))
        now = self._now()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            row = self.intent(intent_id)
            if row is None:
                raise ValueError("no such intent")
            if to_state not in TRANSITIONS.get(row["state"], ()):
                raise ValueError("illegal transition %s -> %s" % (row["state"], to_state))
            digest = self.store_raw(raw)
            sets = ["state=?", "reason=?", "updated_at=?"] + ["%s=?" % k for k in sorted(fields)]
            args = [to_state, reason, now] + [None if fields[k] is None else str(fields[k])
                                              for k in sorted(fields)]
            self._db.execute("UPDATE intents SET %s WHERE intent_id=?" % ", ".join(sets), args + [intent_id])
            self._db.execute("INSERT INTO events (intent_id, from_state, to_state, reason, raw_sha256, at)"
                             " VALUES (?, ?, ?, ?, ?, ?)",
                             (intent_id, row["state"], to_state, reason, digest, now))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        return self.intent(intent_id)
