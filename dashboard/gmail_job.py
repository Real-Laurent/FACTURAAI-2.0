"""
Background runner for an ad-hoc, date-ranged Gmail check triggered from the
dashboard ("Check Gmail" button on /health) — wraps
scripts/backfill_gmail.run_backfill() in a daemon thread so the request that
starts it returns immediately, with progress polled via /gmail/backfill/status.

Only one run at a time; a second start request while one is in flight is
rejected rather than queued or run in parallel (both would hit the same
Gmail account and inbox/gmail/ folder).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

_lock = threading.Lock()
_status: dict = {"running": False}


def start(since: Optional[str], until: Optional[str]) -> dict:
    """Kick off a backfill run for [since, until). Returns {"ok": True} if
    started, or {"ok": False, "error": "..."} if one is already running."""
    with _lock:
        if _status.get("running"):
            return {"ok": False, "error": "already_running"}
        _status.clear()
        _status.update({
            "running": True,
            "since": since,
            "until": until,
            "current": 0,
            "total": 0,
            "last_message": "",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
            "counts": None,
        })

    thread = threading.Thread(
        target=_run, args=(since, until), daemon=True, name="gmail-backfill-job",
    )
    thread.start()
    return {"ok": True}


def get_status() -> dict:
    with _lock:
        return dict(_status)


def _progress(i: int, total: int, filename: str, status: str) -> None:
    with _lock:
        _status.update({"current": i, "total": total, "last_message": f"{filename} -> {status}"})


def _run(since: Optional[str], until: Optional[str]) -> None:
    from scripts.backfill_gmail import run_backfill

    try:
        counts = run_backfill(since=since, until=until, progress_cb=_progress)
        with _lock:
            if counts and counts.get("error"):
                _status["error"] = counts["error"]
            else:
                _status["counts"] = counts
    except Exception as e:
        log.exception("Dashboard-triggered Gmail backfill failed")
        with _lock:
            _status["error"] = str(e)
    finally:
        with _lock:
            _status["running"] = False
            _status["finished_at"] = datetime.now(timezone.utc).isoformat()
