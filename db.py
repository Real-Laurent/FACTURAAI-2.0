import logging
import sqlite3
import hashlib
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from config.loader import get_config

log = logging.getLogger(__name__)


def db_path() -> str:
    return get_config()["paths"]["db"]


def get_connection() -> sqlite3.Connection:
    path = db_path()
    os.makedirs(Path(path).parent, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def transaction():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with transaction() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS invoices (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT,
                supplier        TEXT,
                invoice_number  TEXT,
                net_amount      REAL,
                vat_amount      REAL,
                vat_rate        REAL,
                vat_breakdown   TEXT,
                total_amount    REAL,
                currency        TEXT DEFAULT 'EUR',
                file_path       TEXT,
                source          TEXT CHECK(source IN ('gmail','scan','backfill')),
                confidence      REAL,
                needs_review    INTEGER DEFAULT 0,
                vat_flag        INTEGER DEFAULT 0,
                spike_flag      INTEGER DEFAULT 0,
                ai_flag         INTEGER DEFAULT 0,
                ai_issue        TEXT,
                rejected        INTEGER DEFAULT 0,
                reject_reason   TEXT,
                extractor_pending INTEGER DEFAULT 0,
                hash            TEXT UNIQUE,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS processing_log (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp        TEXT DEFAULT (datetime('now')),
                cycle_number     INTEGER,
                files_found      INTEGER DEFAULT 0,
                files_processed  INTEGER DEFAULT 0,
                files_failed     INTEGER DEFAULT 0,
                files_skipped    INTEGER DEFAULT 0,
                duration_seconds REAL
            );

            CREATE TABLE IF NOT EXISTS heartbeat (
                id        INTEGER PRIMARY KEY CHECK (id = 1),
                last_seen TEXT
            );

            INSERT OR IGNORE INTO heartbeat (id, last_seen) VALUES (1, datetime('now'));

            CREATE INDEX IF NOT EXISTS idx_invoices_date     ON invoices(date);
            CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier);
            CREATE INDEX IF NOT EXISTS idx_invoices_hash     ON invoices(hash);
            CREATE INDEX IF NOT EXISTS idx_invoices_review   ON invoices(needs_review);

            CREATE TABLE IF NOT EXISTS bank_transactions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                date                TEXT,
                description         TEXT,
                amount              REAL,
                balance             REAL,
                matched_invoice_id  INTEGER REFERENCES invoices(id),
                source_file         TEXT,
                imported_at         TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_bank_date    ON bank_transactions(date);
            CREATE INDEX IF NOT EXISTS idx_bank_matched ON bank_transactions(matched_invoice_id);

            CREATE TABLE IF NOT EXISTS cash_income (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                amount      REAL NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cash_income_date ON cash_income(date);
        """)
    migrate_db()


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_duplicate(file_hash: str) -> bool:
    with transaction() as conn:
        row = conn.execute("SELECT id FROM invoices WHERE hash = ?", (file_hash,)).fetchone()
    return row is not None


def migrate_db():
    """Add columns introduced after the initial schema (safe to re-run)."""
    with transaction() as conn:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(invoices)").fetchall()
        }
        if "vat_breakdown" not in existing:
            conn.execute("ALTER TABLE invoices ADD COLUMN vat_breakdown TEXT")
        if "category" not in existing:
            conn.execute("ALTER TABLE invoices ADD COLUMN category TEXT")
        if "ai_flag" not in existing:
            conn.execute("ALTER TABLE invoices ADD COLUMN ai_flag INTEGER DEFAULT 0")
        if "ai_issue" not in existing:
            conn.execute("ALTER TABLE invoices ADD COLUMN ai_issue TEXT")
        if "rejected" not in existing:
            conn.execute("ALTER TABLE invoices ADD COLUMN rejected INTEGER DEFAULT 0")
        if "reject_reason" not in existing:
            conn.execute("ALTER TABLE invoices ADD COLUMN reject_reason TEXT")
        if "extractor_pending" not in existing:
            conn.execute("ALTER TABLE invoices ADD COLUMN extractor_pending INTEGER DEFAULT 0")


def insert_invoice(record: dict) -> int:
    cols = [
        "date", "supplier", "invoice_number", "net_amount", "vat_amount",
        "vat_rate", "vat_breakdown", "total_amount", "currency", "file_path",
        "source", "confidence", "needs_review", "vat_flag", "spike_flag", "hash",
        "category", "ai_flag", "ai_issue", "rejected", "reject_reason",
        "extractor_pending",
    ]
    keys = [c for c in cols if c in record]
    placeholders = ", ".join(["?"] * len(keys))
    col_str = ", ".join(keys)
    vals = [record[k] for k in keys]
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO invoices ({col_str}) VALUES ({placeholders})", vals
        )
        return cur.lastrowid


def update_invoice(invoice_id: int, fields: dict):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [invoice_id]
    with transaction() as conn:
        conn.execute(f"UPDATE invoices SET {set_clause} WHERE id = ?", vals)


def log_cycle(cycle_number: int, files_found: int, files_processed: int,
              files_failed: int, files_skipped: int, duration_seconds: float):
    with transaction() as conn:
        conn.execute(
            """INSERT INTO processing_log
               (cycle_number, files_found, files_processed, files_failed, files_skipped, duration_seconds)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (cycle_number, files_found, files_processed, files_failed, files_skipped, duration_seconds),
        )


def update_heartbeat():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute("UPDATE heartbeat SET last_seen = ? WHERE id = 1", (now,))


def clear_all_data() -> dict:
    """Delete all invoices, bank transactions, and processing log rows.
    Keeps the schema intact so the service can keep running."""
    with transaction() as conn:
        inv   = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        bank  = conn.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        conn.execute("DELETE FROM bank_transactions")
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM processing_log")
    log.warning("clear_all_data: removed %d invoices, %d bank transactions", inv, bank)
    return {"invoices": inv, "bank_transactions": bank}


def get_monthly_average(year: int, month: int) -> float:
    """Rolling average total_amount for the given month (previous 3 months)."""
    with transaction() as conn:
        row = conn.execute(
            """SELECT AVG(total_amount) FROM invoices
               WHERE date < ? AND total_amount IS NOT NULL""",
            (f"{year:04d}-{month:02d}-01",),
        ).fetchone()
    val = row[0] if row and row[0] is not None else 0.0
    return val


def get_all_invoices(filters: dict = None, page: int = 1, page_size: int = 50):
    where, params = _build_where(filters)
    offset = (page - 1) * page_size
    with transaction() as conn:
        rows = conn.execute(
            f"SELECT * FROM invoices {where} ORDER BY date DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
        count = conn.execute(
            f"SELECT COUNT(*) FROM invoices {where}", params
        ).fetchone()[0]
    return [dict(r) for r in rows], count


def get_monthly_totals():
    with transaction() as conn:
        rows = conn.execute(
            """SELECT substr(date,1,7) as month,
                      SUM(net_amount)   as net,
                      SUM(vat_amount)   as vat,
                      SUM(total_amount) as total,
                      COUNT(*)          as count
               FROM invoices
               WHERE date IS NOT NULL
               GROUP BY month
               ORDER BY month DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_last_cycle():
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM processing_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}


def get_heartbeat():
    with transaction() as conn:
        row = conn.execute("SELECT last_seen FROM heartbeat WHERE id = 1").fetchone()
    return row["last_seen"] if row else None


def get_review_queue():
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM invoices WHERE needs_review = 1 AND rejected = 0 ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_rejected_invoices(page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    with transaction() as conn:
        rows = conn.execute(
            """SELECT * FROM invoices WHERE rejected = 1
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (page_size, offset),
        ).fetchall()
        count = conn.execute("SELECT COUNT(*) FROM invoices WHERE rejected = 1").fetchone()[0]
    return [dict(r) for r in rows], count


def get_invoices_for_period(start_date: str, end_date: str,
                            confirmed_only: bool = True) -> list[dict]:
    where = "WHERE date >= ? AND date <= ? AND rejected = 0"
    if confirmed_only:
        where += " AND needs_review = 0"
    with transaction() as conn:
        rows = conn.execute(
            f"SELECT * FROM invoices {where} ORDER BY date",
            (start_date, end_date),
        ).fetchall()
    return [dict(r) for r in rows]


def get_income_for_period(start_date: str, end_date: str) -> float:
    """Business income (ingresos) for a date range: bank credits (sales
    deposited to the account) plus manually-entered cash income. Feeds
    Modelo 130 and Modelo 100, both computed from net income = income -
    expenses, and the P&L statement (reports/pnl.py)."""
    return round(
        get_bank_income_for_period(start_date, end_date)
        + get_cash_income_total_for_period(start_date, end_date),
        2,
    )


def get_bank_income_for_period(start_date: str, end_date: str) -> float:
    """Sum of credit (positive-amount) bank transactions in the period —
    the bank side of income. Debits (negative amounts) are expenses,
    already matched against invoices elsewhere; see bank._find_match()."""
    with transaction() as conn:
        row = conn.execute(
            """SELECT SUM(amount) FROM bank_transactions
               WHERE amount > 0 AND date >= ? AND date <= ?""",
            (start_date, end_date),
        ).fetchone()
    return round(row[0] or 0.0, 2)


# ---- cash income (manual entry — for sales the bank statement won't show) ----

def insert_cash_income(date: str, amount: float, description: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO cash_income (date, amount, description) VALUES (?, ?, ?)",
            (date, amount, description),
        )
        return cur.lastrowid


def delete_cash_income(entry_id: int) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM cash_income WHERE id = ?", (entry_id,))


def get_cash_income_total_for_period(start_date: str, end_date: str) -> float:
    with transaction() as conn:
        row = conn.execute(
            "SELECT SUM(amount) FROM cash_income WHERE date >= ? AND date <= ?",
            (start_date, end_date),
        ).fetchone()
    return round(row[0] or 0.0, 2)


def get_cash_income_for_period(start_date: str, end_date: str) -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            """SELECT * FROM cash_income WHERE date >= ? AND date <= ?
               ORDER BY date DESC, id DESC""",
            (start_date, end_date),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_cash_income(page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    with transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM cash_income ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
        count = conn.execute("SELECT COUNT(*) FROM cash_income").fetchone()[0]
    return [dict(r) for r in rows], count


def get_available_years() -> list[int]:
    with transaction() as conn:
        rows = conn.execute(
            """SELECT DISTINCT substr(date,1,4) as yr
               FROM invoices WHERE date IS NOT NULL
               ORDER BY yr DESC"""
        ).fetchall()
    return [int(r[0]) for r in rows if r[0] and r[0].isdigit()]


def get_category_totals(year: int | None = None) -> list[dict]:
    if year:
        where, params = "WHERE date LIKE ?", [f"{year}-%"]
    else:
        where, params = "", []
    with transaction() as conn:
        rows = conn.execute(
            f"""SELECT category,
                       SUM(net_amount)   as net,
                       SUM(vat_amount)   as vat,
                       SUM(total_amount) as total,
                       COUNT(*)          as count
                FROM invoices {where}
                GROUP BY category
                ORDER BY total DESC""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


# ---- bank transactions ----

def bank_file_already_imported(source_file: str) -> bool:
    with transaction() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE source_file = ?", (source_file,)
        ).fetchone()[0]
    return n > 0


def insert_bank_transaction(tx: dict, source_file: str) -> int | None:
    try:
        with transaction() as conn:
            cur = conn.execute(
                """INSERT INTO bank_transactions (date, description, amount, balance, source_file)
                   VALUES (?, ?, ?, ?, ?)""",
                (tx.get("date"), tx.get("description"),
                 tx.get("amount"), tx.get("balance"), source_file),
            )
            return cur.lastrowid
    except Exception as e:
        log.warning("insert_bank_transaction failed: %s", e)
        return None


def match_bank_transaction(tx_id: int, invoice_id: int):
    with transaction() as conn:
        conn.execute(
            "UPDATE bank_transactions SET matched_invoice_id = ? WHERE id = ?",
            (invoice_id, tx_id),
        )


def get_bank_transactions(page: int = 1, page_size: int = 100) -> tuple[list[dict], int]:
    offset = (page - 1) * page_size
    with transaction() as conn:
        rows = conn.execute(
            """SELECT bt.*,
                      i.supplier     as matched_supplier,
                      i.total_amount as matched_total,
                      i.invoice_number as matched_invoice_number
               FROM bank_transactions bt
               LEFT JOIN invoices i ON bt.matched_invoice_id = i.id
               ORDER BY bt.date DESC, bt.id DESC
               LIMIT ? OFFSET ?""",
            (page_size, offset),
        ).fetchall()
        count = conn.execute(
            "SELECT COUNT(*) FROM bank_transactions"
        ).fetchone()[0]
    return [dict(r) for r in rows], count


def get_unmatched_transactions() -> list[dict]:
    with transaction() as conn:
        rows = conn.execute(
            """SELECT * FROM bank_transactions
               WHERE matched_invoice_id IS NULL
               ORDER BY date DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_bank_stats() -> dict:
    with transaction() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        matched = conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE matched_invoice_id IS NOT NULL"
        ).fetchone()[0]
    return {"total": total, "matched": matched, "unmatched": total - matched}


def _build_where(filters: dict):
    # Rejected (non-factura) rows have their own dashboard view — always
    # exclude them from the main invoice list regardless of other filters.
    clauses, params = ["rejected = 0"], []
    if not filters:
        return "WHERE " + clauses[0], params
    if filters.get("supplier"):
        clauses.append("supplier LIKE ?")
        params.append(f"%{filters['supplier']}%")
    if filters.get("date_from"):
        clauses.append("date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        clauses.append("date <= ?")
        params.append(filters["date_to"])
    if filters.get("amount_min") is not None:
        clauses.append("total_amount >= ?")
        params.append(filters["amount_min"])
    if filters.get("amount_max") is not None:
        clauses.append("total_amount <= ?")
        params.append(filters["amount_max"])
    if filters.get("needs_review") is not None:
        clauses.append("needs_review = ?")
        params.append(1 if filters["needs_review"] else 0)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params
