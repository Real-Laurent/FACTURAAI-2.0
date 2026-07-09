"""
Mercadona S.A.  —  supermarket chain
CIF A-46103834

Invoice layout (pdfplumber text stream — multi-page, summary on LAST page):
  "Nº Factura:  A-V2026-0000123456"
  "Fecha Factura:  31/05/2026"

  DETALLE (€) table (last page):
    "4%  47,56  1,89  49,45"
    "10%  209,52  20,96  230,48"
    "21%  30,05  6,30  36,35"

  Total:  "Total Factura  316,28€"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult, VatLine
from extractors.helpers import parse_amount, parse_date


class MercadonaExtractor(BaseExtractor):
    supplier_name = "Mercadona"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'MERCADONA|A-?46103834', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "Mercadona S.A."

        # Invoice number: "Nº Factura:  A-V2026-0000123456"
        m = re.search(r'N[°º]\s*Factura:\s*(A-V[\d-]+)', text, re.IGNORECASE)
        if m:
            r.invoice_number = m.group(1)

        # Date: "Fecha Factura:  31/05/2026"
        m = re.search(r'Fecha\s+Factura:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if m:
            r.date = parse_date(m.group(1))

        # DETALLE summary table — only on the last page, after the "DETALLE" header.
        # Individual ticket line-items earlier in the doc use the same "N% amount"
        # format, and \s+ crosses newlines, so we must scope to the summary section.
        # Columns: rate%  Base Imponible  Cuota IVA  Total
        detalle_pos = text.rfind('DETALLE')
        summary = text[detalle_pos:] if detalle_pos >= 0 else text
        breakdown = []
        for m in re.finditer(
            r'(\d+)%\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)',
            summary
        ):
            rate = float(m.group(1)) / 100
            base = parse_amount(m.group(2))
            amount = parse_amount(m.group(3))
            if base is not None and amount is not None:
                breakdown.append(VatLine(rate=rate, base=base, amount=amount))

        if breakdown:
            r.vat_breakdown = breakdown
            r.vat_rate = None
            r.net_amount = round(sum(l.base for l in breakdown), 2)
            r.vat_amount = round(sum(l.amount for l in breakdown), 2)

        # Total: "Total Factura  316,28€"
        m = re.search(r'Total\s+Factura\s+([\d,\.]+)€', text, re.IGNORECASE)
        if m:
            r.total_amount = parse_amount(m.group(1))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
