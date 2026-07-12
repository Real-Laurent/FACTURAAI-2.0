"""
Unidad Editorial S.A.  —  publisher of the newspaper 'EL MUNDO'
Issuer C.I.F.: A79102331  (registro mercantil de Madrid)

These are newspaper subscription invoices.  The customer's company name
(e.g. 'SPAIN STARWORLD TRADE SERVICE COMPANY SL', CIF B10886893) is shown
twice in the billed-to block at the top, but the actual ISSUER (emisor) is
Unidad Editorial, identified by the C.I.F. A79102331 in the mercantile
registry footer and by the 'EL MUNDO' concept header.

Invoice layout (pdfplumber text stream):
  "N\u00ba Factura: DS0260036073"
  "Fecha: 17/06/2026"
  ...
  "Base Imponible Porcentaje de Impuesto Importe IVA Total factura"
  "38,32 4 1,53 39,85 \u20ac"
"""

import re
from extractors.base import BaseExtractor, ExtractionResult
from extractors.helpers import parse_amount, parse_date


class UnidadEditorialExtractor(BaseExtractor):
    supplier_name = "Unidad Editorial S.A. (El Mundo)"

    def can_handle(self, text: str) -> bool:
        try:
            # Stable ISSUER identifier: the mercantile-registry C.I.F. of
            # Unidad Editorial, plus the 'EL MUNDO' publication concept.
            if re.search(r'A[\s.-]?79102331', text, re.IGNORECASE):
                return True
            return bool(re.search(r'EL\s+MUNDO', text) and
                        re.search(r'N[\u00ba\u00b0]\s*Factura:\s*DS\d', text, re.IGNORECASE))
        except Exception:
            return False

    def extract(self, text: str) -> ExtractionResult:
        r = ExtractionResult()
        r.supplier = self.supplier_name
        r.currency = "EUR"

        # Invoice number: "N\u00ba Factura: DS0260036073"
        try:
            m = re.search(r'N[\u00ba\u00b0]\s*Factura:\s*([A-Z0-9/]+)', text, re.IGNORECASE)
            if m:
                r.invoice_number = m.group(1).strip()
        except Exception:
            pass

        # Date: "Fecha: 17/06/2026"
        try:
            m = re.search(r'Fecha:\s*(\d{2}/\d{2}/\d{4})', text)
            if m:
                r.date = parse_date(m.group(1))
        except Exception:
            pass

        # VAT summary line (single rate), scoped after the table header:
        #   "Base Imponible Porcentaje de Impuesto Importe IVA Total factura"
        #   "38,32 4 1,53 39,85 \u20ac"
        try:
            hdr = re.search(r'Base\s+Imponible.*?Total\s+factura', text,
                            re.IGNORECASE | re.DOTALL)
            summary = text[hdr.end():] if hdr else text
            m = re.search(
                r'([\d.,]+)\s+(\d{1,2}(?:,\d+)?)\s+([\d.,]+)\s+([\d.,]+)\s*\u20ac',
                summary,
            )
            if m:
                base = parse_amount(m.group(1))
                rate = parse_amount(m.group(2))
                vat = parse_amount(m.group(3))
                total = parse_amount(m.group(4))
                if base is not None:
                    r.net_amount = base
                if vat is not None:
                    r.vat_amount = vat
                if rate is not None:
                    r.vat_rate = round(rate / 100, 4)
                if total is not None:
                    r.total_amount = total
        except Exception:
            pass

        # Fallback total: "Total factura ... 39,85 \u20ac"
        if r.total_amount is None:
            try:
                matches = re.findall(r'([\d.,]+)\s*\u20ac', text)
                if matches:
                    r.total_amount = parse_amount(matches[-1])
            except Exception:
                pass

        if r.total_amount is None and r.net_amount is not None and r.vat_amount is not None:
            r.total_amount = round(r.net_amount + r.vat_amount, 2)

        return r
