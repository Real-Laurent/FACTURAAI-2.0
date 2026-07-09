"""
Voldistribucion Madrid S.A.  —  wine & beverage distributor
CIF A78061389

Invoice layout (pdfplumber text stream):
  Invoice:  "FACTURA Nº FP26-032308"
  Date:     "19 mayo 2026"  (Spanish month name, in the header info block)
  Totals table footer — two lines:
    Line 1: "{base}  {vat%}  {vat}  0  0,00"   e.g. "147,56  21  30,99  0  0,00"
    Line 2: "{CLA}  {vat}  {TOTAL}"             e.g. "2,00  30,99  178,55"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult
from extractors.helpers import parse_amount, parse_date, SPANISH_MONTHS


class VoldisExtractor(BaseExtractor):
    supplier_name = "Voldistribucion Madrid"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'VOLDISTRIBUCION|VOLDIS|A78061389', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "Voldistribucion Madrid S.A."

        # Invoice number: "FACTURA Nº FP26-032308"
        m = re.search(r'FACTURA\s+N[°º]\s+([A-Z]{1,3}\d{2}-\d+)', text, re.IGNORECASE)
        if m:
            r.invoice_number = m.group(1)

        # Date: Spanish month name — "19 mayo 2026"
        month_names = '|'.join(SPANISH_MONTHS.keys())
        m = re.search(
            rf'(\d{{1,2}})\s+({month_names})\s+(\d{{4}})',
            text, re.IGNORECASE
        )
        if m:
            month_num = SPANISH_MONTHS[m.group(2).lower()]
            r.date = f"{m.group(3)}-{month_num:02d}-{int(m.group(1)):02d}"

        # Totals span two lines:
        #   Line 1: "{base}  {vat%}  {vat}  0  0,00"
        #   Line 2: "{CLA}  {vat}  {TOTAL}"
        # Capture both lines together to avoid ambiguity with the repeated vat amount.
        m = re.search(
            r'([\d,\.]+)\s+(4|10|21)\s+([\d,\.]+)\s+0\s+0[,\.]00\s*\n\s*[\d,\.]+\s+[\d,\.]+\s+([\d,\.]+)',
            text
        )
        if m:
            r.net_amount   = parse_amount(m.group(1))
            r.vat_rate     = float(m.group(2)) / 100
            r.vat_amount   = parse_amount(m.group(3))
            r.total_amount = parse_amount(m.group(4))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
