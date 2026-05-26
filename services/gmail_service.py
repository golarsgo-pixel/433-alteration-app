import os
import base64
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from services.google_auth import get_credentials

ALTERATIONS_EMAIL = os.environ.get("ALTERATIONS_EMAIL", "alterations@433w34.com")


def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    from_alias: Optional[str] = None,
    reply_to: Optional[str] = None,
):
    """Send an email via Gmail API using the board's OAuth credentials."""
    creds = get_credentials()
    svc = build("gmail", "v1", credentials=creds)

    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
