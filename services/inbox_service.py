"""
Architect inbox processing.

Checks alterations@433w34.com for unread emails from known architect addresses.
For each matching email:
  - Extracts the App ID from the subject line
  - Downloads any PDF attachments
  - Has Claude write a brief cover note (navigational aid only)
  - Forwards to shareholder + GC with original attachments intact
  - Uploads attachments to the application's Drive folder
  - Updates application status to "Architect Review"
  - Marks the email as read so it isn't reprocessed
"""

import re
import os
import logging

logger = logging.getLogger(__name__)

# App ID pattern: ALT-YYYYMM-XXXXX
_APP_ID_RE = re.compile(r'ALT-\d{6}-[A-Z0-9]{5}')
# Drive folder ID from webViewLink URL
_FOLDER_ID_RE = re.compile(r'/folders/([a-zA-Z0-9_-]+)')

ALTERATIONS_EMAIL = os.environ.get("ALTERATIONS_EMAIL", "alterations@433w34.com")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")


def _extract_app_id(text: str):
    m = _APP_ID_RE.search(text or "")
    return m.group(0) if m else None


def _folder_id_from_url(url: str):
    m = _FOLDER_ID_RE.search(url or "")
    return m.group(1) if m else None


def _strip_html(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html or "")


def process_architect_inbox():
    """
    Check inbox for unread architect emails and process each one.
    Returns (processed: list[str], errors: list[str]) for display in the admin panel.
    Safe to call from a background thread or request context.
    """
    from services.gmail_service import (
        get_unread_architect_emails, get_email_with_attachments, mark_as_read, send_email
    )
    from services.sheets_service import get_application, update_application_field
    from services.drive_service import upload_bytes
    from services.claude_service import summarize_architect_report
    from services.email_templates import architect_review_forward_email

    processed = []
    errors = []

    try:
        messages = get_unread_architect_emails()
    except Exception as e:
        logger.error(f"Inbox fetch failed: {e}")
        return [], [f"Could not read inbox: {e}"]

    for msg_ref in messages:
        msg_id = msg_ref["id"]
        try:
            email = get_email_with_attachments(msg_id)
            subject = email["subject"]
            sender = email["from"]

            # Find App ID — try subject first, then body
            app_id = _extract_app_id(subject) or _extract_app_id(email["body_text"])
            if not app_id:
                msg = f"Email from {sender} — no App ID found (subject: {subject[:80]}). Left unread for manual review."
                logger.warning(msg)
                errors.append(msg)
                continue  # Leave unread so Jeremy sees it

            app = get_application(app_id)
            if not app:
                msg = f"Email references {app_id} but not found in sheet. Left unread."
                logger.warning(msg)
                errors.append(msg)
                continue

            # First round = status not yet "Architect Review"; otherwise it's a follow-up
            round_label = "initial" if app.get("status") != "Architect Review" else "follow-up"

            # Get readable text from the email body
            report_text = email["body_text"] or _strip_html(email["body_html"])

            # Claude cover note — gracefully degrade if it fails
            cover_note = None
            try:
                cover_note = summarize_architect_report(report_text, app, round_label)
            except Exception as e:
                logger.error(f"Claude summary failed for {app_id}: {e}")

            # Build forwarding email
            forward_body = architect_review_forward_email(app, cover_note, round_label)

            # Recipients
            cc_parts = [p for p in [app.get("gc_email"), ADMIN_EMAIL] if p]

            send_email(
                to=app["shareholder_email"],
                cc=",".join(cc_parts) if cc_parts else None,
                subject=f"Architect Review Comments ({round_label.title()}) — Apt {app['apartment']} | {app_id}",
                body=forward_body,
                reply_to=ALTERATIONS_EMAIL,
                attachments=email["attachments"] if email["attachments"] else None,
            )

            # Upload attachments to Drive
            folder_url = app.get("drive_folder_url", "")
            folder_id = _folder_id_from_url(folder_url)
            if folder_id and email["attachments"]:
                for att in email["attachments"]:
                    try:
                        upload_bytes(folder_id, att["filename"], att["data"], att["mime_type"])
                    except Exception as e:
                        logger.error(f"Drive upload failed for {att['filename']}: {e}")

            # Update status + mark email as read
            update_application_field(app_id, "status", "Architect Review")
            mark_as_read(msg_id)

            # Log the event
            from services.sheets_service import log_event
            att_names = ", ".join(a["filename"] for a in email["attachments"]) if email["attachments"] else "no attachments"
            log_event(app_id, f"Status: Architect Review ({round_label.title()})",
                      f"Architect report received from {sender}. {att_names}. "
                      f"Forwarded to {app['shareholder_email']}"
                      + (f" and {app.get('gc_email')}" if app.get('gc_email') else "")
                      + f". Uploaded to Drive.",
                      actor="architect", apartment=app.get("apartment", ""))

            summary = f"Apt {app['apartment']} ({app_id}) — {round_label} review comments forwarded to {app['shareholder_email']}"
            processed.append(summary)
            logger.info(f"Processed architect email for {app_id}")

        except Exception as e:
            logger.error(f"Error processing message {msg_id}: {e}")
            errors.append(f"Error processing a message: {e}")

    return processed, errors
