"""
Core processing pipeline: given a PDF path, classifies, extracts (via an
existing extractor or a freshly AI-generated one), reviews plausibility,
validates, renames, archives, and writes to DB.

Pipeline order: dedup -> extract text -> classify/detect -> (existing
extractor | new-supplier codegen | reject) -> AI plausibility review ->
sanity checks (VAT/spike) -> determine needs_review -> archive/review.
"""

import logging
import os
import re
import shutil
from datetime import datetime

import ai_client
import codegen
import db
from categories import auto_category
from classifier import DetectionOutcome, detect
from config.loader import get_config
from extractors.base import ExtractionResult
from extractors.registry import select_extractor
from onedrive_client import upload_invoice
from pdf_extractor import extract_text
from sanity import check_spike, check_vat

log = logging.getLogger(__name__)


class ProcessingResult:
    def __init__(self):
        self.success = False
        self.skipped = False
        self.failed = False
        self.rejected = False
        self.path = None
        self.reason = ""


def _ai_enabled() -> bool:
    return bool(get_config().get("ai", {}).get("enabled", True))


def process_pdf(pdf_path: str, source: str = "scan") -> ProcessingResult:
    result = ProcessingResult()
    result.path = pdf_path

    # --- deduplication ---
    try:
        file_hash = db.hash_file(pdf_path)
    except Exception as e:
        log.error("Cannot hash %s: %s", pdf_path, e)
        result.failed = True
        result.reason = f"hash error: {e}"
        return result

    if db.is_duplicate(file_hash):
        log.info("Duplicate, skipping: %s", pdf_path)
        result.skipped = True
        result.reason = "duplicate"
        return result

    # --- text extraction ---
    try:
        text = extract_text(pdf_path)
    except Exception as e:
        log.error("Text extraction failed for %s: %s", pdf_path, e)
        result.failed = True
        result.reason = f"extraction error: {e}"
        return result

    # --- classify: known supplier / new supplier / not a factura ---
    detection = detect(text)
    cfg = get_config()

    if detection.outcome == DetectionOutcome.NOT_FACTURA:
        return _reject(pdf_path, file_hash, source, detection.reasoning, result)

    extraction, extractor_name, extractor_pending, detect_reason = _extract(text, detection, cfg)

    if extraction.not_invoice:
        reason = f"{extractor_name}: recognised as a non-invoice document (not_invoice)"
        return _reject(pdf_path, file_hash, source, reason, result)

    threshold = cfg.get("processing", {}).get("confidence_threshold", 0.6)
    needs_review = extraction.confidence < threshold
    review_reasons = [detect_reason] if detect_reason else []

    # --- AI plausibility review (every real extraction, not the fallback cases) ---
    ai_flag = False
    ai_issue = None
    if _ai_enabled() and extractor_name != "none" and not detect_reason:
        try:
            plaus = ai_client.review_plausibility(text, extraction.to_dict())
            if not plaus.plausible:
                ai_flag = True
                ai_issue = plaus.issue
                review_reasons.append(f"plausibility: {plaus.issue}")
        except Exception as e:
            log.warning("review_plausibility failed for %s: %s", pdf_path, e)

    # --- sanity checks ---
    vat_flag = False
    spike_flag = False
    if extraction.net_amount and extraction.vat_amount:
        vat_flag = not check_vat(
            extraction.net_amount,
            extraction.vat_amount,
            extraction.vat_breakdown_json(),
        )

    if extraction.total_amount and extraction.date:
        try:
            dt = datetime.strptime(extraction.date[:10], "%Y-%m-%d")
            spike_flag = check_spike(extraction.total_amount, dt.year, dt.month)
        except (ValueError, TypeError):
            pass

    if vat_flag or spike_flag or ai_flag or extractor_pending:
        needs_review = True

    # --- determine destination ---
    if needs_review:
        dest_dir = cfg["paths"]["manual_review"]
    else:
        dest_dir = _output_dir(extraction.date)

    os.makedirs(dest_dir, exist_ok=True)
    new_name = _build_filename(extraction)
    dest_path = _safe_dest(dest_dir, new_name)

    # --- move file ---
    try:
        shutil.move(pdf_path, dest_path)
        log.info("Moved %s -> %s", pdf_path, dest_path)
    except Exception as e:
        log.error("Cannot move %s to %s: %s", pdf_path, dest_path, e)
        result.failed = True
        result.reason = f"move error: {e}"
        return result

    if not needs_review:
        try:
            upload_invoice(dest_path, extraction.date)
        except Exception as e:
            log.warning("OneDrive upload failed for %s (kept locally): %s", dest_path, e)

    # --- write DB record ---
    record = extraction.to_dict()
    record.update({
        "file_path":         dest_path,
        "source":            source,
        "needs_review":      int(needs_review),
        "vat_flag":          int(vat_flag),
        "spike_flag":        int(spike_flag),
        "ai_flag":           int(ai_flag),
        "ai_issue":          ai_issue,
        "extractor_pending": int(extractor_pending),
        "hash":              file_hash,
        "category":          auto_category(extraction.supplier),
    })
    try:
        db.insert_invoice(record)
    except Exception as e:
        log.error("DB insert failed for %s: %s", dest_path, e)
        result.failed = True
        result.reason = f"db error: {e}"
        return result

    result.success = True
    result.reason = "; ".join(review_reasons)
    return result


