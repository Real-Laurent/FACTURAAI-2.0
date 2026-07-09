"""
Makro Distribucion S.A.  —  cash & carry wholesale
CIF A-28647451

PDFs from Makro use character-level spacing in the text stream
('M a k r o' instead of 'Makro'), so text is normalised with
collapse_spaced_chars() before any pattern matching.

Invoice layout after normalisation:
  "Factura0/0(019)0006/(2026)003256"
  "Fechadeventa:01/02/2026"

  VAT table (base and rate still space-joined, totals at line end are intact):
    "32,431=10,00% 3,24"   → base=32,43  rate=10%  vat=3,24
    "11,905=4,00% 0,48"    → base=11,90  rate=4%   vat=0,48

  Total (intact multi-char token at line end):
    "Totalapagar 48,05"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult, VatLine
from extractors.helpers import parse_amount, parse_date, collapse_spaced_chars


class MakroExtractor(BaseExtractor):
    supplier_name = "Makro"

    def can_handle(self, text: str) -> bool:
        norm = collapse_spaced_chars(text)
        return bool(re.search(r'Makro|A-28', norm, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        text = collapse_spaced_chars(text)
        r = ExtractionResult()
        r.supplier = "Makro Distribucion S.A."

        # Invoice number — embedded after "Factura" with no space (after normalisation)
        m = re.search(r'Factura\s*(0/0\(019\)\d+/\(2026\)\d+)', text, re.IGNORECASE)
        if m:
            r.invoice_number = m.group(1)

        # Date — "Fechadeventa:01/02/2026" after normalisation
        m = re.search(r'Fecha\s*de\s*venta:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if m:
            r.date = parse_date(m.group(1))

        # VAT table after normalisation: "32,431=10,00% 3,24"
        # The rate-code digit merges with the base amount, so we use backtracking:
        # ([\d,\.]+) greedily takes base+code, then \d= backtracks one digit for the code.
        breakdown = []
        for m in re.finditer(r'([\d,\.]+)\d=([\d,\.]+)%\s*([\d,\.]+)', text):
            base = parse_amount(m.group(1))
            rate = parse_amount(m.group(2))
            amount = parse_amount(m.group(3))
            if base is not None and rate is not None and amount is not None:
                breakdown.append(VatLine(rate=rate / 100, base=base, amount=amount))

        if breakdown:
            r.vat_breakdown = breakdown
            r.vat_rate = None
            r.net_amount = round(sum(l.base for l in breakdown), 2)
            r.vat_amount = round(sum(l.amount for l in breakdown), 2)

        # Total — "Totalapagar 48,05" after normalisation
        m = re.search(r'Total\s*a\s*pagar\s*([\d,\.]+)', text, re.IGNORECASE)
        if m:
            r.total_amount = parse_amount(m.group(1))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
