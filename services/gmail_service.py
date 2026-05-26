import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders as email_encoders
from typing import Optional
from googleapiclient.discovery import build
from services.google_auth import get_credentials

ALTERATIONS_EMAIL = os.environ.get("ALTERATIONS_EMAIL", "alterations@433w34.com")


def _svc():
    return build("gmail", "v1", credentials=get_credentials())


# ── Sending ───────────────────────────────────────────────────────────────────

def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    from_alias: Optional[str] = None,
    reply_to: Optional[str] = None,
    attachments: Optional[list] = None,  # list of {filename, data: bytes, mime_type}
):
    """Send an email via Gmail API. Optionally attach files."""
    if attachments:
        msg = MIMEMultipart("mixed")
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(body, "html"))
        msg.attach(alt_part)
        for att in attachments:
            main_type, sub_type = (att.get("mime_type", "application/octet-stream") + "/x").split("/")[:2]
            part = MIMEBase(main_type, sub_type)
            part.set_payload(att["data"])
            email_encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=att["filename"])
            msg.attach(part)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "html"))

    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if reply_to:
        msg["Reply-To"] = reply_to

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    _svc().users().messages().send(userId="me", body={"raw": raw}).execute()


# ── Reading ───────────────────────────────────────────────────────────────────

def get_unread_architect_emails() -> list:
    """Return list of unread message IDs sent from known architect addresses."""
    addrs = []
    for addr in os.environ.get("MELONE_EMAILS", "").split(","):
        if addr.strip():
            addrs.append(addr.strip())
    cap = os.environ.get("CAPOBIANCO_EMAIL", "").strip()
    if cap:
        addrs.append(cap)

    if not addrs:
        return []

    svc = _svc()
    results = []
    for addr in addrs:
        resp = svc.users().messages().list(
            userId="me", q=f"from:{addr} is:unread", maxResults=20
        ).execute()
        results.extend(resp.get("messages", []))
    return results


def get_email_with_attachments(msg_id: str) -> dict:
    """
    Fetch a full email and extract text body + attachments.
    Returns: {id, subject, from, body_text, body_html, attachments: [{filename, data, mime_type}]}
    """
    svc = _svc()
    msg = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()

    headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
    subject = headers.get("subject", "")
    sender = headers.get("from", "")

    body_text = ""
    body_html = ""
    attachments = []

    def _decode(data: str) -> bytes:
        # Add padding if needed
        return base64.urlsafe_b64decode(data + "=" * (4 - len(data) % 4))

    def process_part(part):
        nonlocal body_text, body_html
        mime_type = part.get("mimeType", "")
        filename = part.get("filename", "")
        body_data = part.get("body", {})

        if filename and body_data.get("attachmentId"):
            att = svc.users().messages().attachments().get(
                userId="me", messageId=msg_id, id=body_data["attachmentId"]
            ).execute()
            attachments.append({
                "filename": filename,
                "data": _decode(att["data"]),
                "mime_type": mime_type or "application/octet-stream",
            })
        elif mime_type == "text/plain" and not filename:
            raw = body_data.get("data", "")
            if raw:
                body_text = _decode(raw).decode("utf-8", errors="replace")
        elif mime_type == "text/html" and not filename:
            raw = body_data.get("data", "")
            if raw:
                body_html = _decode(raw).decode("utf-8", errors="replace")

        for subpart in part.get("parts", []):
            process_part(subpart)

    process_part(msg["payload"])

    return {
        "id": msg_id,
        "subject": subject,
        "from": sender,
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
    }


def mark_as_read(msg_id: str):
    """Remove the UNREAD label so we don't reprocess this email."""
    _svc().users().messages().modify(
        userId="me",
        id=msg_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()
