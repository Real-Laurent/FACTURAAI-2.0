import os
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

_config = None

# (section, key) pairs that hold filesystem paths and must resolve relative
# to the project root — not the process's current working directory, which
# varies depending on how FacturaAI is launched (double-click, Task
# Scheduler, a shell in some other folder, etc.).
_PATH_KEYS = [
    ("paths", "inbox_scan"), ("paths", "inbox_gmail"), ("paths", "output"),
    ("paths", "manual_review"), ("paths", "rejected"), ("paths", "logs"),
    ("paths", "db"), ("paths", "exports"),
    ("gmail", "credentials_file"), ("gmail", "token_file"),
    ("onedrive", "client_secret_file"), ("onedrive", "token_cache_file"),
]


def load_config(path: str = None) -> dict:
    global _config
    if _config is not None:
        return _config

    if path is None:
        path = PROJECT_ROOT / "config" / "config.yaml"
        if not path.exists():
            path = PROJECT_ROOT / "config" / "config.example.yaml"

    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    _config = _resolve_config_paths(raw)
    return _config


def get_config() -> dict:
    if _config is None:
        return load_config()
    return _config


def _resolve_path(value: str) -> str:
    """Expand ~, or resolve a relative path against the project root."""
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return str(p)


def _resolve_config_paths(cfg: dict) -> dict:
    for section, key in _PATH_KEYS:
        section_cfg = cfg.get(section)
        if isinstance(section_cfg, dict) and section_cfg.get(key):
            section_cfg[key] = _resolve_path(section_cfg[key])
    return cfg


def ensure_dirs():
    cfg = get_config()
    paths_cfg = cfg.get("paths", {})
    dirs = [
        paths_cfg.get("inbox_scan"),
        paths_cfg.get("inbox_gmail"),
        paths_cfg.get("manual_review"),
        paths_cfg.get("rejected"),
        paths_cfg.get("logs"),
        str(Path(paths_cfg.get("db", "")).parent),
        str(Path(paths_cfg.get("exports", "")).parent) if paths_cfg.get("exports") else None,
    ]
    for d in dirs:
        if d:
            os.makedirs(d, exist_ok=True)
