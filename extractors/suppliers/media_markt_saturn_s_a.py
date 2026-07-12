"""
MEDIA MARKT SATURN S.A.  —  electronics retailer
NIF ESA82037292

Letterhead / issuer identified by the footer block:
  "MEDIA MARKT SATURN S.A."
  "NIF: ESA82037292"
(The header shows "MEDIA MARKT ONLINE"; the customer box "Datos de cliente"
carries the client's data and must be ignored.)

Invoice layout (pdfplumber text stream):
  "Número de factura" ... "E601-A001260001251159 318112608"
  "Fecha de factura" ... "02.07.2026"

  VAT summary row:
    "21,00% 271,90 EUR 57,10 EUR 329,00 EUR ..."
    (rate%  Base Imponible  Cuota IVA  Total)
"""

import re
from extractors.base import BaseExtractor, ExtractionResult, VatLine
from extractors.helpers import parse_amount, parse_date


class MediaMarktExtractor(BaseExtractor):
    supplier_name = "MEDIA MARKT SATURN S.A."

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'MEDIA\s*MARKT|ESA82037292|A-?82037292', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "MEDIA MARKT SATURN S.A."

        try:
            # Invoice number: first E601-... code appearing AFTER "Número de factura"
            # (the earlier E601 code belongs to the "Referencia" field).
            m = re.search(
                r'N[uú]mero\s+de\s+factura.*?(E\d+-[A-Z0-9]+)',
                text, re.IGNORECASE | re.DOTALL
            )
            if m:
                r.invoice_number = m.group(1)
        except Exception:
            r.invoice_number = None

        try:
            # Date: "Fecha de factura" ... "02.07.2026"
            m = re.search(
                r'Fecha\s+de\s+factura.*?(\d{2}\.\d{2}\.\d{4})',
                text, re.IGNORECASE | re.DOTALL
            )
            if m:
                r.date = parse_date(m.group(1))
        except Exception:
            r.date = None

        try:
            # VAT summary row: "21,00% 271,90 EUR 57,10 EUR 329,00 EUR"
            breakdown = []
            for m in re.finditer(
                r'(\d{1,2},\d{2})%\s+([\d.,]+)\s+EUR\s+([\d.,]+)\s+EUR\s+([\d.,]+)\s+EUR',
                text
            ):
                rate = parse_amount(m.group(1))
                base = parse_amount(m.group(2))
                amount = parse_amount(m.group(3))
                if rate is not None and base is not None and amount is not None:
                    breakdown.append(VatLine(rate=rate / 100, base=base, amount=amount))

            if breakdown:
                r.net_amount = round(sum(l.base for l in breakdown), 2)
                r.vat_amount = round(sum(l.amount for l in breakdown), 2)
                if len(breakdown) == 1:
                    r.vat_rate = breakdown[0].rate
                    r.vat_breakdown = []
                else:
                    r.vat_rate = None
                    r.vat_breakdown = breakdown
        except Exception:
            pass

        try:
            # Total: header row ends with "Total 329,00 EUR"
            m = re.search(r'Total\s+Total\s+([\d.,]+)\s+EUR', text, re.IGNORECASE)
            if m:
                r.total_amount = parse_amount(m.group(1))
        except Exception:
            r.total_amount = None

        if r.total_amount is None and r.net_amount is not None and r.vat_amount is not None:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
