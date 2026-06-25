"""
Bidirectional inbox processing for alterations@433w34.com.

Two routing directions, both matched by App ID in the subject line:

  Architect → Shareholder/GC
    Detected by: sender is a known architect address
    Action: Claude cover note + forward original PDF → shareholder/GC,
            upload to Drive, set status "Architect Review", log

  Shareholder/GC/Anyone → Architect
    Detected by: App ID in subject, sender is NOT an architect address,
                 application status is "Architect Review"
    Action: Forward original email + attachments → assigned architect,
            upload to Drive, log
    Note: matched on App ID only — no sender address whitelist,
          so contractor team changes / new colleagues are handled transparently

Emails with no recognisable App ID are left unread for manual review.
"""

import re
import io
import os
import logging

logger = logging.getLogger(__name__)

_SCOPE_FILENAME_RE = re.compile(
    r'(scope|sow|s\.o\.w|revised|updated|work.?order)', re.IGNORECASE
)

_APP_ID_RE = re.compile(r'ALT-\d{6}-[A-Z0-9]{5}')
_FOLDER_ID_RE = re.compile(r'/folders/([a-zA-Z0-9_-]+)')
_EMAIL_ADDR_RE = re.compile(r'[\w.+-]+@[\w-]+\.[a-zA-Z]+')

ALTERATIONS_EMAIL = os.environ.get("ALTERATIONS_EMAIL", "alterations@433w34.com")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")


def _extract_app_id(text: str):
    m = _APP_ID_RE.search(text or "")
    return m.group(0) if m else None


def _extract_sender_email(from_header: str) -> str:
    """Pull bare email address from 'Display Name <addr>' or plain addr."""
    m = re.search(r'<([^>]+)>', from_header)
    if m:
        return m.group(1).lower().strip()
    addrs = _EMAIL_ADDR_RE.findall(from_header)
    return addrs[0].lower() if addrs else from_header.lower().strip()


def _folder_id_from_url(url: str):
    m = _FOLDER_ID_RE.search(url or "")
    return m.group(1) if m else None


def _strip_html(html: str) -> str:
    return re.sub(r'<[^>]+>', ' ', html or "")


def _get_architect_email(architect_name: str) -> str:
    """Return the to-address for the named architect."""
    if architect_name == "Melone":
        return ",".join(
            e.strip() for e in os.environ.get("MELONE_EMAILS", "").split(",") if e.strip()
        )
    return os.environ.get("CAPOBIANCO_EMAIL", "")


def _upload_attachments_to_drive(app: dict, attachments: list):
    """Upload a list of attachment dicts to the application's Drive folder."""
    if not attachments:
        return
    from services.drive_service import upload_bytes
    folder_id = _folder_id_from_url(app.get("drive_folder_url", ""))
    if not folder_id:
        return
    for att in attachments:
        try:
            upload_bytes(folder_id, att["filename"], att["data"], att["mime_type"])
        except Exception as e:
            logger.error(f"Drive upload failed for {att['filename']}: {e}")


# ── Direction 1: Architect → Shareholder/GC ──────────────────────────────────

