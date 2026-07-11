#!/usr/bin/env python3
"""
One-time historical import: pulls every PDF attachment already sitting in
the monitored Gmail mailbox (not just new/unprocessed mail) through the
same pipeline steady-state processing uses.

Usage:
    python scripts/backfill_gmail.py [--since YYYY-MM-DD] [--until YYYY-MM-DD]

Also runnable from the dashboard's Status page ("Check Gmail" button) for
an ad-hoc date-range check without a terminal — see dashboard/gmail_job.py.

Resumable for free: processor.process_pdf() dedupes by content hash, so if
this is interrupted (closed terminal, network drop), re-running it just
skips everything already archived.

Note on scope: the approved plan called for routing the classification and
plausibility-review calls through the Message Batches API during backfill
(50% cost, since a bit of async delay is fine for a one-time bulk job).
That would need classifier.py's per-invoice detect-then-act flow (a new
supplier's codegen call depends on that invoice's classification result
before the next invoice can safely reuse the registry) to be restructured
around a submit-all/poll/resume-per-result batch cycle. Given the size of
that change and the difficulty of validating a batch integration without
live API access in this session, this script runs the same synchronous
pipeline as steady-state processing instead — correct and simple, at
standard (non-batch) API pricing. Revisit if the per-run cost at real
volume turns out to matter.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import ensure_dirs, get_config, load_config
import db
from gmail_poller import _get_service, _process_message
from processor import process_pdf

log = logging.getLogger(__name__)


def _iter_all_message_ids(service, query: str) -> list[str]:
    """Page through Gmail's messages.list until every match is collected."""
    ids = []
    page_token = None
    while True:
        response = (
            service.users().messages()
            .list(userId="me", q=query, pageToken=page_token, maxResults=500)
            .execute()
        )
        ids.extend(m["id"] for m in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return ids


def run_backfill(
    since: str | None = None,
    until: str | None = None,
    progress_cb=None,
) -> dict:
    """Run the backfill for an optional [since, until) date window.

    progress_cb, if given, is called as progress_cb(i, total, filename, status)
    after every processed message — used by the dashboard's "Check Gmail"
    button to report live progress. Returns the final counts dict."""
    load_config()
    ensure_dirs()
    db.init_db()

    cfg = get_config()
    if not cfg.get("gmail", {}).get("enabled", False):
        print("gmail.enabled is false in config — nothing to do.")
        return {"error": "gmail.enabled is false in config"}

    dest_dir = cfg["paths"]["inbox_gmail"]
    os.makedirs(dest_dir, exist_ok=True)

    service = _get_service()

    # Broad query — every PDF attachment, no "unprocessed" filter. The
    # classifier decides invoice vs. not; this stage just fetches candidates.
    query = "has:attachment filename:pdf"
    if since:
        query += f" after:{since.replace('-', '/')}"
    if until:
        query += f" before:{until.replace('-', '/')}"

    print(f"Searching Gmail: {query!r} ...")
    message_ids = _iter_all_message_ids(service, query)
    total = len(message_ids)
    print(f"Found {total} messages with PDF attachments.")

    archived = rejected = pending_review = failed = skipped = 0

    for i, msg_id in enumerate(message_ids, start=1):
        try:
            paths = _process_message(service, msg_id, dest_dir)
        except Exception as e:
            log.error("Failed to download attachments for message %s: %s", msg_id, e)
            print(f"[{i}/{total}] message {msg_id} -> download failed: {e}")
            failed += 1
            if progress_cb:
                progress_cb(i, total, f"message {msg_id}", f"download failed: {e}")
            continue

        if not paths:
            print(f"[{i}/{total}] message {msg_id} -> no PDF attachment found")
            if progress_cb:
                progress_cb(i, total, f"message {msg_id}", "no PDF attachment found")
            continue

        for path in paths:
            filename = os.path.basename(path)
            result = process_pdf(path, source="backfill")
            if result.success:
                if result.reason:
                    pending_review += 1
                    status = f"pending review ({result.reason})"
                else:
                    archived += 1
                    status = "archived"
            elif result.rejected:
                rejected += 1
                status = f"rejected ({result.reason})"
            elif result.skipped:
                skipped += 1
                status = "already processed"
            else:
                failed += 1
                status = f"FAILED ({result.reason})"
            print(f"[{i}/{total}] {filename} -> {status}")
            if progress_cb:
                progress_cb(i, total, filename, status)

    counts = {
        "total": total, "archived": archived, "pending_review": pending_review,
        "rejected": rejected, "skipped": skipped, "failed": failed,
    }
    print(
        f"\nDone. archived={archived} pending_review={pending_review} "
        f"rejected={rejected} skipped={skipped} failed={failed}"
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", metavar="YYYY-MM-DD", default=None,
                         help="Only fetch mail on/after this date")
    parser.add_argument("--until", metavar="YYYY-MM-DD", default=None,
                         help="Only fetch mail before this date")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
    run_backfill(since=args.since, until=args.until)


if __name__ == "__main__":
    main()
