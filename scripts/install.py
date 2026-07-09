#!/usr/bin/env python3
"""
Cross-platform installer for FacturaAI 2.0 — Windows and macOS.

Replaces v1's bash install_launchagent.sh with one script so the idempotent
check-before-install logic (skip venv creation if it exists, skip a brew
install if the binary is already on PATH, etc. — same discipline v1's shell
scripts already used) lives in one place instead of being duplicated per OS.

Usage:
    python scripts/install.py [--service]

Without --service this just sets up the venv, dependencies, config, and
directories — the safe default anywhere. --service additionally registers
a background service (launchd on macOS, Task Scheduler on Windows) so
FacturaAI starts automatically; skip it if you'd rather run
`python main.py` manually or via your own scheduler.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _env_checks import (  # noqa: E402
    PROJECT_ROOT, check_ghostscript, check_tesseract, ensure_config_yaml,
    ensure_directories, ensure_python_deps, ensure_venv,
)


def install_macos_service() -> None:
    plist_name = "com.facturaai.agent.plist"
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist_dest = agents_dir / plist_name
    plist_src = PROJECT_ROOT / plist_name

    if not plist_src.exists():
        print(f"No {plist_name} found in project root — skipping launchd install. "
              f"Run `python main.py` manually or via your own scheduler instead.")
        return

    text = plist_src.read_text(encoding="utf-8").replace("__PROJECT_ROOT__", str(PROJECT_ROOT))
    plist_dest.write_text(text, encoding="utf-8")

    already_loaded = subprocess.run(
        ["launchctl", "list"], capture_output=True, text=True
    ).stdout.find("com.facturaai.agent") != -1
    if already_loaded:
        print("Reloading existing launchd agent...")
        subprocess.run(["launchctl", "unload", str(plist_dest)], check=False)
    subprocess.run(["launchctl", "load", "-w", str(plist_dest)], check=True)
    print(f"launchd agent installed and loaded: {plist_dest}")


def install_windows_service() -> None:
    task_name = "FacturaAI"
    exists = subprocess.run(
        ["schtasks", "/query", "/tn", task_name],
        capture_output=True, text=True,
    ).returncode == 0
    if exists:
        print(f'Scheduled task "{task_name}" already exists — leaving it as-is. '
              f'Delete it first (schtasks /delete /tn {task_name}) to recreate.')
        return

    from _env_checks import venv_python
    py = venv_python()
    main_py = PROJECT_ROOT / "main.py"
    subprocess.run(
        [
            "schtasks", "/create", "/tn", task_name,
            "/tr", f'"{py}" "{main_py}"',
            "/sc", "onlogon",
            "/rl", "limited",
        ],
        check=True,
    )
    print(f'Scheduled task "{task_name}" created (runs at logon). '
          f'Run it now from Task Scheduler, or just `python main.py` to start immediately.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", action="store_true",
                         help="Also register a background service (launchd/Task Scheduler)")
    args = parser.parse_args()

    print("=== FacturaAI 2.0 Installer ===\n")

    py = ensure_venv()
    ensure_python_deps(py)
    check_tesseract()
    check_ghostscript()
    ensure_config_yaml()
    ensure_directories()

    if args.service:
        system = platform.system()
        if system == "Darwin":
            install_macos_service()
        elif system == "Windows":
            install_windows_service()
        else:
            print(f"No service integration for {system} — run `python main.py` manually "
                  f"or via cron/your own scheduler.")

    print("\nDone.")
    print("  Drop PDFs into:  inbox/scan/")
    print("  Dashboard:       http://127.0.0.1:5000")
    print("  Manual start:    python main.py")


if __name__ == "__main__":
    main()