def _process_architect_to_shareholder(email: dict, app: dict):
    from services.gmail_service import send_email, mark_as_read
    from services.sheets_service import update_application_field, log_event
    from services.claude_service import summarize_architect_report, classify_architect_report
    from services.email_templates import architect_review_forward_email, board_architect_recommendation_email

    sender = email["from"]
    app_id = app["app_id"]
    report_text = email["body_text"] or _strip_html(email["body_html"])

    # Step 1: Classify — is this a final recommendation or mid-review?
    classification = {"is_final": False, "recommendation": "more_info"}
    try:
        classification = classify_architect_report(report_text, app_id)
    except Exception as e:
        logger.error(f"Claude classification failed for {app_id}: {e}")

    is_final = classification.get("is_final", False)
    recommendation = classification.get("recommendation", "more_info")

    # Step 2: Determine round label for cover note and subject line
    _round_label_map = {
        "final": "Final Recommendation",
        "follow-up": "Follow-Up Comments",
        "initial": "Initial Comments",
    }
    if is_final:
        round_label = "final"
    elif app.get("status") != "Architect Review":
        round_label = "initial"
    else:
        round_label = "follow-up"
    round_display = _round_label_map[round_label]

    # Step 3: Claude cover note (navigational aid — original PDF always attached)
    cover_note = None
    try:
        cover_note = summarize_architect_report(report_text, app, round_label)
    except Exception as e:
        logger.error(f"Claude summary failed for {app_id}: {e}")

    # Step 4: Forward to shareholder/GC (always, regardless of whether final)
    body = architect_review_forward_email(app, cover_note, round_label)
    cc_parts = [p for p in [app.get("gc_email"), ADMIN_EMAIL] if p]

    send_email(
        to=app["shareholder_email"],
        cc=",".join(cc_parts) if cc_parts else None,
        subject=f"Architect Review ({round_display}) — Apt {app['apartment']} | {app_id}",
        body=body,
        reply_to=ALTERATIONS_EMAIL,
        attachments=email["attachments"] or None,
    )

    _upload_attachments_to_drive(app, email["attachments"])
    mark_as_read(email["id"])

    att_names = ", ".join(a["filename"] for a in email["attachments"]) if email["attachments"] else "no attachments"

    if is_final:
        # Final recommendation: alert the board, advance status to "Awaiting Board Vote"
        try:
            board_body = board_architect_recommendation_email(app, recommendation, cover_note)
            send_email(
                to=ADMIN_EMAIL,
                subject=f"[ACTION REQUIRED] Architect Review Complete — Apt {app['apartment']} | {app_id}",
                body=board_body,
                reply_to=ALTERATIONS_EMAIL,
                attachments=email["attachments"] or None,
            )
        except Exception as e:
            logger.error(f"Board alert send failed for {app_id}: {e}")

        update_application_field(app_id, "status", "Awaiting Board Vote")
        log_event(app_id, "Status: Awaiting Board Vote",
                  f"Architect final recommendation ({recommendation}) received from {sender}. "
                  f"{att_names}. Forwarded to shareholder and board alerted.",
                  actor="architect", apartment=app.get("apartment", ""))
        return (f"Apt {app['apartment']} ({app_id}) — architect final recommendation "
                f"({recommendation}); board alerted, status → Awaiting Board Vote")

    else:
        # Mid-review: keep status as "Architect Review"
        update_application_field(app_id, "status", "Architect Review")
        log_event(app_id, f"Status: Architect Review ({round_display})",
                  f"Report received from {sender}. {att_names}. "
                  f"Forwarded to {app['shareholder_email']}"
                  + (f" and {app.get('gc_email')}" if app.get('gc_email') else "") + ".",
                  actor="architect", apartment=app.get("apartment", ""))
        return f"Apt {app['apartment']} ({app_id}) — {round_label} architect report forwarded to shareholder"


# ── PDF text extraction ───────────────────────────────────────────────────────

