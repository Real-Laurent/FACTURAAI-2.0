#!/usr/bin/env python3
"""
FacturaAI — main entry point.
Runs the processing loop + Flask dashboard as background thread.
Designed to run as a macOS LaunchAgent.
"""

import logging
import logging.handlers
import os
import signal
import sys
import threading
import time
from pathlib import Path

# Allow running from any working directory
sys.path.insert(0, str(Path(__file__).parent))

from config.loader import load_config, ensure_dirs, get_config
import db
import watcher
from gmail_poller import poll_gmail
from processor import process_pdf
from exports import run_exports
from retention import run_yearly_archives


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging():
    cfg = get_config()
    log_dir = cfg["paths"]["logs"]
    os.makedirs(log_dir, exist_ok=True)

    log_cfg = cfg.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    max_bytes = log_cfg.get("max_bytes", 10 * 1024 * 1024)
    backup_count = log_cfg.get("backup_count", 5)

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "factura.log"),
        maxBytes=max_bytes, backupCount=backup_count,
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)


log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shutdown coordination
# ---------------------------------------------------------------------------

_shutdown = threading.Event()


def _handle_signal(sig, frame):
    log.info("Signal %s received — shutting down", sig)
    _shutdown.set()


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# ---------------------------------------------------------------------------
# Processing cycle
# ---------------------------------------------------------------------------

_cycle_number = 0


def _process_paths(paths: list[str], source: str) -> tuple[int, int, int]:
    """Run process_pdf() over paths, returning (processed, failed, skipped)."""
    processed = failed = skipped = 0
    for path in paths:
        try:
            result = process_pdf(path, source=source)
            if result.success:
                processed += 1
            elif result.skipped:
                skipped += 1
            else:
                failed += 1
        except Exception as e:
            log.error("Unhandled error processing %s: %s", path, e)
            failed += 1
    return processed, failed, skipped


def run_cycle():
    global _cycle_number
    _cycle_number += 1
    t0 = time.monotonic()

    # Collect + process local scan files first, independent of Gmail — a
    # slow or stuck Gmail poll (e.g. waiting on a first-time OAuth browser
    # flow) must never delay files already sitting in inbox/scan/.
    scan_paths = list(dict.fromkeys(watcher.drain()))
    if _cycle_number == 1:
        scan_paths = list(dict.fromkeys(scan_paths + watcher.scan_existing()))
    scan_processed, scan_failed, scan_skipped = _process_paths(scan_paths, "scan")

    # Gmail — poll_gmail() already catches its own exceptions and has a
    # bounded wait on first-time auth (see gmail_poller._get_service), so
    # this can't hang the loop indefinitely, but scan files above are
    # processed regardless of what happens here.
    gmail_paths = [p for p in dict.fromkeys(poll_gmail()) if p not in scan_paths]
    gmail_processed, gmail_failed, gmail_skipped = _process_paths(gmail_paths, "gmail")

    found = len(scan_paths) + len(gmail_paths)
    processed = scan_processed + gmail_processed
    failed = scan_failed + gmail_failed
    skipped = scan_skipped + gmail_skipped

    duration = time.monotonic() - t0
    db.log_cycle(_cycle_number, found, processed, failed, skipped, duration)
    db.update_heartbeat()

    if found:
        log.info(
            "Cycle #%d done — found=%d processed=%d failed=%d skipped=%d (%.1fs)",
            _cycle_number, found, processed, failed, skipped, duration,
        )

    if processed:
        run_exports()
        run_yearly_archives()


# ---------------------------------------------------------------------------
# Dashboard thread
# ---------------------------------------------------------------------------

def start_dashboard():
    try:
        from dashboard.app import run_dashboard
        t = threading.Thread(target=run_dashboard, daemon=True, name="dashboard")
        t.start()
        log.info("Dashboard thread started")
    except Exception as e:
        log.error("Failed to start dashboard: %s", e)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    cfg_path = os.environ.get("FACTURA_CONFIG")
    load_config(cfg_path)
    ensure_dirs()
    setup_logging()

    log.info("FacturaAI starting up")
    db.init_db()
    watcher.start()
    start_dashboard()

    cfg = get_config()
    poll_interval = cfg.get("gmail", {}).get("poll_interval_minutes", 10) * 60

    last_gmail_poll = 0.0

    try:
        while not _shutdown.is_set():
            now = time.monotonic()
            if now - last_gmail_poll >= poll_interval:
                last_gmail_poll = now

            run_cycle()
            _shutdown.wait(timeout=30)
    finally:
        log.info("Shutting down watcher")
        watcher.stop()
        log.info("FacturaAI stopped")


if __name__ == "__main__":
    main()
