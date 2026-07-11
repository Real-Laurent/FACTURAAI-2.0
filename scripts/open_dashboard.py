#!/usr/bin/env python3
"""
Waits for the dashboard to actually start accepting connections, then opens
it in the default browser. Used by the one-click start_facturaai.bat /
start_facturaai.command launchers — polls the real port instead of a blind
sleep, since main.py's startup time (db init, watcher, dependency imports)
varies.
"""

from __future__ import annotations

import socket
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import get_config, load_config  # noqa: E402

TIMEOUT_SECONDS = 30.0


def _wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    load_config()
    cfg = get_config().get("dashboard", {})
    host = cfg.get("host", "127.0.0.1")
    port = cfg.get("port", 5000)

    if _wait_for_port(host, port, TIMEOUT_SECONDS):
        webbrowser.open(f"http://{host}:{port}")
        return 0

    print(
        f"Dashboard didn't come up on {host}:{port} within {TIMEOUT_SECONDS:.0f}s "
        "— check the FacturaAI console window for errors."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
