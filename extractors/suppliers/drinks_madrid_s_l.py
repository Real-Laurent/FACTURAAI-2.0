"""
Drinks Madrid S.L.  —  food & drinks wholesale distributor
CIF B58443821

The issuer (letterhead) is Drinks Madrid S.L.; the customer box
("RAZON SOCIAL / DATOS DE ENVIO") on the sample happens to be
SPAIN STARWORLD TRADE SERVICE COMPANY SL — that is the RECEPTOR, not
the supplier, so we key off the issuer identifiers only.

Invoice layout (pdfplumber text stream):
  "FACTURA : 2606A001278"
  "FECHA : 30/06/2026"
  "Nif. B58443821"

  VAT summary block (between the R.E. header and TOTALES):
    "30/06/2026 80.50 1.10 21.00 0.23"   -> base=1.10  rate=21%  vat=0.23
    "71.97 10.00 7.20"                   -> base=71.97 rate=10%  vat=7.20

  Totals line (after the TOTAL BRUTO ... header):
    "73.07 73.07 7.43 EUR 80.50"
    (TOTAL BRUTO / TOTAL NETO / TOTAL IVA + RE / TOTAL)

Note: this supplier prints numbers in English style (dot decimals);
parse_amount handles both conventions.
"""

import re
from extractors.base import BaseExtractor, ExtractionResult, VatLine
from extractors.helpers import parse_amount, parse_date


class DrinksMadridExtractor(BaseExtractor):
    supplier_name = "Drinks Madrid S.L."

    def can_handle(self, text: str) -> bool:
        try:
            return bool(re.search(r'Drinks\s+Madrid|B58443821', text, re.IGNORECASE))
        except Exception:
            return False

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = self.supplier_name
        r.currency = "EUR"

        # Invoice number: "FACTURA : 2606A001278"
        try:
            m = re.search(r'FACTURA\s*:\s*(\S+)', text, re.IGNORECASE)
            if m:
                r.invoice_number = m.group(1).strip()
        except Exception:
            r.invoice_number = None

        # Date: "FECHA : 30/06/2026"
        try:
            m = re.search(r'FECHA\s*:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
            if m:
                r.date = parse_date(m.group(1))
        except Exception:
            r.date = None

        # VAT breakdown — scope to the region between the R.E. header and TOTALES
        try:
            seg_start = text.find('R. E. R. E.')
            seg_end = text.find('TOTALES')
            if seg_start >= 0 and seg_end > seg_start:
                segment = text[seg_start:seg_end]
            else:
                segment = text

            breakdown = []
            for m in re.finditer(r'([\d.,]+)\s+(\d{1,2})\.00\s+([\d.,]+)', segment):
                base = parse_amount(m.group(1))
                rate = parse_amount(m.group(2))
                amount = parse_amount(m.group(3))
                if base is not None and rate is not None and amount is not None:
                    breakdown.append(VatLine(rate=rate / 100, base=base, amount=amount))

            if breakdown:
                r.vat_breakdown = breakdown
                r.vat_rate = None
        except Exception:
            r.vat_breakdown = []

        # Totals line: "73.07 73.07 7.43 EUR 80.50"
        try:
            m = re.search(
                r'TOTAL\s+BRUTO\s+TOTAL\s+NETO\s+TOTAL\s+IVA\s*\+\s*RE\s+TOTAL\s*\n\s*'
                r'([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+EUR\s+([\d.,]+)',
                text, re.IGNORECASE
            )
            if m:
                r.net_amount = parse_amount(m.group(2))
                r.vat_amount = parse_amount(m.group(3))
                r.total_amount = parse_amount(m.group(4))
        except Exception:
            pass

        # Fall back to breakdown sums if totals line was not captured
        try:
            if r.net_amount is None and r.vat_breakdown:
                r.net_amount = round(sum(l.base for l in r.vat_breakdown), 2)
            if r.vat_amount is None and r.vat_breakdown:
                r.vat_amount = round(sum(l.amount for l in r.vat_breakdown), 2)
            if r.total_amount is None and r.net_amount is not None and r.vat_amount is not None:
                r.total_amount = round(r.net_amount + r.vat_amount, 2)
        except Exception:
            pass

        return r
