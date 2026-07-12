#!/usr/bin/env python3
"""
Retries files already sitting in manual_review/ through the same
extraction -> classification -> filing pipeline used for new mail
(processor.process_pdf() — reused as-is, nothing duplicated here), without
touching Gmail at all. Useful after fixing a classification/extraction bug,
to see whether previously-flagged files now go through cleanly.

On success: process_pdf() moves the file to output/YYYY/MM/ (or rejected/)
exactly like a normal run — nothing special needed here.
On continued failure: the file stays in manual_review/ (possibly renamed,
if its newly-extracted fields differ from before), and its DB row's
retry_count/last_retried_at are updated so the dashboard shows it was
retried, not just left untouched since its first pass.

Usage:
    python scripts/reprocess_manual_review.py                # every file in manual_review/
    python scripts/reprocess_manual_review.py --file "Unknown 0000-00-00 0.00_3.pdf"

Also runnable from the dashboard's Review page ("Reprocess" buttons) for
an ad-hoc retry without a terminal — see dashboard/reprocess_job.py.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import ensure_dirs, get_config, load_config  # noqa: E402
import db  # noqa: E402
from processor import process_pdf  # noqa: E402

log = logging.getLogger(__name__)

# Progress callback signature: progress_cb(i, total, filename, outcome)
ProgressCb = Optional[Callable[[int, int, str, str], None]]


def reprocess_file(path: Path) -> str:
    """Retry one file currently sitting in manual_review/. Returns one of
    'succeeded' | 'pending_review' | 'rejected' | 'failed'."""
    file_hash = db.hash_file(str(path))
    previous = db.get_invoice_by_hash(file_hash)
    retry_count = (previous.get("retry_count") or 0) + 1 if previous else 1

    # Reprocessing requires clearing the old row first — process_pdf()'s
    # dedup check (db.is_duplicate) would otherwise just skip this file as
    # "already processed" and never actually retry it.
    db.delete_invoice_by_hash(file_hash)

    try:
        result = process_pdf(str(path), source="backfill")
    except Exception as e:
        log.error("process_pdf raised while reprocessing %s: %s", path, e)
        result = None

    row_after = db.get_invoice_by_hash(file_hash)
    if row_after is None:
        # process_pdf() didn't get far enough to write a new row (e.g. a
        # move/db error after we already deleted the old one) — reinsert a
        # minimal record so the file doesn't silently vanish from the
        # review queue. The physical file itself is untouched in this case.
        reason = result.reason if result else "unexpected error during reprocessing"
        db.insert_invoice({
            "file_path": str(path), "source": "backfill", "confidence": 0.0,
            "needs_review": 1, "vat_flag": 0, "spike_flag": 0, "ai_flag": 0,
            "rejected": 0, "reject_reason": f"retry failed: {reason}",
            "extractor_pending": 0, "hash": file_hash, "currency": "EUR",
        })
        db.bump_retry(file_hash, retry_count)
        return "failed"

    db.bump_retry(file_hash, retry_count)

    if result is None or result.failed:
        return "failed"
    if result.rejected:
        return "rejected"
    if result.success and result.reason:
        return "pending_review"
    if result.success:
        return "succeeded"
    return "failed"


def reprocess_all(single_file: str | None = None, progress_cb: ProgressCb = None) -> dict:
    load_config()
    ensure_dirs()
    db.init_db()
    cfg = get_config()

    mr_dir = Path(cfg["paths"]["manual_review"])
    if not mr_dir.is_dir():
        print(f"No manual_review folder at {mr_dir}.")
        return {"error": f"no manual_review folder at {mr_dir}"}

    if single_file:
        candidates = [p for p in mr_dir.rglob("*.pdf") if p.name == single_file]
        if not candidates:
            print(f"File {single_file!r} not found under {mr_dir}.")
            return {"error": f"file {single_file!r} not found under {mr_dir}"}
    else:
        candidates = sorted(mr_dir.rglob("*.pdf"))

    if not candidates:
        print("manual_review/ is empty — nothing to reprocess.")
        return {"total": 0, "succeeded": 0, "pending_review": 0, "rejected": 0, "failed": 0}

    counts = {"succeeded": 0, "pending_review": 0, "rejected": 0, "failed": 0}
    total = len(candidates)
    for i, path in enumerate(candidates, start=1):
        try:
            outcome = reprocess_file(path)
        except Exception as e:
            log.error("Reprocessing failed for %s: %s", path, e)
            outcome = "failed"
        counts[outcome] += 1
        print(f"[{i}/{total}] {path.name} -> {outcome}")
        if progress_cb:
            progress_cb(i, total, path.name, outcome)

    print(
        f"\nReprocessed: {counts['succeeded']} succeeded, "
        f"{counts['pending_review']} still pending review, "
        f"{counts['rejected']} rejected, {counts['failed']} failed"
    )
    return {"total": total, **counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", metavar="FILENAME", default=None,
                         help="Retry only this one file (basename, as it currently appears in manual_review/)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
    reprocess_all(single_file=args.file)


if __name__ == "__main__":
    main()
