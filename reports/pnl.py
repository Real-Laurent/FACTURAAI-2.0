"""
P&L statement (Cuenta de Perdidas y Ganancias) — quarterly or annual.

Income = bank credits (db.get_bank_income_for_period) + manually-entered
cash income (db.get_cash_income_total_for_period) — the same combined
figure db.get_income_for_period() feeds into Modelo 130/100. Expenses =
FacturaAI's invoice ledger (net_amount), broken down by category.

Unlike Modelo 130/100, this report is not a tax-office draft — it's an
internal management view of income vs. expenses, so it's not tied to
AEAT box numbers.
"""
from __future__ import annotations

import csv
import io
from calendar import monthrange

import db
from categories import label as category_label

QUARTER_MONTHS = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}


def generate(year: int, quarter: int | None = None) -> dict:
    if quarter:
        months = QUARTER_MONTHS[quarter]
        start_date = f"{year}-{months[0]:02d}-01"
        end_date = f"{year}-{months[-1]:02d}-{monthrange(year, months[-1])[1]:02d}"
        periodo = f"{quarter}T/{year}"
    else:
        start_date, end_date, periodo = f"{year}-01-01", f"{year}-12-31", str(year)

    bank_income = db.get_bank_income_for_period(start_date, end_date)
    cash_income = db.get_cash_income_total_for_period(start_date, end_date)
    total_income = round(bank_income + cash_income, 2)

    invoices = db.get_invoices_for_period(start_date, end_date)
    by_category: dict[str, float] = {}
    for inv in invoices:
        cat = inv.get("category") or "sin_clasificar"
        by_category[cat] = by_category.get(cat, 0.0) + (inv.get("net_amount") or 0.0)
    by_category = {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])}
    total_expenses = round(sum(by_category.values()), 2)

    net_result = round(total_income - total_expenses, 2)

    return {
        "year": year,
        "quarter": quarter,
        "periodo": periodo,
        "start_date": start_date,
        "end_date": end_date,
        "invoice_count": len(invoices),
        "bank_income": bank_income,
        "cash_income": cash_income,
        "total_income": total_income,
        "by_category": by_category,
        "by_category_labels": {k: category_label(k) for k in by_category},
        "total_expenses": total_expenses,
        "net_result": net_result,
    }


def as_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Cuenta de Perdidas y Ganancias", report.get("periodo", "")])
    w.writerow([])
    w.writerow(["INGRESOS"])
    w.writerow(["Ingresos bancarios (abonos)", f"{report['bank_income']:.2f}"])
    w.writerow(["Ingresos en efectivo (manual)", f"{report['cash_income']:.2f}"])
    w.writerow(["TOTAL INGRESOS", f"{report['total_income']:.2f}"])
    w.writerow([])
    w.writerow(["GASTOS"])
    for cat, amount in report["by_category"].items():
        w.writerow([report["by_category_labels"][cat], f"{amount:.2f}"])
    w.writerow(["TOTAL GASTOS", f"{report['total_expenses']:.2f}"])
    w.writerow([])
    w.writerow(["RESULTADO NETO", f"{report['net_result']:.2f}"])
    return out.getvalue()
