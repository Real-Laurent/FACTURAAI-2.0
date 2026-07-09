"""
El Espejo Hostelero S.A.  —  food distributor (EHOSA)
CIF A-00929787

Invoice layout (OCR text from scanned PDF):
  Header:   "N° FACTURA  FECHA  PAG"
            "01057218  24-03-26  1"
  Totals:   "BASE  %Iva  Imp. Iva  %Rec  Imp. Rec"
            "26,87  4,00%  1,07"
            "41,76  10,00%  4,18"
  Total:    "73,88  euros"

Multi-rate invoices (4%, 10%, 21%) are handled via vat_breakdown.
OCR sometimes misreads day digits (e.g. 24 → 74); fallback to delivery date.
"""

import re
from extractors.base import BaseExtractor, ExtractionResult, VatLine
from extractors.helpers import parse_amount, parse_date


class EhosaExtractor(BaseExtractor):
    supplier_name = "EHOSA"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'ESPEJO\s+HOSTELERO|EHOSA|ehosa\.es', text, re.IGNORECASE))

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = "El Espejo Hostelero S.A."

        # Invoice number + date: "01057218  24-03-26  1"
        # If OCR produces an impossible day (>31), leave date=None so the
        # invoice is routed to manual_review rather than silently wrong.
        m = re.search(r'(\d{6,10})\s+(\d{2}-\d{2}-\d{2})', text)
        if m:
            r.invoice_number = m.group(1)
            raw_date = m.group(2)
            if int(raw_date[:2]) <= 31:
                r.date = parse_date(raw_date)

        # VAT breakdown: one line per rate band
        # "26,87  4,00%  1,07"  "41,76  10,00%  4,18"
        vat_rows = re.findall(
            r'([\d,\.]+)\s+([\d,\.]+)%\s+([\d,\.]+)',
            text
        )
        lines = []
        for base_s, rate_s, vat_s in vat_rows:
            base = parse_amount(base_s)
            rate_pct = parse_amount(rate_s)
            vat = parse_amount(vat_s)
            if base is not None and rate_pct is not None and vat is not None:
                lines.append(VatLine(rate=round(rate_pct / 100, 4), base=base, amount=vat))

        if lines:
            if len(lines) == 1:
                r.net_amount = lines[0].base
                r.vat_rate   = lines[0].rate
                r.vat_amount = lines[0].amount
            else:
                r.vat_breakdown = lines
                r.net_amount = round(sum(l.base for l in lines), 2)
                r.vat_amount = round(sum(l.amount for l in lines), 2)

        # Total: "73,88 euros"
        m = re.search(r'([\d,\.]+)\s+euros', text, re.IGNORECASE)
        if m:
            r.total_amount = parse_amount(m.group(1))

        if r.total_amount is None and r.net_amount and r.vat_amount:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        r.currency = "EUR"
        return r
