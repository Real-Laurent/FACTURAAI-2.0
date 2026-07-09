"""
Modelo 100 — annual business-activity net income summary, feeding into Renta.

This is explicitly NOT a full Modelo 100 calculator: a real annual personal
income tax return needs progressive IRPF brackets, personal/family minimums,
and any other income categories (employment, capital gains, other
activities) — none of which an invoice-processing tool can know. What this
gives you is the one number a bar's economic activity actually contributes
to that return: net business income for the year (ingresos - gastos
deducibles), computed the same way Modelo 130 computes it quarterly. Feed
this figure into the "Rendimientos de actividades economicas" section of
your real Modelo 100 filing (or hand it to a gestor).

Mirrors modelo390.py's relationship to modelo303.py: annualizes the
quarterly calculation core (here, modelo130's cumulative breakdown for Q4,
which already spans 1 Jan - 31 Dec) rather than reimplementing it.
"""
from __future__ import annotations

import csv
import io

from reports.modelo130 import _cumulative_breakdown


def generate(year: int) -> dict:
    breakdown = _cumulative_breakdown(year, 4)  # Q4 cumulative == full calendar year
    return {
        "year": year,
        "periodo": str(year),
        **breakdown,
        "income_is_stub": breakdown["ingresos"] == 0.0,
    }


def as_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Modelo 100 — Resumen Anual Rendimiento Actividad Economica", report.get("periodo", "")])
    w.writerow(["(No sustituye a la declaracion completa de la Renta — solo la actividad economica)"])
    if report.get("income_is_stub"):
        w.writerow(["AVISO", "Ingresos = 0.00 — fuente de ingresos aun no configurada; borrador solo de gastos"])
    w.writerow([])
    w.writerow(["Concepto", "Importe (€)"])
    w.writerow(["Ingresos del ejercicio", f"{report['ingresos']:.2f}"])
    w.writerow(["Gastos deducibles del ejercicio", f"{report['gastos']:.2f}"])
    w.writerow(["Rendimiento neto de la actividad economica", f"{report['rendimiento_neto']:.2f}"])
    return out.getvalue()
