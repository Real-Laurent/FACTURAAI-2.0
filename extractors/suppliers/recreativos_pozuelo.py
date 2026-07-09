"""
Recreativos Pozuelo S.L.  —  amusement / slot machine operator
CIF B81308439

Multi-page PDF — each page is a separate establishment invoice.
Only the FIRST matching page is extracted here.

Actual PDF layout (pdfplumber text, one page per invoice):
  "Factura POZH27557/12091/2025/12"
  "Fecha emisión 02/12/2025"
  table header: "Concepto Servicio %IVA IVA Establecimiento"
  data row:     "RECAUDACIÓN MÁQUINAS SEGÚN CONTRATO 141,16 € 21,00 29,64 € 170,80 €"
  summary row:  "Total importe 141,16 € 29,64 € 170,80 €"

Note: "IVA" is a column header, NOT followed by an amount — the VAT value
sits after the rate (21,00) on the RECAUDACIÓN data row.
"""

import re
from extractors.base import BaseExtractor, ExtractionResult
from extractors.helpers import parse_amount, parse_date


class RecreativosPozueloExtractor(BaseExtractor):
    supplier_name = "Recreativos Pozuelo"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'RECREATIVOS\s+POZUELO|B81308439|POZH\d+', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "Recreativos Pozuelo S.L."
        r.vat_rate = 0.21

        # Invoice number — first occurrence
        m = re.search(r'Factura\s+(POZH[\w/]+)', text, re.IGNORECASE)
        if m:
            r.invoice_number = m.group(1)

        # Date — "Fecha emisión 02/12/2025"
        m = re.search(r'Fecha\s+emisi[oó]n\s+(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if m:
            r.date = parse_date(m.group(1))

        # Data row: "{concept} {net} € {rate} {vat} € {total} €"
        # e.g. "RECAUDACIÓN MÁQUINAS SEGÚN CONTRATO 141,16 € 21,00 29,64 € 170,80 €"
        m = re.search(
            r'RECAUDACI[OÓ]N\s+M[AÁ]QUINAS\s+SEG[UÚ]N\s+CONTRATO\s+'
            r'([\d,\.]+)\s*€\s+'   # net
            r'[\d,]+\s+'           # %IVA rate — skip
            r'([\d,\.]+)\s*€\s+'  # IVA amount
            r'([\d,\.]+)\s*€',    # establishment total
            text, re.IGNORECASE
        )
        if m:
            r.net_amount = parse_amount(m.group(1))
            r.vat_amount = parse_amount(m.group(2))
            r.total_amount = parse_amount(m.group(3))
        else:
            # Fallback: net only (older or reformatted invoices)
            m2 = re.search(
                r'RECAUDACI[OÓ]N\s+M[AÁ]QUINAS\s+SEG[UÚ]N\s+CONTRATO\s+([\d,\.]+)\s*€',
                text, re.IGNORECASE
            )
            if m2:
                r.net_amount = parse_amount(m2.group(1))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
