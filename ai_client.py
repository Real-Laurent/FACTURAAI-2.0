"""
Claude API wrapper for FacturaAI 2.0's three AI-driven steps:

  classify_invoice()    — is this text a factura, and from a known/new supplier?
  generate_extractor()  — write a new BaseExtractor subclass for a new supplier
  review_plausibility() — sanity-check extracted fields against the raw text

All three use structured outputs (output_config.format) so responses are
always valid, directly-parseable JSON — no markdown-fence scraping.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import anthropic

from config.loader import get_config

log = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None
_codegen_system_prompt: Optional[list] = None

EXTRACTORS_DIR = Path(__file__).parent / "extractors"

# Supplier files used as few-shot examples for codegen — chosen for variety:
# makro.py (spaced-char normalisation + mixed VAT rates), mercadona.py (a
# straightforward single-rate case), caixabank_tpv.py (a non-invoice
# financial document that deliberately reports confidence=0.0 — teaches the
# model what "not a factura" looks like at the extractor level too).
FEW_SHOT_SUPPLIERS = ["makro.py", "mercadona.py", "caixabank_tpv.py"]


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _ai_config() -> dict:
    return get_config().get("ai", {})


# ---------------------------------------------------------------------------
# classify_invoice
# ---------------------------------------------------------------------------

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "is_factura": {
            "type": "boolean",
            "description": "True if this text is a Spanish invoice/factura (or foreign equivalent), false for any other kind of document.",
        },
        "confidence": {"type": "number"},
        "supplier_name": {
            "type": ["string", "null"],
            "description": "Best-guess supplier/company name if is_factura is true, otherwise null.",
        },
        "reasoning": {"type": "string"},
    },
    "required": ["is_factura", "confidence", "supplier_name", "reasoning"],
    "additionalProperties": False,
}

CLASSIFY_SYSTEM = """You classify documents for a Spanish bar business's invoice-automation pipeline.
You will be given text extracted from a PDF (digitally or via OCR — expect occasional OCR noise).
Decide whether it is a factura (invoice) — a document billing the business for goods or services,
showing a supplier, and normally a net amount, VAT, and total. Receipts, contracts, bank statements,
marketing material, POS reports, and other documents are NOT facturas."""


@dataclass
class ClassificationResult:
    is_factura: bool
    confidence: float
    supplier_name: Optional[str]
    reasoning: str


def classify_invoice(text: str) -> ClassificationResult:
    cfg = _ai_config()
    model = cfg.get("classifier_model", "claude-haiku-4-5")
    client = _get_client()

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=CLASSIFY_SYSTEM,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": CLASSIFY_SCHEMA},
        },
        messages=[{"role": "user", "content": text[:15000]}],
    )
    data = _parse_json_response(response)
    return ClassificationResult(
        is_factura=bool(data["is_factura"]),
        confidence=float(data["confidence"]),
        supplier_name=data.get("supplier_name"),
        reasoning=data.get("reasoning", ""),
    )


# ---------------------------------------------------------------------------
# generate_extractor
# ---------------------------------------------------------------------------

CODEGEN_SCHEMA = {
    "type": "object",
    "properties": {
        "supplier_name": {
            "type": "string",
            "description": "Human-readable supplier name, e.g. 'Makro Distribucion S.A.'",
        },
        "python_code": {
            "type": "string",
            "description": "Complete, runnable Python source for the new extractors/suppliers/<slug>.py module.",
        },
    },
    "required": ["supplier_name", "python_code"],
    "additionalProperties": False,
}


def _load_codegen_system_prompt() -> list:
    """Build (once) the cached system-prompt blocks for codegen: the
    BaseExtractor contract + helpers + a few real extractors as few-shot
    examples. Read live from disk so it always reflects the current
    codebase rather than a copy that can drift out of sync."""
    global _codegen_system_prompt
    if _codegen_system_prompt is not None:
        return _codegen_system_prompt

    base_src = (EXTRACTORS_DIR / "base.py").read_text(encoding="utf-8")
    helpers_src = (EXTRACTORS_DIR / "helpers.py").read_text(encoding="utf-8")

    examples = []
    for fname in FEW_SHOT_SUPPLIERS:
        path = EXTRACTORS_DIR / "suppliers" / fname
        if path.exists():
            examples.append(f"# --- extractors/suppliers/{fname} ---\n{path.read_text(encoding='utf-8')}")

    instructions = """You write supplier-specific invoice extractors for a Spanish bar business's
FacturaAI pipeline. You will be given the extracted text of ONE sample invoice from a supplier
with no existing extractor, plus the BaseExtractor contract, shared parsing helpers, and a few
real extractors as style/pattern references below.

