"""
Pramaan — Database layer.

Local SQLite database with eight tables:
  messages              — All processed messages with classification, extracted
                          transaction data, risk scores, and ledger status.
  contacts              — Counterparty directory with trust scores.
  community_scam_reports — Anonymized scam text patterns + embeddings.
  ledgers               — Monthly bookkeeping periods (e.g. '2026-07').
  settings              — Key-value config store (e.g. auto_upi_sync).
  inventory             — Stock / product catalog with quantities and cost prices.
  daily_snapshots       — End-of-day position locks (cash, inventory value, receivables).

Design: SQLite for zero-setup, zero-cost local persistence.
Schema is Postgres-compatible for future hosted deployment.
"""

import json
import sqlite3
import threading
import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "pramaan.db"
_lock = threading.Lock()

# Thread-local connections so SQLite doesn't get concurrent write conflicts
_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating it on first call."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # enables concurrent reads while writing
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
    return _local.conn


def init_db():
    """Create all tables if they don't already exist. Called once at API startup."""
    conn = get_conn()
    
    # Create auth tables (User and Shop) first, before other tables
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS shops (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        phone       TEXT,
        address     TEXT,
        created_at  TEXT NOT NULL,
        updated_at  TEXT
    );

    CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id         INTEGER NOT NULL UNIQUE,
        email           TEXT NOT NULL UNIQUE,
        password_hash   TEXT NOT NULL,
        full_name       TEXT,
        is_active       BOOLEAN DEFAULT 1,
        created_at      TEXT NOT NULL,
        updated_at      TEXT,
        FOREIGN KEY (shop_id) REFERENCES shops(id)
    );

    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_shop ON users(shop_id);
    """)
    
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS messages (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        channel             TEXT    NOT NULL DEFAULT 'web',
        sender_id           TEXT    NOT NULL DEFAULT 'web_user',
        sender_name         TEXT,
        raw_text            TEXT    NOT NULL,
        language            TEXT    DEFAULT 'english',
        received_at         TEXT    NOT NULL,

        -- Classification output
        classification      TEXT    NOT NULL DEFAULT 'unknown',
        classifier_stage    TEXT    NOT NULL DEFAULT 'fast_path',
        confidence          REAL,

        -- Extracted transaction fields (NULL when no transaction detected)
        amount              REAL,
        currency            TEXT    DEFAULT 'INR',
        counterparty_name   TEXT,
        counterparty_phone  TEXT,
        txn_date            TEXT,
        purpose             TEXT,
        payment_method      TEXT,
        upi_reference       TEXT,
        txn_direction       TEXT,

        -- Risk scoring
        risk_score          INTEGER,
        risk_signals        TEXT,    -- JSON array of strings
        explanation         TEXT,

        -- Ledger status: execution-free until user confirms
        ledger_status       TEXT    DEFAULT 'n/a',
        confirmed_at        TEXT,

        -- Monthly ledger association (e.g. '2026-07')
        ledger_month        TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_messages_received ON messages(received_at DESC);
    CREATE INDEX IF NOT EXISTS idx_messages_ledger   ON messages(ledger_status);
    CREATE INDEX IF NOT EXISTS idx_messages_month    ON messages(ledger_month);

    CREATE TABLE IF NOT EXISTS contacts (
        phone                   TEXT    PRIMARY KEY,
        display_name            TEXT,
        first_seen              TEXT    NOT NULL,
        txn_count               INTEGER DEFAULT 0,
        total_verified_inflow   REAL    DEFAULT 0.0,
        scam_reports_against    INTEGER DEFAULT 0,
        trust_score             REAL    DEFAULT 50.0
    );

    CREATE TABLE IF NOT EXISTS community_scam_reports (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        reported_text   TEXT    NOT NULL,
        embedding_json  TEXT,
        pattern_summary TEXT,
        report_count    INTEGER DEFAULT 1,
        created_at      TEXT    NOT NULL
    );

    -- Monthly ledger periods.
    -- status: 'active' | 'closed' | 'inherited'
    CREATE TABLE IF NOT EXISTS ledgers (
        month_key   TEXT    PRIMARY KEY,    -- e.g. '2026-07'
        label       TEXT,                   -- e.g. 'July 2026'
        status      TEXT    NOT NULL DEFAULT 'active',
        created_at  TEXT    NOT NULL
    );

    -- Key-value configuration store.
    CREATE TABLE IF NOT EXISTS settings (
        key     TEXT    PRIMARY KEY,
        value   TEXT    NOT NULL
    );

    -- Inventory / stock catalog.
    CREATE TABLE IF NOT EXISTS inventory (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name   TEXT    UNIQUE NOT NULL,
        quantity    REAL    DEFAULT 0,
        cost_price  REAL    DEFAULT 0,
        unit        TEXT    DEFAULT 'unit',
        created_at  TEXT    NOT NULL,
        updated_at  TEXT    NOT NULL
    );

    -- Daily closing snapshots.
    CREATE TABLE IF NOT EXISTS daily_snapshots (
        date                TEXT    PRIMARY KEY,
        cash_balance        REAL    DEFAULT 0,
        inventory_value     REAL    DEFAULT 0,
        khata_receivable    REAL    DEFAULT 0,
        note                TEXT,
        created_at          TEXT    NOT NULL
    );

    -- Seed default settings on first run (INSERT OR IGNORE keeps existing values).
    INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_upi_sync', 'false');
    """)

    # Safe migration: add category column to messages if it doesn't exist yet
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN category TEXT DEFAULT 'other'")
        conn.commit()
    except Exception:
        pass  # Column already exists — safe to ignore

    conn.commit()
    logger.info("Pramaan database ready at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Message operations
# ---------------------------------------------------------------------------

def insert_message(data: dict) -> int:
    """Insert one processed message. Returns the new row ID."""
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    # Auto-tag with the currently active ledger month if not supplied
    if not data.get("ledger_month"):
        data["ledger_month"] = get_active_ledger_month()
    with _lock:
        cur = conn.execute("""
            INSERT INTO messages (
                channel, sender_id, sender_name, raw_text, language, received_at,
                classification, classifier_stage, confidence,
                amount, currency, counterparty_name, counterparty_phone,
                txn_date, purpose, payment_method, upi_reference, txn_direction,
                risk_score, risk_signals, explanation, ledger_status, confirmed_at,
                ledger_month, category
            ) VALUES (
                :channel, :sender_id, :sender_name, :raw_text, :language, :received_at,
                :classification, :classifier_stage, :confidence,
                :amount, :currency, :counterparty_name, :counterparty_phone,
                :txn_date, :purpose, :payment_method, :upi_reference, :txn_direction,
                :risk_score, :risk_signals, :explanation, :ledger_status, :confirmed_at,
                :ledger_month, :category
            )
        """, {
            "channel":            data.get("channel", "web"),
            "sender_id":          data.get("sender_id", "web_user"),
            "sender_name":        data.get("sender_name"),
            "raw_text":           data.get("raw_text", ""),
            "language":           data.get("language", "english"),
            "received_at":        data.get("received_at", now),
            "classification":     data.get("classification", "unknown"),
            "classifier_stage":   data.get("classifier_stage", "fast_path"),
            "confidence":         data.get("confidence"),
            "amount":             data.get("amount"),
            "currency":           data.get("currency", "INR"),
            "counterparty_name":  data.get("counterparty_name"),
            "counterparty_phone": data.get("counterparty_phone"),
            "txn_date":           data.get("txn_date"),
            "purpose":            data.get("purpose"),
            "payment_method":     data.get("payment_method"),
            "upi_reference":      data.get("upi_reference"),
            "txn_direction":      data.get("txn_direction"),
            "risk_score":         data.get("risk_score"),
            "risk_signals":       json.dumps(data.get("risk_signals", [])),
            "explanation":        data.get("explanation"),
            "ledger_status":      data.get("ledger_status", "n/a"),
            "confirmed_at":       data.get("confirmed_at"),
            "ledger_month":       data.get("ledger_month"),
            "category":           data.get("category", "other"),
        })
        conn.commit()
        msg_id = cur.lastrowid

    # Upsert contact record if we have a counterparty
    if data.get("counterparty_phone"):
        _upsert_contact(data["counterparty_phone"], data.get("counterparty_name"))

    return msg_id


def get_messages(limit: int = 60, ledger_month: str | None = None) -> list:
    conn = get_conn()
    if ledger_month:
        rows = conn.execute(
            "SELECT * FROM messages WHERE ledger_month=? ORDER BY received_at DESC LIMIT ?",
            (ledger_month, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY received_at DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["risk_signals"] = json.loads(d["risk_signals"] or "[]")
        except (ValueError, TypeError):
            d["risk_signals"] = []
        result.append(d)
    return result


def update_ledger_status(msg_id: int, status: str) -> bool:
    """
    Transition ledger_status to 'confirmed' or 'rejected'.
    On confirm: updates the contact's verified inflow + recalculates trust score.
    Returns True if a row was actually updated.
    """
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    with _lock:
        cur = conn.execute(
            "UPDATE messages SET ledger_status=?, confirmed_at=? WHERE id=?",
            (status, now if status == "confirmed" else None, msg_id)
        )
        conn.commit()

    if status == "confirmed" and cur.rowcount:
        row = conn.execute("SELECT * FROM messages WHERE id=?", (msg_id,)).fetchone()
        if row and row["amount"] and row["counterparty_phone"]:
            with _lock:
                conn.execute(
                    """UPDATE contacts
                       SET total_verified_inflow = total_verified_inflow + ?,
                           txn_count = txn_count + 1
                       WHERE phone = ?""",
                    (row["amount"], row["counterparty_phone"])
                )
                conn.commit()
            _recalculate_trust(row["counterparty_phone"])

    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Contact operations
# ---------------------------------------------------------------------------

def _upsert_contact(phone: str, name: str | None = None):
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    with _lock:
        conn.execute("""
            INSERT INTO contacts (phone, display_name, first_seen, txn_count,
                                  total_verified_inflow, scam_reports_against, trust_score)
            VALUES (?, ?, ?, 0, 0.0, 0, 50.0)
            ON CONFLICT(phone) DO UPDATE SET
                display_name = COALESCE(excluded.display_name, contacts.display_name)
        """, (phone, name, now))
        conn.commit()


def _recalculate_trust(phone: str):
    """
    Trust score formula:
      base 50 + (2 per confirmed txn) − (15 per scam report against them)
    Clamped to [0, 100].
    Same underlying features as the risk score — the 'same job' design made
    literal in the code: one feature set, two labeled outputs.
    """
    conn = get_conn()
    row = conn.execute("SELECT * FROM contacts WHERE phone=?", (phone,)).fetchone()
    if not row:
        return
    score = 50.0 + (row["txn_count"] * 2.0) - (row["scam_reports_against"] * 15.0)
    score = max(0.0, min(100.0, score))
    with _lock:
        conn.execute("UPDATE contacts SET trust_score=? WHERE phone=?", (score, phone))
        conn.commit()


def get_contacts(limit: int = 20) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM contacts ORDER BY trust_score DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def report_contact_as_scam(phone: str):
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE contacts SET scam_reports_against = scam_reports_against + 1 WHERE phone=?",
            (phone,)
        )
        conn.commit()
    _recalculate_trust(phone)


# ---------------------------------------------------------------------------
# Community scam report operations
# ---------------------------------------------------------------------------

def add_community_report(text: str, embedding: list | None, summary: str = ""):
    """Store an anonymized scam pattern with its embedding for future similarity checks."""
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    emb_json = json.dumps(embedding) if embedding is not None else None
    with _lock:
        conn.execute("""
            INSERT INTO community_scam_reports
                (reported_text, embedding_json, pattern_summary, report_count, created_at)
            VALUES (?, ?, ?, 1, ?)
        """, (text[:600], emb_json, summary, now))
        conn.commit()


def get_community_reports(limit: int = 200) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM community_scam_reports ORDER BY report_count DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_setting(key: str, default: str = "") -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        conn.commit()


def get_all_settings() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------------------
# Ledger management
# ---------------------------------------------------------------------------

def _month_key(dt: datetime.date | None = None) -> str:
    """Return the 'YYYY-MM' key for the given date (today if None)."""
    d = dt or datetime.date.today()
    return d.strftime("%Y-%m")


def _month_label(month_key: str) -> str:
    """Convert '2026-07' → 'July 2026'."""
    dt = datetime.datetime.strptime(month_key, "%Y-%m")
    return dt.strftime("%B %Y")


def get_active_ledger_month() -> str | None:
    """Return the month_key of the currently active ledger, or None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT month_key FROM ledgers WHERE status='active' ORDER BY month_key DESC LIMIT 1"
    ).fetchone()
    return row["month_key"] if row else None


def check_ledger_for_month(month_key: str | None = None) -> dict:
    """
    Check whether a ledger exists for the given month (defaults to current month).
    Returns a dict with:
      month_key    — the YYYY-MM key
      exists       — True if a record exists
      status       — 'active' | 'closed' | 'inherited' | None
      previous     — month_key of the most recent past ledger (if any)
    """
    key = month_key or _month_key()
    conn = get_conn()
    row = conn.execute("SELECT * FROM ledgers WHERE month_key=?", (key,)).fetchone()
    prev = conn.execute(
        "SELECT month_key FROM ledgers WHERE month_key < ? ORDER BY month_key DESC LIMIT 1", (key,)
    ).fetchone()
    return {
        "month_key": key,
        "label": _month_label(key),
        "exists": row is not None,
        "status": row["status"] if row else None,
        "previous": prev["month_key"] if prev else None,
    }


def create_ledger(month_key: str | None = None, inherit: bool = False) -> dict:
    """
    Create a new ledger for the given month (default: current month).
    If inherit=True, the previous active ledger is marked 'inherited' (not closed),
    meaning its transactions are still visible in the historical view.
    If a ledger already exists for this month, return it unchanged.
    """
    key = month_key or _month_key()
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()

    existing = conn.execute("SELECT * FROM ledgers WHERE month_key=?", (key,)).fetchone()
    if existing:
        return {"month_key": key, "label": _month_label(key), "status": existing["status"], "created": False}

    with _lock:
        # Mark any previously active ledger as closed
        conn.execute(
            "UPDATE ledgers SET status=? WHERE status='active'",
            ("inherited" if inherit else "closed",)
        )
        conn.execute(
            "INSERT INTO ledgers (month_key, label, status, created_at) VALUES (?, ?, 'active', ?)",
            (key, _month_label(key), now)
        )
        conn.commit()
    return {"month_key": key, "label": _month_label(key), "status": "active", "created": True}


def list_ledgers() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ledgers ORDER BY month_key DESC").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dashboard aggregates
# ---------------------------------------------------------------------------

def get_stats(ledger_month: str | None = None) -> dict:
    """
    Return all counters, P&L data, and cash-flow series for the dashboard.
    When ledger_month is supplied (e.g. '2026-07'), stats are scoped to that
    month. Otherwise, the currently active ledger month is used.
    """
    conn = get_conn()
    month = ledger_month or get_active_ledger_month()

    # Base filter applied to all per-month queries
    month_filter = "AND ledger_month = :month" if month else ""
    base_params  = {"month": month} if month else {}

    total_messages = conn.execute(
        f"SELECT COUNT(*) FROM messages {('WHERE ledger_month=:month' if month else '')}" ,
        base_params
    ).fetchone()[0]
    scam_count = conn.execute(
        f"SELECT COUNT(*) FROM messages WHERE classification='scam' {month_filter}",
        base_params
    ).fetchone()[0]
    suspicious_count = conn.execute(
        f"SELECT COUNT(*) FROM messages WHERE classification='suspicious' {month_filter}",
        base_params
    ).fetchone()[0]
    confirmed_txns = conn.execute(
        f"SELECT COUNT(*) FROM messages WHERE ledger_status='confirmed' {month_filter}",
        base_params
    ).fetchone()[0]
    draft_count = conn.execute(
        f"SELECT COUNT(*) FROM messages WHERE ledger_status='draft' AND amount IS NOT NULL {month_filter}",
        base_params
    ).fetchone()[0]
    contacts_count  = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    community_count = conn.execute("SELECT COUNT(*) FROM community_scam_reports").fetchone()[0]

    # ── Profit & Loss ──────────────────────────────────────────────────────
    # Earnings = confirmed inflows
    total_earnings = conn.execute(
        f"""SELECT COALESCE(SUM(amount), 0) FROM messages
            WHERE ledger_status='confirmed' AND amount IS NOT NULL
              AND (txn_direction='inflow' OR txn_direction IS NULL)
              {month_filter}""",
        base_params
    ).fetchone()[0]
    # Spendings = confirmed outflows
    total_spendings = conn.execute(
        f"""SELECT COALESCE(SUM(amount), 0) FROM messages
            WHERE ledger_status='confirmed' AND amount IS NOT NULL
              AND txn_direction='outflow'
              {month_filter}""",
        base_params
    ).fetchone()[0]
    net_profit_loss = round(total_earnings - total_spendings, 2)

    # ── Cash-flow chart: daily breakdown for the selected month ────────────
    if month:
        cashflow_rows = conn.execute("""
            SELECT DATE(received_at) AS day,
                   COALESCE(SUM(CASE WHEN txn_direction='inflow'  OR txn_direction IS NULL THEN amount ELSE 0 END), 0) AS inflow,
                   COALESCE(SUM(CASE WHEN txn_direction='outflow' THEN amount ELSE 0 END), 0) AS outflow
            FROM messages
            WHERE ledger_status='confirmed' AND amount IS NOT NULL
              AND ledger_month = :month
            GROUP BY day ORDER BY day
        """, {"month": month}).fetchall()
    else:
        cashflow_rows = conn.execute("""
            SELECT DATE(received_at) AS day,
                   COALESCE(SUM(CASE WHEN txn_direction='inflow'  OR txn_direction IS NULL THEN amount ELSE 0 END), 0) AS inflow,
                   COALESCE(SUM(CASE WHEN txn_direction='outflow' THEN amount ELSE 0 END), 0) AS outflow
            FROM messages
            WHERE ledger_status='confirmed' AND amount IS NOT NULL
              AND received_at >= DATE('now', '-30 days')
            GROUP BY day ORDER BY day
        """).fetchall()

    return {
        "total_messages":   total_messages,
        "scam_count":       scam_count,
        "suspicious_count": suspicious_count,
        "confirmed_txns":   confirmed_txns,
        "total_inflow":     round(total_earnings, 2),
        "total_earnings":   round(total_earnings, 2),
        "total_spendings":  round(total_spendings, 2),
        "net_profit_loss":  net_profit_loss,
        "draft_count":      draft_count,
        "contacts_count":   contacts_count,
        "community_count":  community_count,
        "active_month":     month,
        "cashflow": [
            {"day": r["day"], "inflow": r["inflow"], "outflow": r["outflow"]}
            for r in cashflow_rows
        ],
    }


def get_export_data(ledger_month: str | None = None) -> list:
    """Return confirmed transactions for credit-ready export, optionally filtered by month."""
    conn = get_conn()
    if ledger_month:
        rows = conn.execute("""
            SELECT id, received_at, ledger_month, channel, counterparty_name, counterparty_phone,
                   amount, currency, purpose, payment_method, upi_reference, txn_direction,
                   risk_score, classification, confirmed_at
            FROM messages
            WHERE ledger_status='confirmed' AND amount IS NOT NULL AND ledger_month=?
            ORDER BY received_at DESC
        """, (ledger_month,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, received_at, ledger_month, channel, counterparty_name, counterparty_phone,
                   amount, currency, purpose, payment_method, upi_reference, txn_direction,
                   risk_score, classification, confirmed_at
            FROM messages
            WHERE ledger_status='confirmed' AND amount IS NOT NULL
            ORDER BY received_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Inventory operations
# ---------------------------------------------------------------------------

def get_inventory() -> list:
    """Return all inventory items ordered alphabetically."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM inventory ORDER BY item_name ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def add_or_update_inventory_item(
    item_name: str,
    quantity: float = 0,
    cost_price: float = 0,
    unit: str = "unit",
) -> dict:
    """Insert a new inventory item or update an existing one by name."""
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    with _lock:
        conn.execute("""
            INSERT INTO inventory (item_name, quantity, cost_price, unit, created_at, updated_at)
            VALUES (:name, :qty, :price, :unit, :now, :now)
            ON CONFLICT(item_name) DO UPDATE SET
                quantity   = :qty,
                cost_price = :price,
                unit       = :unit,
                updated_at = :now
        """, {"name": item_name.strip(), "qty": quantity, "price": cost_price, "unit": unit, "now": now})
        conn.commit()
    row = conn.execute("SELECT * FROM inventory WHERE item_name=?", (item_name.strip(),)).fetchone()
    return dict(row) if row else {}


def adjust_stock(item_name: str, qty_delta: float) -> dict | None:
    """
    Increment or decrement the quantity of an inventory item.
    Returns the updated row, or None if item not found.
    """
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    with _lock:
        cur = conn.execute("""
            UPDATE inventory
            SET quantity   = MAX(0, quantity + :delta),
                updated_at = :now
            WHERE item_name = :name
        """, {"delta": qty_delta, "name": item_name, "now": now})
        conn.commit()
    if cur.rowcount == 0:
        return None
    row = conn.execute("SELECT * FROM inventory WHERE item_name=?", (item_name,)).fetchone()
    return dict(row) if row else None


def delete_inventory_item(item_id: int) -> bool:
    """Delete an inventory item by its ID. Returns True if deleted."""
    conn = get_conn()
    with _lock:
        cur = conn.execute("DELETE FROM inventory WHERE id=?", (item_id,))
        conn.commit()
    return cur.rowcount > 0


def update_inventory_price(item_name: str, new_cost_price: float) -> dict | None:
    """Update the cost price of an inventory item by name."""
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    with _lock:
        cur = conn.execute("""
            UPDATE inventory
            SET cost_price = :price,
                updated_at = :now
            WHERE item_name = :name
        """, {"price": new_cost_price, "name": item_name, "now": now})
        conn.commit()
    if cur.rowcount == 0:
        return None
    row = conn.execute("SELECT * FROM inventory WHERE item_name=?", (item_name,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Khata / outstanding dues
# ---------------------------------------------------------------------------

def get_outstanding_dues() -> list:
    """
    Return a list of contacts who owe money (khata credit).
    Computed by summing confirmed inflows minus confirmed outflows per contact.
    Positive net = they owe us money.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            counterparty_name,
            counterparty_phone,
            COALESCE(SUM(
                CASE WHEN txn_direction = 'inflow' OR txn_direction IS NULL THEN amount ELSE -amount END
            ), 0) AS net_owed,
            MIN(confirmed_at) AS earliest_txn,
            MAX(confirmed_at) AS latest_txn,
            COUNT(*) AS txn_count
        FROM messages
        WHERE ledger_status = 'confirmed'
          AND amount IS NOT NULL
          AND counterparty_name IS NOT NULL
        GROUP BY counterparty_phone, counterparty_name
        HAVING net_owed > 0
        ORDER BY net_owed DESC
    """).fetchall()
    result = []
    now = datetime.datetime.utcnow()
    for r in rows:
        d = dict(r)
        # Calculate days since earliest transaction
        try:
            earliest = datetime.datetime.fromisoformat(d["earliest_txn"])
            d["days_outstanding"] = (now - earliest).days
        except (TypeError, ValueError):
            d["days_outstanding"] = 0
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Daily snapshots
# ---------------------------------------------------------------------------

def save_daily_snapshot(
    cash_balance: float,
    inventory_value: float,
    khata_receivable: float,
    note: str = "",
    date: str | None = None,
) -> dict:
    """Save or overwrite the daily closing position."""
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    target_date = date or datetime.date.today().isoformat()
    with _lock:
        conn.execute("""
            INSERT INTO daily_snapshots
                (date, cash_balance, inventory_value, khata_receivable, note, created_at)
            VALUES (:d, :cash, :inv, :khata, :note, :now)
            ON CONFLICT(date) DO UPDATE SET
                cash_balance      = :cash,
                inventory_value   = :inv,
                khata_receivable  = :khata,
                note              = :note,
                created_at        = :now
        """, {"d": target_date, "cash": cash_balance, "inv": inventory_value,
              "khata": khata_receivable, "note": note, "now": now})
        conn.commit()
    row = conn.execute("SELECT * FROM daily_snapshots WHERE date=?", (target_date,)).fetchone()
    return dict(row) if row else {}


def get_daily_snapshots(limit: int = 30) -> list:
    """Return the last N daily snapshots ordered newest-first."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Expense category breakdown
# ---------------------------------------------------------------------------

def get_category_breakdown(ledger_month: str | None = None) -> list:
    """
    Return total confirmed outflow amounts grouped by category.
    """
    conn = get_conn()
    month = ledger_month or get_active_ledger_month()
    if month:
        rows = conn.execute("""
            SELECT COALESCE(category, 'other') AS category,
                   COALESCE(SUM(amount), 0) AS total
            FROM messages
            WHERE ledger_status = 'confirmed'
              AND amount IS NOT NULL
              AND txn_direction = 'outflow'
              AND ledger_month = ?
            GROUP BY category
            ORDER BY total DESC
        """, (month,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT COALESCE(category, 'other') AS category,
                   COALESCE(SUM(amount), 0) AS total
            FROM messages
            WHERE ledger_status = 'confirmed'
              AND amount IS NOT NULL
              AND txn_direction = 'outflow'
            GROUP BY category
            ORDER BY total DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# User and Shop management (Auth)
# ---------------------------------------------------------------------------

def create_shop(name: str, phone: str | None = None, address: str | None = None) -> dict:
    """
    Create a new shop.
    
    Args:
        name: Shop/business name
        phone: Contact phone (optional)
        address: Physical address (optional)
        
    Returns:
        Dict with shop details including id
    """
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    with _lock:
        cur = conn.execute(
            """INSERT INTO shops (name, phone, address, created_at)
               VALUES (?, ?, ?, ?)""",
            (name, phone, address, now)
        )
        conn.commit()
        shop_id = cur.lastrowid
    
    row = conn.execute("SELECT * FROM shops WHERE id=?", (shop_id,)).fetchone()
    return dict(row) if row else {}


def get_shop(shop_id: int) -> dict | None:
    """Get shop details by ID."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM shops WHERE id=?", (shop_id,)).fetchone()
    return dict(row) if row else None


def create_user(
    shop_id: int,
    email: str,
    password_hash: str,
    full_name: str | None = None,
) -> dict:
    """
    Create a new user account.
    
    Args:
        shop_id: Reference to the user's shop
        email: Unique email address
        password_hash: Bcrypt-hashed password (never plaintext)
        full_name: User's display name (optional)
        
    Returns:
        Dict with user details including id
        
    Raises:
        sqlite3.IntegrityError: If email already exists
    """
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    with _lock:
        cur = conn.execute(
            """INSERT INTO users (shop_id, email, password_hash, full_name, is_active, created_at)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (shop_id, email.lower(), password_hash, full_name, now)
        )
        conn.commit()
        user_id = cur.lastrowid
    
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else {}


def get_user_by_email(email: str) -> dict | None:
    """
    Get user by email address.
    
    Args:
        email: Email to search for
        
    Returns:
        User dict if found, None otherwise
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email=?",
        (email.lower(),)
    ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """Get user by ID."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# AI Decision Intelligence — helper queries
# ---------------------------------------------------------------------------

def get_supplier_history(limit: int = 200) -> list:
    """
    Aggregate confirmed outflow (purchase) transactions by supplier name.
    Returns per-supplier stats useful for Supplier Intelligence scoring.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            counterparty_name                                  AS supplier_name,
            COUNT(*)                                           AS order_count,
            COALESCE(SUM(amount), 0)                           AS total_spent,
            COALESCE(AVG(amount), 0)                           AS avg_order_value,
            MIN(confirmed_at)                                  AS first_order,
            MAX(confirmed_at)                                  AS last_order,
            GROUP_CONCAT(COALESCE(purpose,''), '||')           AS purposes
        FROM messages
        WHERE ledger_status = 'confirmed'
          AND txn_direction = 'outflow'
          AND counterparty_name IS NOT NULL
          AND counterparty_name != ''
        GROUP BY counterparty_name
        ORDER BY total_spent DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_sales_velocity(days: int = 90) -> list:
    """
    Return per-category/purpose sales velocity (count + total amount) for the
    last `days` days of confirmed inflow transactions.
    Used for demand forecasting.
    """
    conn = get_conn()
    since = (
        datetime.datetime.utcnow() - datetime.timedelta(days=days)
    ).isoformat()
    rows = conn.execute("""
        SELECT
            COALESCE(category, 'other')    AS category,
            COALESCE(purpose, 'general')   AS purpose,
            COUNT(*)                       AS sale_count,
            COALESCE(SUM(amount), 0)       AS total_revenue,
            COALESCE(AVG(amount), 0)       AS avg_sale_value,
            MIN(confirmed_at)              AS first_sale,
            MAX(confirmed_at)              AS last_sale
        FROM messages
        WHERE ledger_status = 'confirmed'
          AND txn_direction = 'inflow'
          AND confirmed_at >= ?
        GROUP BY category, purpose
        ORDER BY total_revenue DESC
        LIMIT 50
    """, (since,)).fetchall()
    return [dict(r) for r in rows]


def get_business_memory() -> dict:
    """
    Retrieve the AI-generated business memory summary cached in settings.
    Returns empty dict if not yet generated.
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM settings WHERE key='business_memory'"
    ).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):
        return {}


def set_business_memory(memory: dict) -> None:
    """
    Persist AI-generated business memory to the settings table.
    """
    conn = get_conn()
    value = json.dumps(memory, ensure_ascii=False)
    with _lock:
        conn.execute("""
            INSERT INTO settings (key, value) VALUES ('business_memory', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (value,))
        conn.commit()

