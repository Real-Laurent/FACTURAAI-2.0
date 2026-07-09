"""
Sinages Consulting SL  —  monthly consulting/services invoice
CIF B87768594

Invoice layout (pdfplumber text stream):
  "FACTURA #F262184"
  "Fecha 30/05/2026"
  Line item:  "HONORARIO SL V  HONORARIO MENSUAL  148,76€  148,76€  21%  180,00€"
  Summary:
    "BASE IMPONIBLE  148,76€"
    "IVA 21%  31,24€"
    "TOTAL  180,00€"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult
from extractors.helpers import parse_amount, parse_date


class SinagesExtractor(BaseExtractor):
    supplier_name = "Sinages Consulting"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'SINAGES|B87768594', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "Sinages Consulting SL"

        # Invoice number: "FACTURA #F262184"
        m = re.search(r'FACTURA\s*#\s*([A-Z]\d+)', text, re.IGNORECASE)
        if m:
            r.invoice_number = m.group(1)

        # Date: "Fecha 30/05/2026"
        m = re.search(r'Fecha\s+(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if m:
            r.date = parse_date(m.group(1))

        # Net: "BASE IMPONIBLE  148,76€"
        m = re.search(r'BASE\s+IMPONIBLE\s+([\d,\.]+)\s*€?', text, re.IGNORECASE)
        if m:
            r.net_amount = parse_amount(m.group(1))

        # VAT rate + amount: "IVA 21%  31,24€"
        m = re.search(r'IVA\s+(\d+)%\s+([\d,\.]+)\s*€?', text, re.IGNORECASE)
        if m:
            r.vat_rate   = float(m.group(1)) / 100
            r.vat_amount = parse_amount(m.group(2))

        # Total: last "TOTAL  180,00€" (not the line-item total column header)
        for m in re.finditer(r'\bTOTAL\s+([\d,\.]+)\s*€?', text, re.IGNORECASE):
            r.total_amount = parse_amount(m.group(1))  # take the last match

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
