import os
import yaml
from pathlib import Path


_config = None


def load_config(path: str = None) -> dict:
    global _config
    if _config is not None:
        return _config

    if path is None:
        base = Path(__file__).parent.parent
        path = base / "config" / "config.yaml"
        if not path.exists():
            path = base / "config" / "config.example.yaml"

    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    _config = _expand_paths(raw)
    return _config


def get_config() -> dict:
    if _config is None:
        return load_config()
    return _config


def _expand_paths(obj):
    if isinstance(obj, dict):
        return {k: _expand_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_paths(i) for i in obj]
    if isinstance(obj, str) and obj.startswith("~"):
        return str(Path(obj).expanduser())
    return obj


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
