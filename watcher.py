"""
Watchdog-based file system watcher for inbox/scan/.
Queues new PDF files as they appear.
"""

import logging
import queue
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from watchdog.observers import Observer

from config.loader import get_config

log = logging.getLogger(__name__)

_queue: queue.Queue = queue.Queue()
_observer: Observer = None
_lock = threading.Lock()


class _PDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            log.debug("Watcher: new file detected: %s", event.src_path)
            _queue.put(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
            log.debug("Watcher: file moved in: %s", event.dest_path)
            _queue.put(event.dest_path)


def start():
    global _observer
    with _lock:
        if _observer and _observer.is_alive():
            return
        scan_dir = get_config()["paths"]["inbox_scan"]
        Path(scan_dir).mkdir(parents=True, exist_ok=True)
        _observer = Observer()
        _observer.schedule(_PDFHandler(), scan_dir, recursive=True)
        _observer.start()
        log.info("Watcher started on %s", scan_dir)


def stop():
    global _observer
    with _lock:
        if _observer:
            _observer.stop()
            _observer.join()
            _observer = None
            log.info("Watcher stopped")


def drain() -> list[str]:
    """Return all paths currently queued, without blocking."""
    paths = []
    # Brief settle delay so the file is fully written before we process it
    time.sleep(0.5)
    while True:
        try:
            paths.append(_queue.get_nowait())
        except queue.Empty:
            break
    return paths


def scan_existing() -> list[str]:
    """Return any PDFs already sitting in inbox/scan/ at startup."""
    scan_dir = get_config()["paths"]["inbox_scan"]
    return [str(p) for p in Path(scan_dir).rglob("*.pdf")]
