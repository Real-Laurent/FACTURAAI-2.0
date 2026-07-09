#!/usr/bin/env python3
"""
Cross-platform update script for FacturaAI 2.0 — replaces v1's update.sh.

Pulls the latest code (if this is a git checkout), re-runs the same
idempotent dependency checks install.py uses, then restarts whichever
per-OS service is registered — or just prints a reminder to restart
main.py manually if none is.

Usage: python scripts/update.py
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _env_checks import (  # noqa: E402
    PROJECT_ROOT, check_ghostscript, check_tesseract, ensure_python_deps,
    ensure_venv, is_git_repo,
)


def pull_latest() -> None:
    if not is_git_repo():
        print("Not a git checkout — skipping git pull.")
        return
    print("Pulling latest from git...")
    subprocess.run(["git", "pull", "--rebase"], check=True, cwd=str(PROJECT_ROOT))


def restart_macos_service() -> None:
    plist_dest = Path.home() / "Library" / "LaunchAgents" / "com.facturaai.agent.plist"
    if not plist_dest.exists():
        print("No launchd agent installed — restart with: python main.py")
        return
    loaded = subprocess.run(
        ["launchctl", "list"], capture_output=True, text=True
    ).stdout.find("com.facturaai.agent") != -1
    if loaded:
        subprocess.run(["launchctl", "unload", str(plist_dest)], check=False)
    subprocess.run(["launchctl", "load", "-w", str(plist_dest)], check=True)
    print("launchd agent restarted.")


def restart_windows_service() -> None:
    task_name = "FacturaAI"
    exists = subprocess.run(
        ["schtasks", "/query", "/tn", task_name],
        capture_output=True, text=True,
    ).returncode == 0
    if not exists:
        print(f'No scheduled task "{task_name}" found — restart with: python main.py')
        return
    subprocess.run(["schtasks", "/end", "/tn", task_name], check=False)
    subprocess.run(["schtasks", "/run", "/tn", task_name], check=True)
    print(f'Scheduled task "{task_name}" restarted.')


def main() -> None:
    print("=== FacturaAI 2.0 Update ===\n")

    pull_latest()

    py = ensure_venv()
    ensure_python_deps(py)
    check_tesseract()
    check_ghostscript()

    system = platform.system()
    if system == "Darwin":
        restart_macos_service()
    elif system == "Windows":
        restart_windows_service()
    else:
        print("Restart with: python main.py")

    print("\nDone.")


if __name__ == "__main__":
    main()