def _extract(text: str, detection, cfg: dict):
    """Return (ExtractionResult, extractor_name, extractor_pending, reason)."""
    if detection.outcome == DetectionOutcome.KNOWN_SUPPLIER:
        extraction = detection.extractor.safe_extract(text)
        return extraction, detection.extractor.supplier_name, False, None

    if detection.outcome == DetectionOutcome.NEW_SUPPLIER:
        outcome = codegen.generate_and_test_extractor(text, supplier_hint=detection.supplier_hint)
        if outcome.success:
            extractor = select_extractor(text)
            if extractor is not None:
                extraction = extractor.safe_extract(text)
                auto_trust = bool(cfg.get("ai", {}).get("auto_trust_new_extractors", False))
                reason = None if auto_trust else f"new extractor generated for {extractor.supplier_name} — please confirm"
                return extraction, extractor.supplier_name, not auto_trust, reason
            # Self-test passed but the promoted module still doesn't match its own
            # sample text (shouldn't happen, but don't crash the pipeline over it).
            return (
                ExtractionResult(confidence=0.0), "none", True,
                f"extractor promoted for {outcome.supplier_name} but did not match on re-check",
            )
        return ExtractionResult(confidence=0.0), "none", True, outcome.reason

    if detection.outcome == DetectionOutcome.CLASSIFICATION_FAILED:
        return ExtractionResult(confidence=0.0), "none", False, detection.reasoning

    # UNVERIFIED — ai.enabled is false; behave like v1 with no matching extractor
    return ExtractionResult(confidence=0.0), "none", False, None


def _reject(pdf_path: str, file_hash: str, source: str, reason: str, result: ProcessingResult) -> ProcessingResult:
    dest_dir = _output_dir(datetime.now().strftime("%Y-%m-%d"), base_key="rejected")
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = _safe_dest(dest_dir, os.path.basename(pdf_path))
    try:
        shutil.move(pdf_path, dest_path)
    except Exception as e:
        log.error("Cannot move rejected file %s to %s: %s", pdf_path, dest_path, e)
        result.failed = True
        result.reason = f"move error: {e}"
        return result

    record = {
        "file_path": dest_path,
        "source": source,
        "confidence": 0.0,
        "needs_review": 0,
        "vat_flag": 0,
        "spike_flag": 0,
        "ai_flag": 0,
        "rejected": 1,
        "reject_reason": reason,
        "extractor_pending": 0,
        "hash": file_hash,
        "currency": "EUR",
    }
    try:
        db.insert_invoice(record)
    except Exception as e:
        log.error("DB insert failed for rejected %s: %s", dest_path, e)
        result.failed = True
        result.reason = f"db error: {e}"
        return result

    log.info("Rejected (not a factura): %s — %s", dest_path, reason)
    result.rejected = True
    result.reason = reason
    return result


def _output_dir(date_str: str, base_key: str = "output") -> str:
    cfg = get_config()
    base = cfg["paths"][base_key]
    try:
        dt = datetime.strptime((date_str or "")[:10], "%Y-%m-%d")
        return os.path.join(base, f"{dt.year:04d}", f"{dt.month:02d}")
    except (ValueError, TypeError):
        return os.path.join(base, "unknown")


def _build_filename(extraction) -> str:
    company = _safe_name(extraction.supplier or "Unknown")[:50]
    date = (extraction.date or "0000-00-00")[:10]
    amount = f"{extraction.total_amount:.2f}" if extraction.total_amount else "0.00"
    return f"{company} {date} {amount}.pdf"


def _safe_name(s: str) -> str:
    """Strip characters illegal in Windows/macOS filenames; preserve spaces and accents."""
    return re.sub(r'[\\/:*?"<>|]', "", str(s)).strip()


def _safe_dest(directory: str, filename: str) -> str:
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"
