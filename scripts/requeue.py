#!/usr/bin/env python3
"""
Deletes the DB record(s) for PDFs already sitting in manual_review/ or
rejected/ that match a filename pattern, and moves the physical files into
inbox/scan/ so the next run reprocesses them from scratch under the current
code/prompts/extractors.

Useful after fixing a classification or extraction bug: files that were
misfiled under the old buggy behavior won't be picked up again on their own
(process_pdf() dedupes by content hash, so a DB row from the old run blocks
reprocessing even if you just drop the file back into an inbox folder) —
this deletes that DB row and requeues the file in one step.

Usage:
    python scripts/requeue.py "*starworld*"             # case-insensitive glob match
    python scripts/requeue.py "Starworld Trade*.pdf" --dry-run
"""

from __future__ import annotations

import argparse
import fnmatch
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import ensure_dirs, get_config, load_config  # noqa: E402
import db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pattern", help='Glob-style filename pattern, e.g. "*starworld*" (case-insensitive)')
    parser.add_argument("--dry-run", action="store_true", help="List matches without changing anything")
    args = parser.parse_args()

    load_config()
    ensure_dirs()
    db.init_db()
    cfg = get_config()

    scan_dir = Path(cfg["paths"]["inbox_scan"])
    scan_dir.mkdir(parents=True, exist_ok=True)

    search_dirs = [Path(cfg["paths"]["manual_review"]), Path(cfg["paths"]["rejected"])]
    pattern = args.pattern.lower()

    matches = []
    for d in search_dirs:
        if not d.is_dir():
            continue
        for p in d.rglob("*.pdf"):
            if fnmatch.fnmatch(p.name.lower(), pattern):
                matches.append(p)

    if not matches:
        print(f"No files under manual_review/ or rejected/ match {args.pattern!r}.")
        return

    print(f"Found {len(matches)} matching file(s):")
    for p in matches:
        print(f"  {p}")

    if args.dry_run:
        print("\n--dry-run: no changes made.")
        return

    requeued = 0
    for p in matches:
        file_hash = db.hash_file(str(p))
        with db.transaction() as conn:
            cur = conn.execute("DELETE FROM invoices WHERE hash = ?", (file_hash,))
            deleted = cur.rowcount

        dest = scan_dir / p.name
        i = 1
        while dest.exists():
            dest = scan_dir / f"{p.stem}_{i}{p.suffix}"
            i += 1
        shutil.move(str(p), str(dest))
        print(f"Requeued: {p.name} (deleted {deleted} DB row(s)) -> {dest}")
        requeued += 1

    print(f"\nDone. {requeued} file(s) moved to {scan_dir} for reprocessing.")
    print("Start (or restart) FacturaAI to pick them up: start_facturaai.bat, or python main.py")


if __name__ == "__main__":
    main()
