"""
Factura detection — the first AI-driven step in the pipeline.

For every invoice, decide one of:
  KNOWN_SUPPLIER        an existing extractor already recognises it (zero API calls)
  NEW_SUPPLIER          Claude judges it a real factura, but no extractor handles it yet
  NOT_FACTURA            Claude judges it isn't an invoice at all
  CLASSIFICATION_FAILED  the API call itself failed — route to manual_review, don't guess
  UNVERIFIED             ai.enabled is false — same fallback behaviour v1 had with no AI
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import ai_client
from config.loader import get_config
from extractors.base import BaseExtractor
from extractors.registry import select_extractor

log = logging.getLogger(__name__)


class DetectionOutcome(Enum):
    KNOWN_SUPPLIER = "known_supplier"
    NEW_SUPPLIER = "new_supplier"
    NOT_FACTURA = "not_factura"
    CLASSIFICATION_FAILED = "classification_failed"
    UNVERIFIED = "unverified"


@dataclass
class DetectionResult:
    outcome: DetectionOutcome
    extractor: Optional[BaseExtractor] = None
    supplier_hint: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.0


def _ai_enabled() -> bool:
    return bool(get_config().get("ai", {}).get("enabled", True))


def detect(text: str) -> DetectionResult:
    # Fast path: an existing supplier extractor already recognises this
    # invoice — skip the API call entirely. This keeps the common case
    # (a supplier FacturaAI has seen before) free and instant.
    extractor = select_extractor(text)
    if extractor is not None:
        return DetectionResult(
            outcome=DetectionOutcome.KNOWN_SUPPLIER,
            extractor=extractor,
            supplier_hint=extractor.supplier_name,
            reasoning="matched by existing extractor.can_handle()",
            confidence=1.0,
        )

    if not _ai_enabled():
        # AI disabled — fall back to v1's old behaviour: unmatched invoices
        # get a zero-confidence extraction and land in manual_review, with
        # no factura/non-factura judgement made.
        log.info("AI disabled; no extractor matched — routing to manual_review unverified")
        return DetectionResult(
            outcome=DetectionOutcome.UNVERIFIED,
            reasoning="ai.enabled is false; no existing extractor matched",
        )

    if not text.strip():
        log.warning("No text extracted (digital or OCR) — routing to manual_review")
        return DetectionResult(
            outcome=DetectionOutcome.CLASSIFICATION_FAILED,
            reasoning="no text could be extracted from the PDF (OCR unavailable or failed)",
        )

    try:
        result = ai_client.classify_invoice(text)
    except Exception as e:
        log.error("classify_invoice failed: %s", e)
        return DetectionResult(
            outcome=DetectionOutcome.CLASSIFICATION_FAILED,
            reasoning=f"classification API call failed: {e}",
        )

    if not result.is_factura:
        log.info(
            "Classified as NOT a factura (confidence=%.2f): %s",
            result.confidence, result.reasoning,
        )
        return DetectionResult(
            outcome=DetectionOutcome.NOT_FACTURA,
            supplier_hint=result.supplier_name,
            reasoning=result.reasoning,
            confidence=result.confidence,
        )

    log.info(
        "Classified as a NEW SUPPLIER factura (confidence=%.2f, supplier=%s): %s",
        result.confidence, result.supplier_name, result.reasoning,
    )
    return DetectionResult(
        outcome=DetectionOutcome.NEW_SUPPLIER,
        supplier_hint=result.supplier_name,
        reasoning=result.reasoning,
        confidence=result.confidence,
    )