Write ONE new Python module implementing a BaseExtractor subclass for this supplier:
- can_handle(text) must reliably recognise future invoices from the SAME supplier (match on
  company name, CIF/NIF, or another stable identifier — not incidental formatting).
- extract(text) must populate date, supplier, invoice_number, net_amount, vat_amount, vat_rate
  (or vat_breakdown for mixed-rate invoices), total_amount, currency using regex against the
  actual layout you see in the sample text. Use parse_amount/parse_date/collapse_spaced_chars
  from extractors.helpers — do not reimplement Spanish number/date parsing yourself.
- If the sample text has character-level spacing artifacts (e.g. pdfplumber output like
  'M a k r o'), call collapse_spaced_chars() first, as makro.py does.
- Only extract fields you can support with a concrete pattern from the sample text — leave
  anything else as None rather than guessing.
- The module must import cleanly and never raise on can_handle() or extract() — wrap risky
  parsing in try/except that leaves fields as None on failure, matching the existing examples.
- Return the supplier's real display name in supplier_name, and set r.supplier to that same
  name inside extract().

Output only the two requested fields: supplier_name and the complete python_code for the new
module (imports included, ready to save as-is to extractors/suppliers/<slug>.py)."""

    system_text = (
        instructions
        + "\n\n# --- extractors/base.py ---\n" + base_src
        + "\n\n# --- extractors/helpers.py ---\n" + helpers_src
        + "\n\n" + "\n\n".join(examples)
    )

    _codegen_system_prompt = [
        {
            "type": "text",
            "text": system_text,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    return _codegen_system_prompt


@dataclass
class CodegenResult:
    supplier_name: str
    python_code: str


def generate_extractor(text: str, supplier_hint: Optional[str] = None) -> CodegenResult:
    cfg = _ai_config()
    model = cfg.get("codegen_model", "claude-opus-4-8")
    client = _get_client()

    user_content = f"Sample invoice text from a new supplier"
    if supplier_hint:
        user_content += f" (likely name: {supplier_hint})"
    user_content += f":\n\n{text[:20000]}"

    response = client.messages.create(
        model=model,
        max_tokens=8000,
        system=_load_codegen_system_prompt(),
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": CODEGEN_SCHEMA},
        },
        messages=[{"role": "user", "content": user_content}],
    )
    data = _parse_json_response(response)
    return CodegenResult(
        supplier_name=data["supplier_name"],
        python_code=data["python_code"],
    )


# ---------------------------------------------------------------------------
# review_plausibility
# ---------------------------------------------------------------------------

PLAUSIBILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "plausible": {"type": "boolean"},
        "issue": {
            "type": ["string", "null"],
            "description": "Plain-English description of what looks wrong, or null if plausible.",
        },
    },
    "required": ["plausible", "issue"],
    "additionalProperties": False,
}

PLAUSIBILITY_SYSTEM = """You sanity-check invoice field extraction for a Spanish bar business.
You'll see the fields a parser extracted from an invoice, plus the invoice's raw text. Flag
plausible: false only for things that are actually implausible given the text — e.g. a total
that is orders of magnitude larger or smaller than what the text shows (a likely decimal-shift
or OCR error), a total that doesn't match what's printed on the invoice, or a supplier name
that doesn't appear in the text at all. Do NOT flag things that are merely unusual but clearly
correct per the text (a genuinely large one-off order, an odd but valid VAT rate, etc.) — this
check exists to catch extraction bugs, not to second-guess legitimate invoices."""


@dataclass
class PlausibilityResult:
    plausible: bool
    issue: Optional[str]


def review_plausibility(text: str, extraction: dict) -> PlausibilityResult:
    cfg = _ai_config()
    model = cfg.get("plausibility_model", "claude-haiku-4-5")
    client = _get_client()

    fields_summary = json.dumps(
        {
            "date": extraction.get("date"),
            "supplier": extraction.get("supplier"),
            "net_amount": extraction.get("net_amount"),
            "vat_amount": extraction.get("vat_amount"),
            "total_amount": extraction.get("total_amount"),
            "currency": extraction.get("currency"),
        },
        ensure_ascii=False,
    )
    user_content = (
        f"Extracted fields:\n{fields_summary}\n\nRaw invoice text:\n{text[:15000]}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=PLAUSIBILITY_SYSTEM,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": PLAUSIBILITY_SCHEMA},
        },
        messages=[{"role": "user", "content": user_content}],
    )
    data = _parse_json_response(response)
    return PlausibilityResult(
        plausible=bool(data["plausible"]),
        issue=data.get("issue"),
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_json_response(response) -> dict:
    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        raise ValueError(f"No text block in Claude response (stop_reason={response.stop_reason})")
    return json.loads(text_block.text)
