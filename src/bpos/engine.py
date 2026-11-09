"""Owner-authorized bpOS overlay. Advisory only; NOT Bitcoin consensus."""
import json
import sqlite3
import threading

from .crypto import verify_event
from .model import is_hex64, validate_policy


class BPError(ValueError):
    pass


class Engine:
    def __init__(self, database=":memory:"):
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(database, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS policies (
                policy_id TEXT PRIMARY KEY, outpoint TEXT UNIQUE NOT NULL,
                body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, kind TEXT NOT NULL, content TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observations (
                policy_id TEXT NOT NULL, txid TEXT NOT NULL, seen_height INTEGER NOT NULL,
                PRIMARY KEY (policy_id, txid)
            );
            CREATE TABLE IF NOT EXISTS decisions (
                policy_id TEXT NOT NULL, txid TEXT NOT NULL, kind TEXT NOT NULL,
                event_id TEXT NOT NULL, PRIMARY KEY (policy_id,txid,kind)
            );
            CREATE TABLE IF NOT EXISTS internet_bindings (
                wallet_pubkey TEXT PRIMARY KEY, proof_id TEXT NOT NULL, binding TEXT NOT NULL,
                verified_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
            INSERT OR IGNORE INTO meta(key,value) VALUES ('height',0);
        """)

    def height(self):
        with self.lock:
            return self.conn.execute("SELECT value FROM meta WHERE key='height'").fetchone()[0]

    def set_height(self, height):
        if type(height) is not int or height < 0:
            raise BPError("Invalid block height")
        with self.lock:
            self.conn.execute("UPDATE meta SET value=? WHERE key='height'", (height,))

    def policies(self):
        with self.lock:
            return [{"policy_id": r["policy_id"], **json.loads(r["body"])}
                    for r in self.conn.execute("SELECT * FROM policies ORDER BY policy_id")]

    def get_policy(self, policy_id):
        with self.lock:
            row = self.conn.execute("SELECT body FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
            if row is None:
                raise BPError("Unknown policy")
            return json.loads(row["body"])

    def apply_event(self, event, *, now=None):
        try:
            event_id = verify_event(event, now=now)
        except (ValueError, KeyError, TypeError) as exc:
            raise BPError(str(exc)) from exc
        kind, body, signer = event["kind"], event["body"], event["signer"]
        with self.lock:
            if self.conn.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone():
                return {"event_id": event_id, "accepted": False, "duplicate": True}
            if kind == "enroll":
                try:
                    policy_id = validate_policy(body, signer)
                except ValueError as exc:
                    raise BPError(str(exc)) from exc
                existing = self.conn.execute("SELECT policy_id FROM policies WHERE outpoint=?", (body["outpoint"],)).fetchone()
                if existing and existing[0] != policy_id:
                    raise BPError("Conflicting local registration; no ownership/consensus arbitration exists")
            else:
                if set(body) != {"policy_id", "txid"} or not is_hex64(body["policy_id"]) or not is_hex64(body["txid"]):
                    raise BPError("Invalid authorization payload")
                policy_id = body["policy_id"]
                policy = self.get_policy(policy_id)
                if signer != policy["device_pubkey"]:
                    raise BPError("Signer is not the registered ipayntity device")
                seen = self.conn.execute(
                    "SELECT seen_height FROM observations WHERE policy_id=? AND txid=?",
                    (policy_id, body["txid"])).fetchone()
                if kind == "veto" and seen and self.height() >= seen[0] + policy["delay_blocks"]:
                    raise BPError("Local advisory veto window already elapsed")
                if kind == "veto" and policy["mode"] != "veto_window":
                    raise BPError("Veto not available in instant mode")
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                if kind == "enroll":
                    self.conn.execute("INSERT OR IGNORE INTO policies(policy_id,outpoint,body) VALUES (?,?,?)",
                                      (policy_id, body["outpoint"], json.dumps(body, sort_keys=True)))
                else:
                    # Both authorize and veto can be recorded; veto wins within the window.
                    self.conn.execute("INSERT OR IGNORE INTO decisions(policy_id,txid,kind,event_id) VALUES (?,?,?,?)",
                                      (policy_id, body["txid"], kind, event_id))
                self.conn.execute("INSERT INTO events(event_id,kind,content) VALUES (?,?,?)",
                                  (event_id, kind, json.dumps(event, sort_keys=True)))
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
            return {"event_id": event_id, "accepted": True, "duplicate": False, "policy_id": policy_id}

    def observe(self, policy_id, txid, seen_height=None):
        if not is_hex64(txid):
            raise BPError("Invalid Bitcoin transaction ID")
        with self.lock:
            self.get_policy(policy_id)
            height = self.height() if seen_height is None else seen_height
            if type(height) is not int or height < 0:
                raise BPError("Invalid observation height")
            self.conn.execute("INSERT OR IGNORE INTO observations(policy_id,txid,seen_height) VALUES (?,?,?)",
                              (policy_id, txid, height))
            return self.get_status(policy_id, txid)

    def get_status(self, policy_id, txid):
        with self.lock:
            policy = self.get_policy(policy_id)
            row = self.conn.execute("SELECT seen_height FROM observations WHERE policy_id=? AND txid=?",
                                    (policy_id, txid)).fetchone()
            if row is None:
                raise BPError("Transaction has not been observed")
            decisions = {r[0] for r in self.conn.execute(
                "SELECT kind FROM decisions WHERE policy_id=? AND txid=?", (policy_id, txid))}
            deadline = row["seen_height"] + policy["delay_blocks"]
            elapsed = self.height() >= deadline
            if policy["mode"] == "instant":
                state = "AUTHORIZED_OVERLAY" if "authorize" in decisions else "HARDWARE_PROOF_MISSING"
            elif "veto" in decisions:
                state = "OWNER_VETO"
            elif "authorize" in decisions:
                state = "AUTHORIZED_OVERLAY"
            elif elapsed:
                state = "WINDOW_ELAPSED"
            else:
                state = "VETO_WINDOW_OPEN"
            return {"policy_id": policy_id, "txid": txid, "mode": policy["mode"],
                    "state": state, "current_height": self.height(),
                    "seen_height": row["seen_height"], "deadline_height": deadline,
                    "owner_authorized": "authorize" in decisions,
                    "owner_veto_signed": "veto" in decisions,
                    "on_chain_enforced": False}

    def observations(self):
        with self.lock:
            return [self.get_status(r["policy_id"], r["txid"]) for r in self.conn.execute(
                "SELECT policy_id,txid FROM observations ORDER BY seen_height,policy_id,txid")]

    def register_internet_binding(self, binding, proof_id, verified_at):
        """Called only AFTER cryptographic and fresh network challenge verification."""
        wallet_pubkey = binding["body"]["wallet_pubkey"]
        with self.lock:
            existing = self.conn.execute(
                "SELECT proof_id FROM internet_bindings WHERE wallet_pubkey=?", (wallet_pubkey,)
            ).fetchone()
            if existing and existing["proof_id"] != proof_id:
                raise BPError("Conflicting local internet binding (no global arbitration)")
            self.conn.execute(
                "INSERT OR IGNORE INTO internet_bindings(wallet_pubkey,proof_id,binding,verified_at) VALUES (?,?,?,?)",
                (wallet_pubkey, proof_id, json.dumps(binding, sort_keys=True), verified_at)
            )
            return {"proof_id": proof_id, "wallet_pubkey": wallet_pubkey,
                    "already_known": existing is not None}

    def internet_bindings(self):
        with self.lock:
            return [{"proof_id": r["proof_id"], "verified_at": r["verified_at"],
                     "binding": json.loads(r["binding"])}
                    for r in self.conn.execute("SELECT * FROM internet_bindings ORDER BY wallet_pubkey")]

    def internet_binding(self, wallet_pubkey):
        with self.lock:
            row = self.conn.execute(
                "SELECT proof_id,binding,verified_at FROM internet_bindings WHERE wallet_pubkey=?",
                (wallet_pubkey,)
            ).fetchone()
            if not row:
                raise BPError("Unknown wallet public key")
            return {"proof_id": row["proof_id"], "binding": json.loads(row["binding"]),
                    "verified_at": row["verified_at"]}

    def close(self):
        self.conn.close()
