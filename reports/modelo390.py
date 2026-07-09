"""
Modelo 390 — annual IVA summary draft.
Aggregates the full calendar year; reuses the 303 computation core.
"""
from __future__ import annotations

import db
from reports.modelo303 import _compute, as_csv as _303_csv


def generate(year: int) -> dict:
    invoices = db.get_invoices_for_period(f"{year}-01-01", f"{year}-12-31")
    result = _compute(
        invoices,
        year=year,
        periodo=str(year),
        start_date=f"{year}-01-01",
        end_date=f"{year}-12-31",
    )
    return result


def as_csv(report: dict) -> str:
    text = _303_csv(report)
    return text.replace("Modelo 303 — Borrador IVA", "Modelo 390 — Resumen Anual IVA", 1)
