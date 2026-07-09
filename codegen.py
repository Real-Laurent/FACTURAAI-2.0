"""
Automatic extractor generation: when classifier.py detects a new-supplier
factura, this module asks Claude to write a BaseExtractor subclass, self-tests
it in an isolated subprocess against the sample that triggered it, and — if
that passes — promotes it into the live extractors/suppliers/ directory.

The invoice itself still routes to manual_review for a one-time human
confirmation (per config.ai.auto_trust_new_extractors); the extractor is
usable immediately for that confirmation step and for every invoice after.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import ai_client
import extractors.registry as registry

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
SUPPLIERS_DIR = PROJECT_ROOT / "extractors" / "suppliers"
PENDING_DIR = PROJECT_ROOT / "extractors" / "pending_suppliers"
SELFTEST_SCRIPT = PROJECT_ROOT / "_codegen_selftest.py"
SELFTEST_TIMEOUT_SECONDS = 20


@dataclass
class CodegenOutcome:
    success: bool
    supplier_name: Optional[str]
    module_path: Optional[Path]
    reason: str


def generate_and_test_extractor(text: str, supplier_hint: Optional[str] = None) -> CodegenOutcome:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    try:
        result = ai_client.generate_extractor(text, supplier_hint=supplier_hint)
    except Exception as e:
        log.error("generate_extractor failed: %s", e)
        return CodegenOutcome(
            success=False, supplier_name=supplier_hint, module_path=None,
            reason=f"codegen API call failed: {e}",
        )

    slug = _slugify(result.supplier_name)
    pending_path = PENDING_DIR / f"{slug}.py"
    pending_path.write_text(result.python_code, encoding="utf-8")
    log.info("Generated extractor for %s → %s", result.supplier_name, pending_path)

    ok, detail = _self_test(pending_path, text)
    if not ok:
        log.warning("Self-test FAILED for %s: %s", result.supplier_name, detail)
        return CodegenOutcome(
            success=False, supplier_name=result.supplier_name, module_path=pending_path,
            reason=f"extractor generation failed self-test: {detail}",
        )

    live_path = _promote(pending_path, slug)
    registry.reload()
    log.info("Promoted extractor for %s → %s (self-test: %s)", result.supplier_name, live_path, detail)
    return CodegenOutcome(
        success=True, supplier_name=result.supplier_name, module_path=live_path,
        reason=f"self-test passed: {detail}",
    )


def _self_test(module_path: Path, sample_text: str) -> tuple[bool, str]:
    """Run the generated module in an isolated subprocess against the
    sample text that produced it. Subprocess isolation protects the main
    process from a pathological generated regex or an outright crash."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(sample_text)
        text_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [sys.executable, str(SELFTEST_SCRIPT), str(module_path), str(text_path)],
            capture_output=True, text=True, timeout=SELFTEST_TIMEOUT_SECONDS,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return False, f"self-test timed out after {SELFTEST_TIMEOUT_SECONDS}s (possible regex backtracking)"
    finally:
        text_path.unlink(missing_ok=True)

    if proc.returncode != 0:
        return False, f"self-test process exited {proc.returncode}: {proc.stderr[-500:]}"

    import json
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return False, f"self-test produced no parseable output: {proc.stdout[-500:]} {proc.stderr[-500:]}"

    if not data.get("ok"):
        return False, data.get("error", "unknown self-test failure")
    return True, f"populated {data.get('populated_fields')}"


def _promote(pending_path: Path, slug: str) -> Path:
    dest = SUPPLIERS_DIR / f"{slug}.py"
    if dest.exists():
        i = 2
        while (SUPPLIERS_DIR / f"{slug}_{i}.py").exists():
            i += 1
        dest = SUPPLIERS_DIR / f"{slug}_{i}.py"
    pending_path.replace(dest)
    return dest


def _slugify(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return name or "unknown_supplier"
