"""
Qualianza S. Int Dist, SLU  —  food products distributor (Pascual, Bezoya, etc.)
CIF B09547167

Invoice layout (pdfplumber text stream):
  "Factura Nº\n2206747395"
  "Fecha Factura\n08.06.2026"

  Per-rate VAT table (multiple rows, one per rate):
    "B.Imponible  % IVA  % RE  Cuota IVA  Cuota R.E."
    "64,22  4,00  2,57"       ← 4% band
    "10,03  10,00  1,00"      ← 10% band
    "17,30  21,00  3,63"      ← 21% band
    "91,55  TOTALES  7,20"    ← sum row

  Footer:
    "Importe(sin I.V.A.)  91,55"
    "Importe I.V.A.  7,20"
    "IMPORTE TOTAL (EUR)  98,75"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult, VatLine
from extractors.helpers import parse_amount, parse_date


class QualianzaExtractor(BaseExtractor):
    supplier_name = "Qualianza"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'QUALIANZA|B09547167', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "Qualianza S. Int Dist, SLU"

        # Header row: "Factura Nº  Fecha Factura  Forma de Pago ..."
        # Data row  : "3601466799  14.01.2026  ..."
        # Capture both fields from the single data row that follows the header.
        m = re.search(
            r'Factura\s+N[°º][^\n]*\n\s*(\d{8,12})\s+(\d{2}\.\d{2}\.\d{4})',
            text
        )
        if m:
            r.invoice_number = m.group(1)
            r.date = parse_date(m.group(2))

        # Per-rate VAT lines: "base  rate  vat_amount"
        # Rates seen: 4,00 / 10,00 / 21,00
        # Pattern stops before the TOTALES line
        breakdown = []
        for m in re.finditer(
            r'([\d,\.]+)\s+(4[,\.]00|10[,\.]00|21[,\.]00)\s+([\d,\.]+)',
            text
        ):
            base   = parse_amount(m.group(1))
            rate   = parse_amount(m.group(2))
            amount = parse_amount(m.group(3))
            if base and rate and amount:
                breakdown.append(VatLine(rate=rate / 100, base=base, amount=amount))

        if breakdown:
            r.vat_breakdown = breakdown
            r.vat_rate = None   # mixed — no single rate applies
            r.net_amount  = round(sum(l.base   for l in breakdown), 2)
            r.vat_amount  = round(sum(l.amount for l in breakdown), 2)

        # Totals from footer labels (override/confirm the sums above)
        m = re.search(r'Importe\s*\(sin\s+I\.V\.A\.\)\s*([\d,\.]+)', text)
        if m:
            r.net_amount = parse_amount(m.group(1))

        m = re.search(r'Importe\s+I\.V\.A\.\s*([\d,\.]+)', text)
        if m:
            r.vat_amount = parse_amount(m.group(1))

        m = re.search(r'IMPORTE TOTAL\s*\(?EUR\)?\s*([\d,\.]+)', text)
        if m:
            r.total_amount = parse_amount(m.group(1))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
