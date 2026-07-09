#!/usr/bin/env python3
"""
health_check.py — prints a status report for the FacturaAI agent.
Run from the project root: python3 scripts/health_check.py
"""

import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import load_config
import db
from retention import get_retention_warnings, years_summary, RETENTION_YEARS

SEP = "-" * 60


def fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def agent_running() -> bool:
    """Best-effort check for the registered background service. Returns
    None (not False) when there's no service integration to check on this
    OS/setup at all — distinct from a confirmed-not-running service."""
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.check_output(["launchctl", "list"], text=True)
            return "com.facturaai.agent" in out
        if system == "Windows":
            out = subprocess.check_output(
                ["schtasks", "/query", "/tn", "FacturaAI"],
                text=True, stderr=subprocess.DEVNULL,
            )
            return "Running" in out
    except Exception:
        return False
    return None


def heartbeat_age(last_seen: str) -> str:
    if not last_seen:
        return "NEVER"
    try:
        ts = datetime.strptime(last_seen, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        mins = int(delta.total_seconds() // 60)
        return f"{mins} min ago"
    except ValueError:
        return last_seen


def main():
    cfg = load_config()
    db_file = cfg["paths"]["db"]
    log_dir = cfg["paths"]["logs"]

    print(SEP)
    print("  FacturaAI Health Check")
    print(SEP)

    # Service status (launchd on macOS, Task Scheduler on Windows, or none
    # registered — e.g. running main.py manually / via a plain cron job)
    running = agent_running()
    status = "RUNNING" if running else ("STOPPED" if running is False else "no service registered")
    print(f"  Background service: {status}")

    # Heartbeat
    last_seen = db.get_heartbeat()
    print(f"  Last heartbeat:   {last_seen or '—'}  ({heartbeat_age(last_seen)})")

    # Last cycle
    cycle = db.get_last_cycle()
    if cycle:
        print(f"  Last cycle #{cycle.get('cycle_number','?')}:")
        print(f"    Found:          {cycle.get('files_found', 0)}")
        print(f"    Processed:      {cycle.get('files_processed', 0)}")
        print(f"    Failed:         {cycle.get('files_failed', 0)}")
        print(f"    Skipped:        {cycle.get('files_skipped', 0)}")
        print(f"    Duration:       {cycle.get('duration_seconds', 0):.1f}s")
    else:
        print("  Last cycle:       no cycles recorded yet")

    # Review queue
    queue = db.get_review_queue()
    print(f"  Manual review:    {len(queue)} invoice(s) pending")

    # VAT / spike flags
    with db.transaction() as conn:
        vat_flagged   = conn.execute("SELECT COUNT(*) FROM invoices WHERE vat_flag = 1").fetchone()[0]
        spike_flagged = conn.execute("SELECT COUNT(*) FROM invoices WHERE spike_flag = 1").fetchone()[0]
    print(f"  VAT flags:        {vat_flagged}")
    print(f"  Spike flags:      {spike_flagged}")

    # File sizes
    if os.path.exists(db_file):
        print(f"  DB size:          {fmt_size(os.path.getsize(db_file))}")
    else:
        print("  DB size:          (not created yet)")

    total_log = sum(f.stat().st_size for f in Path(log_dir).glob("*.log")) if os.path.isdir(log_dir) else 0
    print(f"  Logs size:        {fmt_size(total_log)}")

    # -----------------------------------------------------------------------
    # Retention summary
    # -----------------------------------------------------------------------
    print()
    print(SEP)
    print(f"  Retención Legal  (conservar {RETENTION_YEARS} años — C.Com art. 30)")
    print(SEP)

    summary = years_summary()
    if summary:
        print(f"  {'Año':<6}  {'Facturas':>8}  {'Total €':>12}  {'Conservar hasta':>16}")
        for row in summary:
            year  = row.get("year", "?")
            count = row.get("count", 0)
            total = row.get("total") or 0
            keep_until = int(year) + RETENTION_YEARS if str(year).isdigit() else "?"
            print(f"  {year:<6}  {count:>8}  {total:>12.2f}  {str(keep_until):>16}")
    else:
        print("  Sin facturas registradas todavía.")

    warnings = get_retention_warnings()
    if warnings:
        print()
        print(f"  *** AVISO: {len(warnings)} factura(s) próximas al límite de retención ***")
        for w in warnings[:5]:
            print(f"    #{w['id']}  {w['date']}  {w['supplier']}  {w['invoice_number']}")
        if len(warnings) > 5:
            print(f"    ... y {len(warnings) - 5} más")

    print(SEP)


if __name__ == "__main__":
    main()
