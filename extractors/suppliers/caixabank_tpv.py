"""
CaixaBank TPV card payment slips  —  NOT supplier invoices.
Merchant IDs seen: 367616810, terminal 01308876.

These are card terminal receipts with no VAT breakdown.
Returning confidence=0 routes them to manual review without processing.
"""

import re
from extractors.base import BaseExtractor, ExtractionResult


class CaixaBankTpvExtractor(BaseExtractor):
    supplier_name = "CaixaBank TPV"

    def can_handle(self, text: str) -> bool:
        return bool(re.search(r'367616810|01308876', text))

    def extract(self, text: str) -> ExtractionResult:
        # TPV receipts are not invoices — force manual review
        return ExtractionResult(confidence=0.0)
