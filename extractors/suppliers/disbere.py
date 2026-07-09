"""
DISBERE, S.L.  —  beer & beverage distributor (Mahou)
NIF B80129083

Invoice layout (pdfplumber text stream):
  Header row:  "Nº Factura  Fecha  Cliente  CIF/DNI  Página  Forma de Pago"
  Data row:    "8218  31/12/25  014632  B10886893  1/1  CONTADO"
               (date may be DD/MM/YY or DD/MM/YYYY)

  Summary row: "804,51  804,51  21  168,95"  (Imp.Neto | B.Imponible | %IVA | Cuota IVA)
  Total:       "TOTAL FACTURA ............ 973,46"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult
from extractors.helpers import parse_amount, parse_date, find_amount


class DisberExtractor(BaseExtractor):
    supplier_name = "DISBERE"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'DISBERE', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "DISBERE, S.L."

        # Invoice number + date from the header data row.
        # Date may be DD/MM/YY (2-digit) or DD/MM/YYYY (4-digit).
        m = re.search(r'\b(\d{3,6})\s+(\d{2}/\d{2}/\d{2,4})\s+\d+\s+[A-Z]\d+', text)
        if m:
            r.invoice_number = m.group(1)
            r.date = parse_date(m.group(2))

        # Summary row: Imp.Neto  B.Imponible  %IVA  CuotaIVA
        # Require each number to start with a digit so a lone '.' in a product
        # name (e.g. "5L.") cannot anchor the match.
        m = re.search(
            r'\b(\d[\d,\.]*)\s+(\d[\d,\.]*)\s+(4|10|21)\s+(\d[\d,\.]*)\s*$',
            text, re.MULTILINE
        )
        if m:
            r.net_amount = parse_amount(m.group(2))   # B.Imponible
            r.vat_rate   = float(m.group(3)) / 100
            r.vat_amount = parse_amount(m.group(4))

        # Net alternative (dotted label)
        if r.net_amount is None:
            r.net_amount = find_amount(
                r'BASE\s+IMPONIBLE\s*\.+\s*([\d,\.]+)', text
            )

        # Grand total: "TOTAL FACTURA ............ 973,46"
        m = re.search(r'TOTAL\s+FACTURA\s*\.+\s*([\d,\.]+)', text, re.IGNORECASE)
        if m:
            r.total_amount = parse_amount(m.group(1))

        # Fallback: compute total
        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
