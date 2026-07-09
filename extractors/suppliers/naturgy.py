"""
Naturgy Iberia S.A.  —  gas & electricity utility
CIF A-67760876

Invoice layout (pdfplumber text stream):
  "N.º de factura:  FE2026001234"
  "Fecha de emisión  31/05/2026"
  "Total electricidad  210,45 €"
  "IVA (21%)  44,19 €"
  "Total a pagar  254,64 €"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult
from extractors.helpers import parse_amount, parse_date


class NaturgyExtractor(BaseExtractor):
    supplier_name = "Naturgy"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'Naturgy|A-?67760876', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "Naturgy Iberia S.A."
        r.vat_rate = 0.21

        # Invoice number: "N.º de factura:  FE2026001234"
        m = re.search(r'N\.?[°º]?\s*de\s+factura:\s*(FE\d+)', text, re.IGNORECASE)
        if m:
            r.invoice_number = m.group(1)

        # Date: "Fecha de emisión: 07/01/2026" (colon is present in real PDFs)
        m = re.search(r'Fecha\s+de\s+emisi[oó]n:?\s+(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if m:
            r.date = parse_date(m.group(1))

        # Net (base imponible): "Total electricidad  210,45 €"
        m = re.search(r'Total\s+electricidad\s+([\d,\.]+)\s*€', text, re.IGNORECASE)
        if m:
            r.net_amount = parse_amount(m.group(1))

        # VAT amount — actual layout: "IVA (21%)  385,77 € x 21%  81,01 €"
        # The first number is the base (repeated), the second is the VAT amount.
        m = re.search(r'IVA\s*\(21%\)\s+[\d,\.]+\s*€\s*x\s*21%\s+([\d,\.]+)\s*€', text, re.IGNORECASE)
        if not m:
            # Fallback for simpler layout without the "x 21%" repetition
            m = re.search(r'IVA\s*\(21%\)\s+([\d,\.]+)\s*€', text, re.IGNORECASE)
        if m:
            r.vat_amount = parse_amount(m.group(1))

        # Total: "Total a pagar  254,64 €"
        m = re.search(r'Total\s+a\s+pagar\s+([\d,\.]+)\s*€', text, re.IGNORECASE)
        if m:
            r.total_amount = parse_amount(m.group(1))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
