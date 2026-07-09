from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


EXPECTED_FIELDS = ("date", "supplier", "invoice_number", "net_amount", "vat_amount", "total_amount")


@dataclass
class VatLine:
    """One VAT rate band within an invoice (used for mixed-rate invoices)."""
    rate: float          # e.g. 0.21
    base: float          # taxable base for this rate
    amount: float        # VAT amount for this rate


@dataclass
class ExtractionResult:
    date: Optional[str] = None
    supplier: Optional[str] = None
    invoice_number: Optional[str] = None
    net_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    # vat_rate: single rate (0.21) for single-rate invoices; None for mixed
    vat_rate: Optional[float] = None
    # vat_breakdown: populated for mixed-rate invoices; empty list otherwise
    vat_breakdown: List[VatLine] = field(default_factory=list)
    total_amount: Optional[float] = None
    currency: str = "EUR"
    confidence: float = 0.0
    raw_fields: dict = field(default_factory=dict)

    def compute_confidence(self) -> float:
        extracted = sum(
            1 for f in EXPECTED_FIELDS if getattr(self, f) is not None
        )
        self.confidence = extracted / len(EXPECTED_FIELDS)
        return self.confidence

    def vat_breakdown_json(self) -> Optional[str]:
        if not self.vat_breakdown:
            return None
        return json.dumps([
            {"rate": l.rate, "base": l.base, "amount": l.amount}
            for l in self.vat_breakdown
        ])

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "supplier": self.supplier,
            "invoice_number": self.invoice_number,
            "net_amount": self.net_amount,
            "vat_amount": self.vat_amount,
            "vat_rate": self.vat_rate,
            "vat_breakdown": self.vat_breakdown_json(),
            "total_amount": self.total_amount,
            "currency": self.currency,
            "confidence": self.confidence,
        }


class BaseExtractor(ABC):
    """Abstract base for all supplier extractors."""

    # Human-readable name stored in DB
    supplier_name: str = "Unknown"

    @abstractmethod
    def can_handle(self, text: str) -> bool:
        """Return True if this extractor recognises the supplier in text."""

    @abstractmethod
    def extract(self, text: str) -> ExtractionResult:
        """Parse text and return a populated ExtractionResult."""

    def safe_extract(self, text: str) -> ExtractionResult:
        try:
            result = self.extract(text)
            result.compute_confidence()
            return result
        except Exception:
            return ExtractionResult(confidence=0.0)
