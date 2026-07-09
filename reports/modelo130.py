"""
Modelo 130 — quarterly IRPF pago fraccionado (estimacion directa simplificada) draft.

Computed from net business income (ingresos - gastos deducibles), cumulative
from the start of the calendar year through the end of the requested
quarter, matching AEAT's actual calculation: each quarter's payment is 20%
of year-to-date net income, minus payments already made in earlier quarters
of the same year (floored at zero — a quarter never asks for money back).

Income (ingresos, casilla 01) comes from db.get_income_for_period(), which
is currently a stub returning 0.0 — FacturaAI has only ever tracked
expenses. Everything below the income line is correct and ready for when a
real income source is wired in; until then net income is <= 0 for any
supplier with expenses, so casilla 04 (and the final resultado) reports as
0.00 per the floor-at-zero rule, and this is clearly an expense-only draft.

This is a simplified version of the real form: retenciones (casilla 07) and
the irregular-income adjustment (casillas 05-06) are out of scope for an
invoice-processing tool and are not included.
"""
from __future__ import annotations

import csv
import io
from calendar import monthrange

import db

QUARTER_MONTHS = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}
PAGO_FRACCIONADO_RATE = 0.20


def _period_bounds(year: int, quarter: int) -> tuple[str, str]:
    end_month = QUARTER_MONTHS[quarter][-1]
    end_date = f"{year}-{end_month:02d}-{monthrange(year, end_month)[1]:02d}"
    return f"{year}-01-01", end_date


def _cumulative_breakdown(year: int, quarter: int) -> dict:
    start_date, end_date = _period_bounds(year, quarter)
    income = db.get_income_for_period(start_date, end_date)
    invoices = db.get_invoices_for_period(start_date, end_date)
    expenses = round(sum(inv.get("net_amount") or 0 for inv in invoices), 2)
    net_income = round(income - expenses, 2)
    casilla_04 = round(max(net_income, 0) * PAGO_FRACCIONADO_RATE, 2)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "invoice_count": len(invoices),
        "ingresos": round(income, 2),
        "gastos": expenses,
        "rendimiento_neto": net_income,
        "casilla_04": casilla_04,
    }


def _resultado_for_quarter(year: int, quarter: int) -> float:
    casilla_04 = _cumulative_breakdown(year, quarter)["casilla_04"]
    prior = round(sum(_resultado_for_quarter(year, q) for q in range(1, quarter)), 2)
    return round(max(casilla_04 - prior, 0), 2)


def generate(year: int, quarter: int) -> dict:
    breakdown = _cumulative_breakdown(year, quarter)
    prior_payments = round(sum(_resultado_for_quarter(year, q) for q in range(1, quarter)), 2)
    resultado = round(max(breakdown["casilla_04"] - prior_payments, 0), 2)

    return {
        "year": year,
        "quarter": quarter,
        "periodo": f"{quarter}T/{year}",
        **breakdown,
        "pagos_fraccionados_anteriores": prior_payments,
        "resultado": resultado,
        "income_is_stub": breakdown["ingresos"] == 0.0,
    }


def as_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Modelo 130 — Borrador Pago Fraccionado IRPF", report.get("periodo", "")])
    if report.get("income_is_stub"):
        w.writerow(["AVISO", "Ingresos = 0.00 — fuente de ingresos aun no configurada; borrador solo de gastos"])
    w.writerow([])
    w.writerow(["Casilla", "Concepto", "Importe (€)"])
    w.writerow(["01", "Ingresos (acumulado desde 1 enero)", f"{report['ingresos']:.2f}"])
    w.writerow(["02", "Gastos deducibles (acumulado desde 1 enero)", f"{report['gastos']:.2f}"])
    w.writerow(["03", "Rendimiento neto (01 - 02)", f"{report['rendimiento_neto']:.2f}"])
    w.writerow(["04", "20% s/ casilla 03", f"{report['casilla_04']:.2f}"])
    w.writerow(["16", "Pagos fraccionados de trimestres anteriores", f"{report['pagos_fraccionados_anteriores']:.2f}"])
    w.writerow(["18", "RESULTADO (a ingresar)", f"{report['resultado']:.2f}"])
    return out.getvalue()
