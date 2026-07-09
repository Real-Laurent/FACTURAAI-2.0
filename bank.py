"""
Bank statement import (CSV or Excel) and invoice reconciliation.

Supports common Spanish bank export formats (Santander, CaixaBank, BBVA, Sabadell)
in either CSV or XLSX. Auto-matches debit transactions to invoices by amount
± €0.02 within ±7 days. Credit (positive-amount) transactions are income —
see db.get_bank_income_for_period(), which feeds Modelo 130/100 and the P&L
statement (reports/pnl.py).
"""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date as _date, datetime, timedelta

import db
from extractors.helpers import parse_date

log = logging.getLogger(__name__)

_DATE_COLS = {"fecha", "date", "data", "f.valor", "f.operación", "f.operacion",
              "fecha operación", "fecha operacion", "fecha valor"}
_DESC_COLS = {"concepto", "descripción", "descripcion", "descripció",
              "concepcio", "description", "movimiento", "referencia"}
_AMT_COLS  = {"importe", "import", "amount", "cargo/abono", "movimiento (eur)"}
_BAL_COLS  = {"saldo", "balance", "disponible", "saldo disponible"}


def _detect_delimiter(text: str) -> str:
    sample = text[:2000]
    for delim in (";", "\t", ","):
        if sample.count(delim) > sample.count("\n") // 2:
            return delim
    return ";"


def _parse_es_number(s: str) -> float | None:
    if not s:
        return None
    s = s.strip().strip('"').replace("\xa0", "").replace(" ", "")
    if not s or s in ("-", "+"):
        return None
    # Spanish: 1.234,56 → 1234.56  /  plain: 1234.56 stays
    if "," in s and "." in s:
        # which comes last? last separator is the decimal one
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _resolve_date(raw: str) -> str | None:
    if not raw:
        return None
    # Already ISO (Excel-native date/datetime cells are pre-formatted this
    # way before reaching here — see parse_bank_excel) — a 4-digit year up
    # front is unambiguous vs. Spanish DD-MM-YY, so check it first.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    return parse_date(raw.replace("-", "/"))


def _rows_to_transactions(rows: list[list[str]]) -> list[dict]:
    """Shared header-detection + row-parsing logic for both CSV and Excel
    input, once each has been normalised to a list of string rows."""
    if not rows:
        return []

    # Find the header row: first row with >= 3 non-empty cells
    header_idx = 0
    for i, row in enumerate(rows):
        if sum(1 for c in row if c.strip()) >= 3:
            header_idx = i
            break

    raw_headers = [h.strip().strip('"').lower() for h in rows[header_idx]]

    col: dict[str, int | None] = {"date": None, "desc": None, "amount": None, "balance": None}
    for i, h in enumerate(raw_headers):
        if h in _DATE_COLS and col["date"] is None:
            col["date"] = i
        elif h in _DESC_COLS and col["desc"] is None:
            col["desc"] = i
        elif h in _AMT_COLS and col["amount"] is None:
            col["amount"] = i
        elif h in _BAL_COLS and col["balance"] is None:
            col["balance"] = i

    # Positional fallback when headers are not recognised
    if col["date"] is None:
        if len(raw_headers) >= 3:
            col["date"], col["desc"], col["amount"] = 0, 1, 2
        if len(raw_headers) >= 4:
            col["balance"] = 3

    def _cell(row: list[str], idx: int | None) -> str:
        if idx is None or idx >= len(row):
            return ""
        return row[idx].strip().strip('"')

    transactions = []
    for row in rows[header_idx + 1:]:
        if not row or not any(c.strip() for c in row):
            continue
        raw_date = _cell(row, col["date"])
        desc     = _cell(row, col["desc"])
        raw_amt  = _cell(row, col["amount"])
        raw_bal  = _cell(row, col["balance"])

        date    = _resolve_date(raw_date) if raw_date else None
        amount  = _parse_es_number(raw_amt)
        balance = _parse_es_number(raw_bal)

        if date and amount is not None:
            transactions.append({
                "date":        date,
                "description": desc,
                "amount":      amount,
                "balance":     balance,
            })
        else:
            log.debug("Skipped bank row (no date/amount): %s", row)

    return transactions


def parse_bank_csv(text: str) -> list[dict]:
    """Parse bank statement CSV text. Returns list of {date, description, amount, balance}."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    delim = _detect_delimiter(text)
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    except Exception as e:
        log.error("CSV parse error: %s", e)
        return []
    return _rows_to_transactions(rows)


def parse_bank_excel(file_bytes: bytes) -> list[dict]:
    """Parse bank statement XLSX bytes. Returns list of {date, description, amount, balance}."""
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception as e:
        log.error("Excel parse error: %s", e)
        return []

    try:
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = []
            for c in row:
                if c is None:
                    cells.append("")
                elif isinstance(c, (_date, datetime)):
                    cells.append(c.strftime("%Y-%m-%d"))
                else:
                    cells.append(str(c))
            rows.append(cells)
    finally:
        wb.close()

    return _rows_to_transactions(rows)


def import_bank_file(data: bytes, source_filename: str) -> dict:
    """
    Parse a bank statement (CSV or XLSX, by file extension) and insert into
    bank_transactions. Returns {imported, matched, skipped, already_imported}.
    """
    if db.bank_file_already_imported(source_filename):
        return {"imported": 0, "matched": 0, "skipped": 0, "already_imported": True}

    ext = source_filename.lower().rsplit(".", 1)[-1] if "." in source_filename else ""
    if ext in ("xlsx", "xls"):
        rows = parse_bank_excel(data)
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        rows = parse_bank_csv(text)

    if not rows:
        return {"imported": 0, "matched": 0, "skipped": 0, "already_imported": False}

    imported = matched = skipped = 0
    for tx in rows:
        tx_id = db.insert_bank_transaction(tx, source_filename)
        if tx_id is None:
            skipped += 1
            continue
        imported += 1
        inv_id = _find_match(tx)
        if inv_id:
            db.match_bank_transaction(tx_id, inv_id)
            matched += 1

    return {"imported": imported, "matched": matched,
            "skipped": skipped, "already_imported": False}


def rematch_all() -> int:
    """Re-run auto-match for all unmatched transactions. Returns number newly matched."""
    matched = 0
    for tx in db.get_unmatched_transactions():
        inv_id = _find_match(tx)
        if inv_id:
            db.match_bank_transaction(tx["id"], inv_id)
            matched += 1
    return matched


def _find_match(tx: dict) -> int | None:
    """
    Return invoice.id if a unique invoice matches this transaction by amount + date.
    Only considers debit (negative) transactions — credits are income, not expenses.
    """
    amount = tx.get("amount")
    date   = tx.get("date")
    if not amount or not date:
        return None
    if amount >= 0:
        return None  # credit/income — handled by db.get_bank_income_for_period()

    target = abs(amount)
    try:
        tx_dt  = datetime.strptime(date[:10], "%Y-%m-%d")
    except ValueError:
        return None

    d_from = (tx_dt - timedelta(days=7)).strftime("%Y-%m-%d")
    d_to   = (tx_dt + timedelta(days=7)).strftime("%Y-%m-%d")

    candidates = db.get_invoices_for_period(d_from, d_to, confirmed_only=False)
    matches = [
        inv for inv in candidates
        if inv.get("total_amount") is not None
        and abs(abs(float(inv["total_amount"])) - target) <= 0.02
    ]
    return matches[0]["id"] if len(matches) == 1 else None
