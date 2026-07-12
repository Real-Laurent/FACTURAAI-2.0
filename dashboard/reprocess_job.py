"""
Background runner for the dashboard's "Reprocess" button(s) on /review —
wraps scripts/reprocess_manual_review.reprocess_all() in a daemon thread so
the request that starts it returns immediately, with progress polled via
/manual-review/reprocess/status. Same shape as dashboard/gmail_job.py.

Only one run at a time; a second start request while one is in flight is
rejected rather than queued or run in parallel (both would hit the same
manual_review/ folder and DB).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

_lock = threading.Lock()
_status: dict = {"running": False}


def start(single_file: Optional[str] = None) -> dict:
    """Kick off a reprocess run (all manual_review/ files, or just one).
    Returns {"ok": True} if started, or {"ok": False, "error": "..."} if
    one is already running."""
    with _lock:
        if _status.get("running"):
            return {"ok": False, "error": "already_running"}
        _status.clear()
        _status.update({
            "running": True,
            "file": single_file,
            "current": 0,
            "total": 0,
            "last_message": "",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
            "counts": None,
        })

    thread = threading.Thread(
        target=_run, args=(single_file,), daemon=True, name="manual-review-reprocess-job",
    )
    thread.start()
    return {"ok": True}


def get_status() -> dict:
    with _lock:
        return dict(_status)


def _progress(i: int, total: int, filename: str, outcome: str) -> None:
    with _lock:
        _status.update({"current": i, "total": total, "last_message": f"{filename} -> {outcome}"})


def _run(single_file: Optional[str]) -> None:
    from scripts.reprocess_manual_review import reprocess_all

    try:
        counts = reprocess_all(single_file=single_file, progress_cb=_progress)
        with _lock:
            if counts and counts.get("error"):
                _status["error"] = counts["error"]
            else:
                _status["counts"] = counts
    except Exception as e:
        log.exception("Dashboard-triggered manual_review reprocess failed")
        with _lock:
            _status["error"] = str(e)
    finally:
        with _lock:
            _status["running"] = False
            _status["finished_at"] = datetime.now(timezone.utc).isoformat()
