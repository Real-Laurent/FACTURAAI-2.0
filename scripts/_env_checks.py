"""
Shared, idempotent environment checks used by both install.py and update.py —
mirrors the check-before-install pattern v1's install_launchagent.sh /
update.sh already used (skip venv creation if it exists, skip brew installs
if the binary is already on PATH, etc.), made cross-platform.
"""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"


def venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python3"


def ensure_venv() -> Path:
    py = venv_python()
    if py.exists():
        print(f"venv already exists at {VENV_DIR}")
        return py
    print(f"Creating venv at {VENV_DIR} ...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    return py


def _missing_requirements(py: Path) -> list[str]:
    """Return the requirements.txt lines whose package isn't already
    importable in the venv — pip install itself is idempotent, but this
    gives an explicit before-you-install picture."""
    req_file = PROJECT_ROOT / "requirements.txt"
    lines = [
        line.strip() for line in req_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    check_script = (
        "import importlib.metadata as m, sys\n"
        "for spec in sys.argv[1:]:\n"
        "    name = spec.split('>=')[0].split('==')[0].strip()\n"
        "    try:\n"
        "        m.version(name)\n"
        "    except m.PackageNotFoundError:\n"
        "        print(spec)\n"
    )
    result = subprocess.run(
        [str(py), "-c", check_script, *lines],
        capture_output=True, text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def ensure_python_deps(py: Path) -> None:
    missing = _missing_requirements(py)
    if not missing:
        print("All Python dependencies already satisfied.")
        return
    print(f"Installing {len(missing)} missing dependency(ies): {', '.join(missing)}")
    subprocess.run([str(py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"], check=True)
    subprocess.run([str(py), "-m", "pip", "install", "--quiet"] + missing, check=True)
    print("Dependencies installed.")


def check_tesseract() -> None:
    if shutil.which("tesseract"):
        print("Tesseract: found on PATH.")
        return

    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            configured = cfg.get("processing", {}).get("ocr_tesseract_dir", "")
            if configured and (Path(configured) / "tesseract.exe").exists():
                print(f"Tesseract: found via config.processing.ocr_tesseract_dir ({configured}).")
                return
        except Exception:
            pass

    system = platform.system()
    if system == "Darwin":
        if shutil.which("brew"):
            print("Tesseract not found — installing via Homebrew...")
            subprocess.run(["brew", "install", "tesseract", "tesseract-lang"], check=True)
        else:
            print("Tesseract not found and Homebrew isn't installed.")
            print("  Install Homebrew from https://brew.sh, then: brew install tesseract tesseract-lang")
    else:
        print("Tesseract not found.")
        print("  Windows: install from https://github.com/UB-Mannheim/tesseract/wiki, then set")
        print("  processing.ocr_tesseract_dir in config.yaml to the install folder.")
        print("  Linux: install via your package manager (e.g. apt install tesseract-ocr).")


def check_ghostscript() -> None:
    if shutil.which("gs") or shutil.which("gswin64c"):
        print("Ghostscript: found on PATH.")
        return

    system = platform.system()
    if system == "Darwin":
        if shutil.which("brew"):
            print("Ghostscript not found — installing via Homebrew...")
            subprocess.run(["brew", "install", "ghostscript"], check=True)
        else:
            print("Ghostscript not found and Homebrew isn't installed.")
            print("  Install Homebrew from https://brew.sh, then: brew install ghostscript")
    else:
        print("Ghostscript not found (required by ocrmypdf for scanned-PDF OCR).")
        print("  Windows: install from https://ghostscript.com/releases/gsdnld.html")
        print("  Linux: install via your package manager (e.g. apt install ghostscript).")


def ensure_directories() -> None:
    from config.loader import ensure_dirs, load_config
    load_config()
    ensure_dirs()
    print("Directory tree ready.")


def ensure_config_yaml() -> None:
    example = PROJECT_ROOT / "config" / "config.example.yaml"
    dest = PROJECT_ROOT / "config" / "config.yaml"
    if dest.exists():
        print("config.yaml already exists — leaving it as-is.")
        return
    dest.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Created {dest} — edit it to enable Gmail/OneDrive/AI as needed.")


def is_git_repo() -> bool:
    return (PROJECT_ROOT / ".git").is_dir()
