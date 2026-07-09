"""
Internal helper, invoked as a subprocess by codegen.py — never imported directly.

Loads a freshly AI-generated extractor module in isolation, runs it against
the sample invoice text that produced it, and reports pass/fail as JSON on
stdout. Runs in a subprocess (rather than in-process) so a pathological
generated regex (catastrophic backtracking) or an outright crash can't take
down the main FacturaAI process — the caller applies a hard timeout.

Usage: python _codegen_selftest.py <module_path> <sample_text_path>
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def main() -> None:
    module_path = Path(sys.argv[1])
    text_path = Path(sys.argv[2])
    text = text_path.read_text(encoding="utf-8")

    try:
        from extractors.base import BaseExtractor

        spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"import failed: {type(e).__name__}: {e}"}))
        return

    extractor_cls = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, BaseExtractor) and obj is not BaseExtractor:
            extractor_cls = obj
            break

    if extractor_cls is None:
        print(json.dumps({"ok": False, "error": "no BaseExtractor subclass found in generated module"}))
        return

    try:
        instance = extractor_cls()
        if not instance.can_handle(text):
            print(json.dumps({"ok": False, "error": "can_handle() returned False on its own sample text"}))
            return

        result = instance.safe_extract(text)
        populated = [
            f for f in ("date", "supplier", "invoice_number", "net_amount", "vat_amount", "total_amount")
            if getattr(result, f, None) is not None
        ]
        if not populated:
            print(json.dumps({"ok": False, "error": "extract() produced an entirely empty result"}))
            return

        print(json.dumps({
            "ok": True,
            "populated_fields": populated,
            "supplier_name": instance.supplier_name,
        }))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))


if __name__ == "__main__":
    main()
