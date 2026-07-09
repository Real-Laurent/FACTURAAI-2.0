"""
DIGI Spain Telecom S.L.U.  —  mobile / broadband operator
CIF A-84919760

Invoice layout (pdfplumber text stream):
  "Número:  DGFCJ2026001234"
  "Fecha de emisión  31/05/2026"
  "IMPORTE (base imponible)  45,83 €"
  "IMPUESTOS (21.00% IVA)  9,62 €"
  "TOTAL FACTURA (imp. incl.)  55,45 €"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult
from extractors.helpers import parse_amount, parse_date


class DigiExtractor(BaseExtractor):
    supplier_name = "DIGI Spain Telecom"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'DIGI\s+Spain\s+Telecom|A-?84919760|DGFCJ', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "DIGI Spain Telecom S.L.U."
        r.vat_rate = 0.21

        # Invoice number: "Número:  DGFCJ2026001234"
        m = re.search(r'N[uú]mero:\s+(DGFCJ[\w]+)', text, re.IGNORECASE)
        if m:
            r.invoice_number = m.group(1)

        # Date: "Fecha de emisión  31/05/2026"
        m = re.search(r'Fecha\s+de\s+emisi[oó]n\s+(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if m:
            r.date = parse_date(m.group(1))

        # Net (base imponible): "IMPORTE (base imponible)  45,83 €"
        m = re.search(r'IMPORTE\s*\(base\s+imponible\)\s+([\d,\.]+)\s*€', text, re.IGNORECASE)
        if m:
            r.net_amount = parse_amount(m.group(1))

        # VAT amount: "IMPUESTOS (21.00% IVA)  9,62 €"
        m = re.search(r'IMPUESTOS\s*\(21[,\.]00%\s+IVA\)\s+([\d,\.]+)\s*€', text, re.IGNORECASE)
        if m:
            r.vat_amount = parse_amount(m.group(1))

        # Total: "TOTAL FACTURA (imp. incl.)  55,45 €"
        m = re.search(r'TOTAL\s+FACTURA\s*\(imp\.\s+incl\.\)\s+([\d,\.]+)\s*€', text, re.IGNORECASE)
        if m:
            r.total_amount = parse_amount(m.group(1))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
