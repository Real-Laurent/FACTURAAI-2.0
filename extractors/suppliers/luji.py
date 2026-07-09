"""
Alimentación Luji, S.L.  —  egg supplier (huevosdelucas.com)
CIF B-86358827

Invoice layout (pdfplumber text stream):
  Header row:  "N.FACTURA  SU REFERENCIA  N.PROVEE.  FECHA  CLIENTE  N.I.F.  HOJA"
               "C/4.479                             31/05/26  11.037   B10886893  1"
  Totals row:  "DTO. %  BASE  I.V.A  REC.  CUOTA I.V.A  CUOTA REC.  TOTAL LÍQUIDO"
               "        173,08  4,00       6,92          180,00"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult
from extractors.helpers import parse_amount, parse_date


class LujiExtractor(BaseExtractor):
    supplier_name = "Alimentación Luji"

    def can_handle(self, text: str) -> bool:
        return bool(
            re.search(r'ALIMENTACI[OÓ]N\s+LUJI|huevosdelucas|B-?86358827', text, re.IGNORECASE)
        )

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "Alimentación Luji, S.L."

        # Invoice number: C/4.479 format
        m = re.search(r'\b(C/[\d\.]+)', text)
        if m:
            r.invoice_number = m.group(1)

        # Date: first DD/MM/YY after "FECHA" label, or the first standalone DD/MM/YY
        m = re.search(r'FECHA.*?(\d{2}/\d{2}/\d{2})', text, re.DOTALL)
        if not m:
            m = re.search(r'\b(\d{2}/\d{2}/\d{2})\b', text)
        if m:
            r.date = parse_date(m.group(1))

        # Totals row: "173,08  4,00  6,92  180,00"
        # After "BASE  I.V.A" header: columns are base, vat_rate, vat_amount, total
        m = re.search(
            r'BASE\s+I\.V\.A.*?\n\s*([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)',
            text, re.DOTALL
        )
        if m:
            r.net_amount   = parse_amount(m.group(1))
            r.vat_rate     = parse_amount(m.group(2))
            if r.vat_rate:
                r.vat_rate = r.vat_rate / 100
            r.vat_amount   = parse_amount(m.group(3))
            r.total_amount = parse_amount(m.group(4))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
