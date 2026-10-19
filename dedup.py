"""Core engine: classify -> validate against existing data -> append only unique."""
import hashlib
import json
import sqlite3
from difflib import SequenceMatcher

from database import get_conn
from validator import normalise_email, normalise_name, normalise_phone, validate

UNIQUE = "UNIQUE_VERIFIED"
REDUNDANT = "REDUNDANT"
FALSE_POSITIVE = "FALSE_POSITIVE"

FUZZY_NAME = 0.92    # name similarity needed for a near-duplicate
FUZZY_LOCAL = 0.85   # email local-part similarity needed for a near-duplicate


def fingerprint(name_n: str, email_n: str, phone_n: str) -> str:
    return hashlib.sha256(f"{name_n}|{email_n}|{phone_n}".encode()).hexdigest()


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_duplicate(conn, name_n, email_n, phone_n):
    """Check new data against existing data. Returns (row, reason) or (None, None)."""
    row = conn.execute("SELECT * FROM records WHERE email_norm=?", (email_n,)).fetchone()
    if row:
        return row, "same email already exists"
    if phone_n:
        row = conn.execute("SELECT * FROM records WHERE phone_norm=?", (phone_n,)).fetchone()
        if row:
            return row, "same phone number already exists"
    # near-duplicate: very similar name AND very similar email username
    local = email_n.split("@")[0]
    for r in conn.execute("SELECT * FROM records"):
        if (_ratio(name_n, r["name_norm"]) >= FUZZY_NAME
                and _ratio(local, r["email_norm"].split("@")[0]) >= FUZZY_LOCAL):
            return r, "near-duplicate (very similar name and email)"
    return None, None


def _log_rejection(conn, record, classification, reason, matched_id=None):
    conn.execute(
        "INSERT INTO rejected_log(payload, classification, reason, matched_id) VALUES (?,?,?,?)",
        (json.dumps(record, ensure_ascii=False), classification, reason, matched_id))


def process_record(record: dict, db_path: str = None) -> dict:
    """Classify one record and append it ONLY if it is unique and verified."""
    conn = get_conn(db_path)
    try:
        ok, why = validate(record)
        if not ok:
            _log_rejection(conn, record, FALSE_POSITIVE, why)
            return {"classification": FALSE_POSITIVE, "inserted": False, "reason": why}

        name_n = normalise_name(record["name"])
        email_n = normalise_email(record["email"])
        phone_n = normalise_phone(record.get("phone", ""))

        conn.execute("BEGIN IMMEDIATE")          # lock so check+insert is atomic
        dup, why = find_duplicate(conn, name_n, email_n, phone_n)
        if dup:
            _log_rejection(conn, record, REDUNDANT, why, dup["id"])
            conn.execute("COMMIT")
            return {"classification": REDUNDANT, "inserted": False,
                    "reason": why, "matched_id": dup["id"]}
        try:
            cur = conn.execute(
                """INSERT INTO records(name,email,phone,name_norm,email_norm,phone_norm,fingerprint)
                   VALUES (?,?,?,?,?,?,?)""",
                (record["name"].strip(), record["email"].strip(), (record.get("phone") or "").strip(),
                 name_n, email_n, phone_n or None, fingerprint(name_n, email_n, phone_n)))
            conn.execute("COMMIT")
            return {"classification": UNIQUE, "inserted": True,
                    "reason": "verified and unique - added", "id": cur.lastrowid}
        except sqlite3.IntegrityError as e:       # DB-level safety net
            conn.execute("ROLLBACK")
            return {"classification": REDUNDANT, "inserted": False,
                    "reason": f"blocked by database constraint ({e})"}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def process_batch(records, db_path: str = None) -> dict:
    results = [process_record(r, db_path) for r in records]
    summary = {UNIQUE: 0, REDUNDANT: 0, FALSE_POSITIVE: 0}
    for r in results:
        summary[r["classification"]] += 1
    return {"summary": summary, "results": results}


def cleanup_existing(db_path: str = None) -> int:
    """Remove redundancy already present in the table (keeps the oldest row)."""
    conn = get_conn(db_path)
    removed = 0
    try:
        rows = conn.execute("SELECT * FROM records ORDER BY id").fetchall()
        kept = []
        for r in rows:
            dup = next((k for k in kept
                        if k["email_norm"] == r["email_norm"]
                        or (r["phone_norm"] and k["phone_norm"] == r["phone_norm"])
                        or (_ratio(r["name_norm"], k["name_norm"]) >= FUZZY_NAME and
                            _ratio(r["email_norm"].split("@")[0], k["email_norm"].split("@")[0]) >= FUZZY_LOCAL)),
                       None)
            if dup:
                conn.execute("DELETE FROM records WHERE id=?", (r["id"],))
                removed += 1
            else:
                kept.append(r)
        return removed
    finally:
        conn.close()