def _extract_pdf_text(data: bytes) -> str:
    """Extract plain text from a PDF attachment (bytes). Returns '' on failure."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as e:
        logger.debug(f"PDF text extraction failed: {e}")
        return ""


def _find_scope_attachment(attachments: list) -> tuple[str, str]:
    """
    Look for a scope-of-work document in the attachment list.
    Returns (filename, extracted_text) for the first match, or ("", "") if none found.
    Strategy: prefer filename signals; fall back to scanning PDF text for SOW language.
    """
    # Pass 1: filename signals
    for att in attachments:
        if att.get("mime_type") != "application/pdf":
            continue
        if _SCOPE_FILENAME_RE.search(att.get("filename", "")):
            text = _extract_pdf_text(att["data"])
            if text:
                return att["filename"], text

    # Pass 2: scan all PDFs for SOW content markers
    sow_markers = ("scope of work", "scope of works", "reconstruction:", "removal:", "install ")
    for att in attachments:
        if att.get("mime_type") != "application/pdf":
            continue
        text = _extract_pdf_text(att["data"])
        text_lower = text.lower()
        if sum(1 for m in sow_markers if m in text_lower) >= 2:
            return att["filename"], text

    return "", ""


# ── Direction 2: Shareholder/GC → Architect ──────────────────────────────────

def _process_shareholder_to_architect(email: dict, app: dict):
    from services.gmail_service import send_email, mark_as_read
    from services.sheets_service import log_event
    from services.email_templates import shareholder_response_forward_email, scope_change_alert_email

    sender = email["from"]
    sender_email = _extract_sender_email(sender)
    app_id = app["app_id"]

    architect_name = app.get("architect_assigned", "")
    architect_email = _get_architect_email(architect_name)
    if not architect_email:
        logger.warning(f"No architect email found for {app_id} — cannot forward response")
        return None

    # ── Scope change detection ────────────────────────────────────────────────
    scope_detection = None
    if email["attachments"]:
        scope_filename, scope_text = _find_scope_attachment(email["attachments"])
        if scope_filename and scope_text:
            try:
                from services.claude_service import detect_scope_change
                original_scope = app.get("scope_description", "")
                scope_detection = detect_scope_change(original_scope, scope_text, app_id)
                logger.info(f"Scope detection for {app_id}: is_scope={scope_detection.get('is_scope_document')}, board_alert={scope_detection.get('board_alert')}")
            except Exception as e:
                logger.error(f"Scope change detection failed for {app_id}: {e}")

    # ── Forward to architect (always) ─────────────────────────────────────────
    body = shareholder_response_forward_email(app, sender, len(email["attachments"]))

    send_email(
        to=architect_email,
        cc=ADMIN_EMAIL or None,
        subject=f"Shareholder Response — Apt {app['apartment']} | {app_id}",
        body=body,
        reply_to=ALTERATIONS_EMAIL,
        attachments=email["attachments"] or None,
    )

    _upload_attachments_to_drive(app, email["attachments"])
    mark_as_read(email["id"])

    att_names = ", ".join(a["filename"] for a in email["attachments"]) if email["attachments"] else "no attachments"

    # ── Board alert if material scope additions found ──────────────────────────
    if scope_detection and scope_detection.get("is_scope_document"):
        has_additions = scope_detection.get("has_material_additions") or bool(scope_detection.get("additions"))
        if has_additions and ADMIN_EMAIL:
            try:
                alert_body = scope_change_alert_email(app, scope_detection, sender_email, att_names)
                alert_subject = (
                    f"[SCOPE CHANGE] Revised scope submitted — Apt {app['apartment']} | {app_id}"
                    if scope_detection.get("board_alert")
                    else f"Revised scope submitted — Apt {app['apartment']} | {app_id}"
                )
                send_email(
                    to=ADMIN_EMAIL,
                    subject=alert_subject,
                    body=alert_body,
                    reply_to=ALTERATIONS_EMAIL,
                )
            except Exception as e:
                logger.error(f"Scope change alert send failed for {app_id}: {e}")

        change_summary = scope_detection.get("summary", "")
        additions = scope_detection.get("additions", [])
        expansion_count = sum(1 for a in additions if a.get("type") == "expansion")
        log_event(
            app_id,
            "Scope Change Detected" if scope_detection.get("board_alert") else "Revised Scope Submitted",
            f"Revised scope document '{scope_filename}' submitted by {sender_email}. "
            f"{expansion_count} expansion addition(s) flagged. {change_summary}",
            actor="shareholder", apartment=app.get("apartment", ""),
        )

    log_event(app_id, "Response: Shareholder → Architect",
              f"Response from {sender_email} forwarded to {architect_name} ({architect_email}). {att_names}.",
              actor="shareholder", apartment=app.get("apartment", ""))

    scope_note = " (scope change detected)" if scope_detection and scope_detection.get("board_alert") else ""
    return f"Apt {app['apartment']} ({app_id}) — shareholder response forwarded to {architect_name}{scope_note}"


# ── Main entry point ──────────────────────────────────────────────────────────

def process_inbox():
    """
    Check inbox for all unread emails with App IDs and route them.
    Returns (processed: list[str], errors: list[str]).
    Safe to call from background thread or request context.
    """
    from services.gmail_service import get_unread_application_emails, get_email_with_attachments, get_architect_addresses

    architect_addresses = get_architect_addresses()
    processed = []
    errors = []

    try:
        messages = get_unread_application_emails()
    except Exception as e:
        logger.error(f"Inbox fetch failed: {e}")
        return [], [f"Could not read inbox: {e}"]

    for msg_ref in messages:
        msg_id = msg_ref["id"]
        try:
            email = get_email_with_attachments(msg_id)
            subject = email["subject"]
            sender_email = _extract_sender_email(email["from"])

            # Match on App ID — not on sender address
            app_id = _extract_app_id(subject) or _extract_app_id(email["body_text"])
            if not app_id:
                logger.warning(f"No App ID in email from {sender_email} (subject: {subject[:80]}). Left unread.")
                errors.append(f"Email from {sender_email} — no App ID found in subject. Left unread for manual review.")
                continue

            from services.sheets_service import get_application
            app = get_application(app_id)
            if not app:
                logger.warning(f"App ID {app_id} not found in sheet. Left unread.")
                errors.append(f"Email references {app_id} — not found in sheet. Left unread.")
                continue

            if sender_email in architect_addresses:
                # Architect → Shareholder
                result = _process_architect_to_shareholder(email, app)
                if result:
                    processed.append(result)

            elif app.get("status") == "Architect Review" and app.get("architect_assigned"):
                # Shareholder/GC/anyone → Architect
                result = _process_shareholder_to_architect(email, app)
                if result:
                    processed.append(result)
                elif result is None:
                    errors.append(f"App {app_id}: response received but no architect assigned — left unread.")

            else:
                # App ID found but not in a state where we can route it
                # (e.g. someone replies after approval) — leave unread for Jeremy
                logger.info(f"Email for {app_id} in status '{app.get('status')}' — not auto-routed, left unread.")

        except Exception as e:
            logger.error(f"Error processing message {msg_id}: {e}")
            errors.append(f"Error processing a message: {e}")

    return processed, errors


# Keep old name as alias so existing app.py import still works during transition
process_architect_inbox = process_inbox
