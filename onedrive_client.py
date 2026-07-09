"""
OneDrive archive destination via Microsoft Graph.

Delegated auth via MSAL's public-client interactive flow: one browser
consent screen the first time, then a cached refresh token reused silently
after that (mirrors the Gmail OAuth pattern v1 already uses). Uploads mirror
the same {supplier} {date} {amount}.pdf naming and YYYY/MM/ folder structure
v1 used for local archiving, just rooted under onedrive.root_folder.

No-ops entirely unless config.processing.output_destination is "onedrive"
or "both" and onedrive.enabled is true — processor.py always archives
locally first regardless, so this is additive, not a replacement path.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.loader import get_config

log = logging.getLogger(__name__)

GRAPH_SCOPES = ["Files.ReadWrite"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
# Graph's simple PUT-to-/content upload only supports files up to 4 MiB;
# invoice PDFs are almost always well under this. Anything larger would
# need a resumable upload session, which isn't implemented here.
MAX_SIMPLE_UPLOAD_BYTES = 4 * 1024 * 1024

_app = None       # msal.PublicClientApplication, built lazily
_cache_path = None  # Path, set alongside _app


def _onedrive_config() -> dict:
    return get_config().get("onedrive", {})


def _enabled() -> bool:
    cfg = _onedrive_config()
    dest = get_config().get("processing", {}).get("output_destination", "local")
    return bool(cfg.get("enabled")) and dest in ("onedrive", "both")


def _get_app():
    global _app, _cache_path
    if _app is not None:
        return _app

    import msal

    cfg = _onedrive_config()
    client_id = cfg.get("client_id")
    tenant_id = cfg.get("tenant_id") or "common"
    if not client_id:
        raise RuntimeError("onedrive.client_id is not configured")

    cache = msal.SerializableTokenCache()
    _cache_path = Path(cfg.get("token_cache_file", ""))
    if _cache_path and _cache_path.exists():
        cache.deserialize(_cache_path.read_text(encoding="utf-8"))

    _app = msal.PublicClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )
    return _app


def _save_cache():
    if _app is None or not _cache_path:
        return
    cache = _app.token_cache
    if cache.has_state_changed:
        _cache_path.parent.mkdir(parents=True, exist_ok=True)
        _cache_path.write_text(cache.serialize(), encoding="utf-8")


def _get_token() -> str:
    app = _get_app()
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
    if not result:
        log.info("No cached OneDrive token — opening browser for one-time sign-in")
        result = app.acquire_token_interactive(scopes=GRAPH_SCOPES)
    _save_cache()
    if not result or "access_token" not in result:
        raise RuntimeError(f"OneDrive auth failed: {(result or {}).get('error_description', result)}")
    return result["access_token"]


def upload_invoice(local_path: str, date_str: Optional[str]) -> Optional[str]:
    """Upload an already-locally-archived file to OneDrive under
    {root_folder}/YYYY/MM/{filename}. No-op if OneDrive isn't enabled.
    Returns the Graph item path on success, raises on failure (the caller
    logs and continues — a failed upload never blocks local archiving)."""
    if not _enabled():
        return None

    import requests

    size = Path(local_path).stat().st_size
    if size > MAX_SIMPLE_UPLOAD_BYTES:
        raise RuntimeError(
            f"{local_path} is {size} bytes, over the {MAX_SIMPLE_UPLOAD_BYTES}-byte "
            "simple-upload limit (resumable upload sessions aren't implemented)"
        )

    cfg = _onedrive_config()
    root = cfg.get("root_folder", "FacturaAI").strip("/")
    try:
        dt = datetime.strptime((date_str or "")[:10], "%Y-%m-%d")
        subpath = f"{dt.year:04d}/{dt.month:02d}"
    except (ValueError, TypeError):
        subpath = "unknown"

    filename = Path(local_path).name
    graph_path = f"{root}/{subpath}/{filename}"

    token = _get_token()
    url = f"{GRAPH_BASE}/me/drive/root:/{graph_path}:/content"
    with open(local_path, "rb") as f:
        data = f.read()

    resp = requests.put(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/pdf"},
        data=data,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"OneDrive upload failed ({resp.status_code}): {resp.text[:300]}")

    log.info("Uploaded to OneDrive: %s", graph_path)
    return graph_path
