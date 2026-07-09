"""
Text extraction from PDFs.
Tries pdfplumber first; if the result is too short (scanned image PDF),
falls back to ocrmypdf + pytesseract.

Handles PDFs that were downloaded with HTTP response headers prepended
(e.g. 'date: ... content-type: application/pdf\n\n%PDF-...'). The
headers are stripped transparently before any processing.
"""

import io
import logging
import os
import subprocess
import tempfile

import pdfplumber

from config.loader import get_config

log = logging.getLogger(__name__)


def _load_pdf_bytes(pdf_path: str) -> bytes:
    """Read a file and strip any HTTP response headers prepended before %PDF-."""
    with open(pdf_path, "rb") as f:
        data = f.read()
    idx = data.find(b"%PDF-")
    if idx > 0:
        log.debug("Stripped %d-byte HTTP header from %s", idx, pdf_path)
        data = data[idx:]
    return data


def extract_text(pdf_path: str) -> str:
    """Return best-effort text from a PDF file."""
    cfg = get_config().get("processing", {})
    min_chars = cfg.get("pdf_text_min_chars", 50)

    text = _extract_digital(pdf_path)
    if len(text.strip()) >= min_chars:
        log.debug("Digital extraction OK for %s (%d chars)", pdf_path, len(text))
        return text

    if cfg.get("ocr_enabled", True):
        log.info("Falling back to OCR for %s", pdf_path)
        text = _extract_ocr(pdf_path)

    return text


def _extract_digital(pdf_path: str) -> str:
    pages = []
    try:
        data = _load_pdf_bytes(pdf_path)
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
    except Exception as e:
        log.warning("pdfplumber failed on %s: %s", pdf_path, e)
    return "\n".join(pages)


def _ocr_env() -> dict:
    """Build subprocess env with tesseract on PATH and TESSDATA_PREFIX set."""
    cfg = get_config().get("processing", {})
    env = os.environ.copy()

    tess_dir = cfg.get("ocr_tesseract_dir", "")
    if tess_dir and os.path.isdir(tess_dir):
        env["PATH"] = tess_dir + os.pathsep + env.get("PATH", "")

    tessdata = cfg.get("ocr_tessdata_prefix", "")
    if tessdata and os.path.isdir(tessdata):
        env["TESSDATA_PREFIX"] = tessdata
    elif tess_dir:
        candidate = os.path.join(tess_dir, "tessdata")
        if os.path.isdir(candidate):
            env["TESSDATA_PREFIX"] = candidate

    return env


def _extract_ocr(pdf_path: str) -> str:
    cfg = get_config().get("processing", {})
    lang = cfg.get("ocr_language", "spa+eng")

    # Write stripped bytes to a clean temp file (ocrmypdf needs a real path)
    data = _load_pdf_bytes(pdf_path)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as clean_tmp:
        clean_tmp.write(data)
        clean_path = clean_tmp.name

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out_tmp:
        ocr_output = out_tmp.name

    try:
        result = subprocess.run(
            ["ocrmypdf", "--language", lang, "--force-ocr",
             "--output-type", "pdf", clean_path, ocr_output],
            capture_output=True, text=True, timeout=180,
            env=_ocr_env(),
        )
        if result.returncode != 0:
            log.warning("ocrmypdf error on %s: %s", pdf_path, result.stderr[-500:])
            return ""
        return _extract_digital(ocr_output)
    except FileNotFoundError:
        log.error("ocrmypdf not found — install with: pip install ocrmypdf")
        return ""
    except subprocess.TimeoutExpired:
        log.error("OCR timed out for %s", pdf_path)
        return ""
    finally:
        for p in (clean_path, ocr_output):
            if os.path.exists(p):
                os.unlink(p)
