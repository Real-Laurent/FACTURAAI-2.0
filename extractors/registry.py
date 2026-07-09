"""
Auto-discovers all BaseExtractor subclasses in extractors/suppliers/ and selects
the best one for a given invoice text.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Optional

from extractors.base import BaseExtractor, ExtractionResult

log = logging.getLogger(__name__)

_registry: list[BaseExtractor] = []
_loaded = False


def _load_all_extractors():
    global _loaded
    if _loaded:
        return
    import extractors.suppliers as pkg
    for finder, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        full_name = f"extractors.suppliers.{module_name}"
        try:
            importlib.import_module(full_name)
        except Exception as e:
            log.warning("Failed to import extractor module %s: %s", full_name, e)

    for subclass in _all_subclasses(BaseExtractor):
        try:
            instance = subclass()
            _registry.append(instance)
        except Exception as e:
            log.warning("Failed to instantiate %s: %s", subclass.__name__, e)

    # Generic fallback always goes last
    _registry.sort(key=lambda e: e.__class__.__name__ == "GenericFallbackExtractor")
    _loaded = True
    log.info("Loaded %d extractors: %s", len(_registry), [e.supplier_name for e in _registry])


def _all_subclasses(cls):
    result = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_all_subclasses(sub))
    return result


def get_registry() -> list[BaseExtractor]:
    _load_all_extractors()
    return _registry


def reload() -> list[BaseExtractor]:
    """Force a re-scan of extractors/suppliers/ — call after codegen.py
    promotes a freshly generated extractor from _pending/ into the live
    directory, so it's picked up without restarting the process."""
    global _loaded
    _registry.clear()
    _loaded = False
    return get_registry()


def select_extractor(text: str) -> Optional[BaseExtractor]:
    """Return the first extractor whose can_handle() returns True."""
    _load_all_extractors()
    for extractor in _registry:
        try:
            if extractor.can_handle(text):
                return extractor
        except Exception as e:
            log.warning("can_handle() raised in %s: %s", extractor.__class__.__name__, e)
    return None


def extract_invoice(text: str) -> tuple[ExtractionResult, str]:
    """
    Run extraction against text.
    Returns (result, extractor_name).
    Falls back to a zero-confidence result if nothing matches.
    """
    extractor = select_extractor(text)
    if extractor is None:
        log.warning("No extractor matched; returning empty result")
        return ExtractionResult(confidence=0.0), "none"

    result = extractor.safe_extract(text)
    log.debug("Extractor %s → confidence %.2f", extractor.supplier_name, result.confidence)
    return result, extractor.supplier_name
