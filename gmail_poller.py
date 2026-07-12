"""
Gmail API poller — downloads PDF attachments from matching emails
into inbox/gmail/ and marks them read (optional).
"""

import logging
import os
from pathlib import Path

from config.loader import get_config

log = logging.getLogger(__name__)


def _get_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    cfg = get_config()["gmail"]
    scopes = ["https://www.googleapis.com/auth/gmail.modify"]
    creds_file = cfg["credentials_file"]
    token_file = cfg["token_file"]

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
            # Cap the wait for the browser consent flow — an incomplete or
            # never-started auth must not hang the whole processing loop
            # (which would otherwise starve inbox/scan/ of every cycle
            # until someone finishes the Google sign-in).
            creds = flow.run_local_server(port=0, timeout_seconds=120)
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def poll_gmail() -> list[str]:
    """
    Download unread PDF attachments from Gmail.
    Returns list of saved file paths.
    """
    cfg = get_config()
    gmail_cfg = cfg.get("gmail", {})

    if not gmail_cfg.get("enabled", False):
        return []

    dest_dir = cfg["paths"]["inbox_gmail"]
    os.makedirs(dest_dir, exist_ok=True)
    saved = []

    try:
        service = _get_service()
        label = gmail_cfg.get("label_filter", "")
        query = "is:unread has:attachment filename:pdf"
        if label:
            query += f" label:{label}"

        response = service.users().messages().list(userId="me", q=query).execute()
        messages = response.get("messages", [])
        log.info("Gmail: %d unread messages with PDF attachments", len(messages))

        for msg_meta in messages:
            msg_id = msg_meta["id"]
            try:
                paths = _process_message(service, msg_id, dest_dir)
                saved.extend(paths)
                if gmail_cfg.get("mark_as_read", True):
                    service.users().messages().modify(
                        userId="me", id=msg_id,
                        body={"removeLabelIds": ["UNREAD"]},
                    ).execute()
            except Exception as e:
                log.error("Failed to process Gmail message %s: %s", msg_id, e)

    except Exception as e:
        log.error("Gmail poll failed: %s", e)

    return saved


def _process_message(service, msg_id: str, dest_dir: str) -> list[str]:
    import base64

    msg = service.users().messages().get(userId="me", id=msg_id).execute()
    saved = []

    def _walk_parts(parts):
        for part in parts:
            if part.get("parts"):
                _walk_parts(part["parts"])
                continue
            filename = part.get("filename", "")
            mime = part.get("mimeType", "")
            if not filename.lower().endswith(".pdf") and mime != "application/pdf":
                continue
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")
            if not attachment_id:
                data = body.get("data", "")
            else:
                att = service.users().messages().attachments().get(
                    userId="me", messageId=msg_id, id=attachment_id
                ).execute()
                data = att.get("data", "")

            if not data:
                continue

            pdf_bytes = base64.urlsafe_b64decode(data)
            safe_name = _safe_filename(filename or f"gmail_{msg_id}.pdf")
            dest = _unique_path(os.path.join(dest_dir, safe_name))
            with open(dest, "wb") as f:
                f.write(pdf_bytes)
            log.info("Gmail: saved attachment %s", dest)
            saved.append(dest)

    payload = msg.get("payload", {})
    if payload.get("parts"):
        _walk_parts(payload["parts"])
    return saved


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()


def _unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"
