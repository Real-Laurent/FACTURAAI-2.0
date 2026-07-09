"""
Modelo 303 — quarterly IVA return draft (gastos/soportado only).
Income side (repercutido) is left empty until income invoices are available.
"""
from __future__ import annotations

import csv
import io
import json
from calendar import monthrange

import db

QUARTER_MONTHS = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}

# AEAT box numbers for IVA soportado by rate
RATE_BOXES = {4: ("28", "29"), 10: ("30", "31"), 21: ("32", "33")}


def generate(year: int, quarter: int) -> dict:
    months = QUARTER_MONTHS[quarter]
    start_date = f"{year}-{months[0]:02d}-01"
    last_m = months[-1]
    end_date = f"{year}-{last_m:02d}-{monthrange(year, last_m)[1]:02d}"
    invoices = db.get_invoices_for_period(start_date, end_date)
    return _compute(
        invoices,
        year=year,
        quarter=quarter,
        periodo=f"{quarter}T/{year}",
        start_date=start_date,
        end_date=end_date,
    )


def _compute(invoices: list[dict], **meta) -> dict:
    soportado: dict[int, dict] = {}  # rate_pct (int) → {base, cuota}

    for inv in invoices:
        if inv.get("vat_breakdown"):
            try:
                for line in json.loads(inv["vat_breakdown"]):
                    r = round(float(line["rate"]) * 100)
                    _acc(soportado, r, float(line.get("base", 0)), float(line.get("amount", 0)))
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        else:
            rate_val = inv.get("vat_rate")
            if rate_val is None:
                continue
            r = round(float(rate_val) * 100)
            _acc(soportado, r, float(inv.get("net_amount") or 0), float(inv.get("vat_amount") or 0))

    for r in soportado:
        soportado[r]["base"]  = round(soportado[r]["base"],  2)
        soportado[r]["cuota"] = round(soportado[r]["cuota"], 2)

    total_soportado      = round(sum(v["cuota"] for v in soportado.values()), 2)
    total_base_soportado = round(sum(v["base"]  for v in soportado.values()), 2)

    # Build ordered rows for display (4%, 10%, 21% then any other rates found)
    ordered_rates = sorted(soportado.keys())

    return {
        **meta,
        "invoice_count":          len(invoices),
        "iva_soportado":          {str(r): soportado[r] for r in ordered_rates},
        "total_base_soportado":   total_base_soportado,
        "total_soportado":        total_soportado,
        # Income side — to be filled when income invoices are available
        "iva_repercutido":        {},
        "total_repercutido":      0.0,
        # Casilla 46: positive = a pagar, negative = a compensar
        "resultado":              round(0.0 - total_soportado, 2),
        "rate_boxes":             RATE_BOXES,
    }


def _acc(d: dict, rate: int, base: float, cuota: float):
    if rate not in d:
        d[rate] = {"base": 0.0, "cuota": 0.0}
    d[rate]["base"]  += base
    d[rate]["cuota"] += cuota


def as_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Modelo 303 — Borrador IVA", report.get("periodo", "")])
    w.writerow([])
    w.writerow(["Sección", "Casilla", "Descripción", "Base Imponible (€)", "Cuota IVA (€)"])
    for rate_str, vals in report["iva_soportado"].items():
        boxes = RATE_BOXES.get(int(rate_str), ("—", "—"))
        w.writerow([
            "II — IVA Deducible (Soportado)",
            f"{boxes[0]}/{boxes[1]}",
            f"Tipo {rate_str}%",
            f"{vals['base']:.2f}",
            f"{vals['cuota']:.2f}",
        ])
    w.writerow([])
    w.writerow(["", "[45]", "TOTAL IVA DEDUCIBLE", f"{report['total_base_soportado']:.2f}", f"{report['total_soportado']:.2f}"])
    w.writerow(["", "[46]", "RESULTADO (a pagar / a compensar)", "", f"{report['resultado']:.2f}"])
    return out.getvalue()
