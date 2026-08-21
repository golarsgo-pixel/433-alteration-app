import os
import uuid
import json
import secrets
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)
from dotenv import load_dotenv
from services.google_auth import require_board_login, get_auth_url, handle_callback
from services.sheets_service import append_application, update_application_field, update_application_fields, get_all_applications, get_application, get_application_log, log_event, get_settings, save_settings, write_vote_tokens, record_vote, get_votes_for_app, get_pending_vote_rows, lookup_vote_token
from services.gmail_service import send_email
from services.claude_service import review_application
from services.email_templates import (
    receipt_email, board_alert_email, eddie_new_submission_email,
    architect_notification_email, architect_package_email,
    approval_email, eddie_approval_email, neighbor_letter_email,
    vote_invitation_email, vote_reminder_email, vote_threshold_email, changes_required_email,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

BOARD_EMAIL = os.environ["BOARD_EMAIL"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ALTERATIONS_EMAIL = os.environ["ALTERATIONS_EMAIL"]
APP_URL = os.environ.get("APP_URL", "https://four33-alteration-app.onrender.com")

CRON_SECRET = os.environ.get("CRON_SECRET", "")
VOTE_THRESHOLD = 4

def _parse_engineers(settings: dict) -> list:
    import json as _json
    raw = settings.get("engineers_json", "")
    if raw:
        try:
            return _json.loads(raw)
        except (ValueError, TypeError):
            pass
    # Fallback to legacy individual keys
    result = []
    for key_k, label_k, emails_k in [
        ("engineer_1_key", "engineer_1_label", "engineer_1_emails"),
        ("engineer_2_key", "engineer_2_label", "engineer_2_email"),
    ]:
        k = settings.get(key_k, "")
        if k:
            result.append({"key": k, "label": settings.get(label_k, k), "emails": settings.get(emails_k, "")})
    return result


def _engineer_email(settings: dict, engineer_key: str) -> str:
    for eng in _parse_engineers(settings):
        if eng.get("key") == engineer_key:
            return eng.get("emails", "").strip()
    return ""


@app.template_filter('comma')
def comma_filter(value):
    try:
        return f"{int(float(str(value).replace(',', '').replace('$', ''))):,}"
    except (ValueError, TypeError):
        return value

# ── Public routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


def _post_submit_background(app_id, data, uploaded_files):
    """
    Runs in a daemon thread after the application is saved and the user
    has already been redirected. Drive uploads, Claude review, and all
    emails happen here so the submission request completes in ~1 second.
    If the process restarts mid-thread, the application row is already in
    Sheets and recoverable from the admin dashboard.
    """
    from services.drive_service import create_application_folder, upload_bytes

    # Step 1: Drive — create folder and upload all attached files
    folder_url = ""
    try:
        folder_id, folder_url = create_application_folder(app_id, data["apartment"])
        for f in uploaded_files:
            upload_bytes(folder_id, f["filename"], f["data"], f["content_type"])
        update_application_field(app_id, "drive_folder_url", folder_url)
        data["drive_folder_url"] = folder_url
    except Exception as e:
        app.logger.error(f"[{app_id}] Drive upload failed: {e}")

    # Step 2: Claude AI review
    try:
        review = review_application(data)
        ai_summary = review.get("summary", "")
        riser = "yes" if review.get("riser_risk") else "no"
        update_application_fields(app_id, {
            "ai_review_summary": ai_summary,
            "riser_flag": riser,
        })
        data["ai_review_summary"] = ai_summary
        data["riser_flag"] = riser
    except Exception as e:
        app.logger.error(f"[{app_id}] Claude review failed: {e}")
        data.setdefault("ai_review_summary", "Automated review unavailable — please review manually.")

    # Step 3: Emails — sent after Claude so board alert includes the review summary
    try:
        send_email(
            to=data["shareholder_email"],
            cc=data["gc_email"] if data["gc_email"] else None,
            subject=f"Application Received — Apt {data['apartment']} | {app_id}",
            body=receipt_email(data),
            from_alias=ALTERATIONS_EMAIL,
        )
        _s = get_settings()
        orsid_cc = _s.get("orsid_coordinator_email", "")
        send_email(
            to=ADMIN_EMAIL,
            cc=orsid_cc if orsid_cc else None,
            subject=f"[ACTION REQUIRED] New Alteration Application — Apt {data['apartment']} | {app_id}",
            body=board_alert_email(data),
            from_alias=ALTERATIONS_EMAIL,
        )
        eddie_email = _s.get("superintendent_email", "")
        if eddie_email:
            send_email(
                to=eddie_email,
                subject=f"FYI: New Alteration Application — Apt {data['apartment']}",
                body=eddie_new_submission_email(data),
                from_alias=ALTERATIONS_EMAIL,
            )
        log_event(app_id, "Email: Receipt sent",
                  f"Receipt sent to {data['shareholder_email']}"
                  + (f", CC {data['gc_email']}" if data.get('gc_email') else "") + ". Board alerted.",
                  apartment=data["apartment"])
    except Exception as e:
        app.logger.error(f"[{app_id}] Email send failed: {e}")


@app.route("/apply", methods=["GET", "POST"])
def apply():
    if request.method == "GET":
        return render_template("intake.html")

    app_id = "ALT-" + datetime.now().strftime("%Y%m") + "-" + uuid.uuid4().hex[:5].upper()
    submitted_at = datetime.now().isoformat()

    data = {
        "app_id": app_id,
        "submitted_at": submitted_at,
        "status": "Received",
        "apartment": request.form.get("apartment", "").strip().upper(),
        "shareholder_name": request.form.get("shareholder_name", "").strip(),
        "shareholder_email": request.form.get("shareholder_email", "").strip(),
        "shareholder_phone": request.form.get("shareholder_phone", "").strip(),
        "project_type": request.form.get("project_type", ""),
        "scope_description": request.form.get("scope_description", "").strip(),
        "estimated_cost": request.form.get("estimated_cost", "").strip(),
        "start_date": request.form.get("start_date", "").strip(),
        "end_date": request.form.get("end_date", "").strip(),
        "gc_name": request.form.get("gc_name", "").strip(),
        "gc_company": request.form.get("gc_company", "").strip(),
        "gc_email": request.form.get("gc_email", "").strip(),
        "gc_phone": request.form.get("gc_phone", "").strip(),
        "plumber_name": request.form.get("plumber_name", "").strip(),
        "electrician_name": request.form.get("electrician_name", "").strip(),
        "involves_plumbing": request.form.get("involves_plumbing", "no"),
        "involves_electrical": request.form.get("involves_electrical", "no"),
        "involves_structural": request.form.get("involves_structural", "no"),
        "involves_kitchen": request.form.get("involves_kitchen", "no"),
        "involves_bathroom": request.form.get("involves_bathroom", "no"),
        "involves_flooring_refinish": request.form.get("involves_flooring_refinish", "no"),
        "involves_flooring_replace": request.form.get("involves_flooring_replace", "no"),
        "architect_assigned": "",
        "expediting": request.form.get("expediting", "no"),
        "ai_review_summary": "",
        "riser_flag": "no",
        "permit_required": "",
        "permits": "[]",
        "payment_status": "Pending",
        "neighbor_letters_sent": "no",
        "drive_folder_url": "",
        "notes": "",
    }

    # Read file bytes now — streams close when the request ends and can't be
    # passed to a background thread
    uploaded_files = []
    for _field, file in request.files.items():
        if file and file.filename:
            uploaded_files.append({
                "filename": file.filename,
                "data": file.read(),
                "content_type": file.content_type or "application/octet-stream",
            })

    # Save to Sheets immediately — application is safe before user redirect
    try:
        append_application(data)
        log_event(app_id, "Status: Received",
                  f"Application submitted by {data['shareholder_name']} for Apt {data['apartment']}. "
                  f"Project: {data.get('project_type','').title()}. "
                  f"{'Expedited review requested. ' if data.get('expediting') == 'yes' else ''}"
                  f"Drive upload, AI review, and notifications processing in background.",
                  actor="shareholder", apartment=data["apartment"])
    except Exception as e:
        app.logger.error(f"[{app_id}] Sheets write failed: {e}")

    # Everything else runs in the background — user sees confirmation immediately
    import threading
    threading.Thread(
        target=_post_submit_background,
        args=(app_id, data, uploaded_files),
        daemon=True,
    ).start()

    return redirect(url_for("submitted", app_id=app_id))


@app.route("/submitted/<app_id>")
def submitted(app_id):
    return render_template("submitted.html", app_id=app_id)


@app.route("/status")
def status():
    return render_template("status.html")


@app.route("/status/lookup")
def status_lookup():
    app_id = request.args.get("app_id", "").strip().upper()
    if not app_id:
        return render_template("status.html", error="Please enter an Application ID.")
    return redirect(url_for("status_detail", app_id=app_id))


@app.route("/status/<app_id>")
def status_detail(app_id):
    try:
        application = get_application(app_id)
    except Exception:
        application = None
    if not application:
        return render_template("status.html", error="Application not found. Check your ID and try again.")
    from services.sheets_service import get_application_log
    # Build a simple milestone dict for the shareholder view: {event_prefix: timestamp}
    milestones = {}
    for entry in get_application_log(app_id):
        event = entry.get("event", "")
        ts = entry.get("timestamp", "")[:10]  # date only
        if event.startswith("Status:") and event not in milestones:
            milestones[event] = ts
    return render_template("status_detail.html", app=application, milestones=milestones)


# ── Shareholder self-report routes (no login required) ────────────────────────

@app.route("/status/<app_id>/confirm-letters", methods=["POST"])
def confirm_neighbor_letters(app_id):
    """Shareholder self-reports that neighbor notification letters have been sent."""
    try:
        application = get_application(app_id)
        if not application:
            flash("Application not found.", "error")
            return redirect(url_for("status_detail", app_id=app_id))
        update_application_field(app_id, "neighbor_letters_sent", "yes")
        log_event(app_id, "Neighbor Letters: Sent",
                  "Shareholder confirmed neighbor notification letters have been sent.",
                  actor="shareholder", apartment=application.get("apartment", ""))
        send_email(
            to=ADMIN_EMAIL,
            subject=f"Neighbor Letters Sent — Apt {application['apartment']} | {app_id}",
            body=(f"<p>{application.get('shareholder_name')} has confirmed that neighbor notification "
                  f"letters have been sent for <strong>Apt {application['apartment']}</strong> "
                  f"({app_id}).</p>"
                  f"<p><a href='{ALTERATIONS_EMAIL}/admin/application/{app_id}'>View application</a></p>"),
            from_alias=ALTERATIONS_EMAIL,
        )
        flash("✓ Neighbor letters confirmed. Thank you!", "success")
    except Exception as e:
        app.logger.error(f"confirm-letters error for {app_id}: {e}")
        flash("Something went wrong — please email us directly.", "error")
    return redirect(url_for("status_detail", app_id=app_id))


@app.route("/status/<app_id>/confirm-deposit", methods=["POST"])
def confirm_deposit_mailed(app_id):
    """Shareholder self-reports that the security deposit check has been mailed."""
    try:
        application = get_application(app_id)
        if not application:
            flash("Application not found.", "error")
            return redirect(url_for("status_detail", app_id=app_id))
        update_application_field(app_id, "payment_status", "Mailed")
        log_event(app_id, "Deposit: Check Mailed",
                  "Shareholder confirmed deposit check has been mailed to Orsid.",
                  actor="shareholder", apartment=application.get("apartment", ""))
        send_email(
            to=ADMIN_EMAIL,
            subject=f"Deposit Check Mailed — Apt {application['apartment']} | {app_id}",
            body=(f"<p>{application.get('shareholder_name')} has confirmed that the security deposit "
                  f"check has been mailed to Orsid for <strong>Apt {application['apartment']}</strong> "
                  f"({app_id}).</p>"
                  f"<p>Update to <strong>Received</strong> once Orsid confirms receipt.</p>"
                  f"<p><a href='{APP_URL}/admin/application/{app_id}'>View application →</a></p>"),
            from_alias=ALTERATIONS_EMAIL,
        )
        flash("✓ Deposit mailing confirmed. Thank you!", "success")
    except Exception as e:
        app.logger.error(f"confirm-deposit error for {app_id}: {e}")
        flash("Something went wrong — please email us directly.", "error")
    return redirect(url_for("status_detail", app_id=app_id))


# ── Auth routes ────────────────────────────────────────────────────────────────

@app.route("/auth/login")
def login():
    return redirect(get_auth_url())


@app.route("/auth/callback")
def auth_callback():
    error = handle_callback(request.args)
    if error:
        return f"Login failed: {error}", 400
    return redirect(url_for("admin_dashboard"))


@app.route("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ── Admin routes (board login required) ───────────────────────────────────────

@app.route("/admin")
@require_board_login
def admin_dashboard():
    try:
        applications = get_all_applications()
    except Exception as e:
        applications = []
        flash(f"Could not load applications: {e}", "error")
    return render_template("admin/dashboard.html", applications=applications)


@app.route("/admin/application/<app_id>")
@require_board_login
def admin_application(app_id):
    try:
        application = get_application(app_id)
    except Exception:
        application = None
    if not application:
        flash("Application not found.", "error")
        return redirect(url_for("admin_dashboard"))
    activity_log = get_application_log(app_id)
    settings = get_settings()
    engineers = [{"key": e["key"], "label": e.get("label", e["key"])} for e in _parse_engineers(settings)]
    votes = get_votes_for_app(app_id)
    approve_count = sum(1 for v in votes if v.get("vote") == "approved")
    return render_template("admin/application.html", app=application, activity_log=activity_log,
                           engineers=engineers, votes=votes, approve_count=approve_count)


@app.route("/admin/application/<app_id>/assign", methods=["POST"])
@require_board_login
def admin_assign(app_id):
    architect = request.form.get("architect")
    expediting = request.form.get("expediting", "no")
    try:
        application = get_application(app_id)
        update_application_fields(app_id, {
            "architect_assigned": architect,
            "expediting": expediting,
            "status": "Pending Assignment",
        })

        settings = get_settings()
        to_email = _engineer_email(settings, architect)
        if not to_email:
            flash(f"No email address configured for {architect}. Update Settings before notifying.", "error")
            return redirect(url_for("admin_application", app_id=app_id))

        send_email(
            to=to_email,
            cc=ADMIN_EMAIL,
            subject=f"Alteration Review — 433 W 34th St, Apt {application['apartment']} | {app_id}",
            body=architect_notification_email(application, architect, expediting == "yes"),
            from_alias=ALTERATIONS_EMAIL,
            reply_to=ALTERATIONS_EMAIL,
        )
        log_event(app_id, "Engineer Notified",
                  f"{architect} notified. {'Expedited review requested — awaiting availability confirmation.' if expediting == 'yes' else 'Standard review.'} Notification sent to {to_email}. Package not yet sent.",
                  actor="board", apartment=application.get("apartment", ""))
        flash(f"{architect} notified. Send the full package once they confirm.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/application/<app_id>/send-package", methods=["POST"])
@require_board_login
def admin_send_package(app_id):
    try:
        application = get_application(app_id)
        architect = application.get("architect_assigned")
        if not architect:
            flash("No Designated Engineer assigned — assign one first.", "error")
            return redirect(url_for("admin_application", app_id=app_id))

        settings = get_settings()
        to_email = _engineer_email(settings, architect)
        if not to_email:
            flash(f"No email address configured for {architect}. Update Settings before sending.", "error")
            return redirect(url_for("admin_application", app_id=app_id))

        send_email(
            to=to_email,
            cc=ADMIN_EMAIL,
            subject=f"Alteration Review Package — 433 W 34th St, Apt {application['apartment']} | {app_id}",
            body=architect_package_email(application, architect, application.get("expediting") == "yes"),
            from_alias=ALTERATIONS_EMAIL,
            reply_to=ALTERATIONS_EMAIL,
        )
        update_application_field(app_id, "status", "Architect Assigned")
        log_event(app_id, "Status: Architect Assigned",
                  f"Full application package sent to {architect} at {to_email}.",
                  actor="board", apartment=application.get("apartment", ""))
        flash(f"Package sent to {architect}. Status updated to Architect Assigned.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/application/<app_id>/update", methods=["POST"])
@require_board_login
def admin_update(app_id):
    """Generic field update from the admin panel."""
    field = request.form.get("field")
    value = request.form.get("value", "")
    allowed_fields = {
        "status", "permit_required", "permits", "payment_status",
        "neighbor_letters_sent", "notes", "riser_flag", "scope_change_flag", "expediting",
    }
    if field not in allowed_fields:
        flash("Invalid field.", "error")
        return redirect(url_for("admin_application", app_id=app_id))
    try:
        update_application_field(app_id, field, value)
        # Log meaningful field changes
        label_map = {
            "status": "Status",
            "payment_status": "Payment",
            "neighbor_letters_sent": "Neighbor Letters",
            "permit_required": "Permit Required",
            "permits": "Permit Details",
            "riser_flag": "Riser Flag",
            "scope_change_flag": "Scope Change Flag",
            "expediting": "Expedited Review",
        }
        if field != "notes" and field in label_map:
            log_event(app_id, f"Updated: {label_map[field]}",
                      f"Set to: {value}",
                      actor="board")
        flash("Updated.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/application/<app_id>/approve", methods=["POST"])
@require_board_login
def admin_approve(app_id):
    try:
        application = get_application(app_id)
        update_application_field(app_id, "status", "Board Approved")

        # Notify shareholder + GC
        send_email(
            to=application["shareholder_email"],
            cc=application.get("gc_email") or None,
            subject=f"Alteration Approved — Apt {application['apartment']} | {app_id}",
            body=approval_email(application),
            from_alias=ALTERATIONS_EMAIL,
        )
        # FYI to Eddie
        _s = get_settings()
        eddie_email = _s.get("superintendent_email", "")
        if eddie_email:
            send_email(
                to=eddie_email,
                subject=f"FYI: Alteration Approved — Apt {application['apartment']}",
                body=eddie_approval_email(application),
                from_alias=ALTERATIONS_EMAIL,
            )
        # FYI to Orsid coordinator(s) — single email, comma-separated addresses handled by Gmail
        orsid_coord = _s.get("orsid_coordinator_email", "")
        if orsid_coord:
            send_email(
                to=orsid_coord,
                subject=f"FYI: Alteration Approved — 433 W 34th St Apt {application['apartment']}",
                body=approval_email(application),
                from_alias=ALTERATIONS_EMAIL,
            )
        log_event(app_id, "Status: Board Approved",
                  f"Board approved. Approval notification sent to {application['shareholder_email']}"
                  + (f" and {application.get('gc_email')}" if application.get('gc_email') else "") + ". Eddie and Orsid notified.",
                  actor="board", apartment=application.get("apartment", ""))
        flash("Application approved. Notifications sent.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/application/<app_id>/start-work", methods=["POST"])
@require_board_login
def admin_start_work(app_id):
    """Mark application as Work In Progress and notify shareholder/GC."""
    try:
        application = get_application(app_id)
        update_application_field(app_id, "status", "Work In Progress")
        from services.email_templates import work_in_progress_email
        send_email(
            to=application["shareholder_email"],
            cc=application.get("gc_email") or None,
            subject=f"Work In Progress — Apt {application['apartment']} | {app_id}",
            body=work_in_progress_email(application),
            from_alias=ALTERATIONS_EMAIL,
        )
        log_event(app_id, "Status: Work In Progress",
                  f"Work commenced. Shareholder notified at {application['shareholder_email']}.",
                  actor="board", apartment=application.get("apartment", ""))
        flash("Marked as Work In Progress. Shareholder notified.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/application/<app_id>/sign-off", methods=["POST"])
@require_board_login
def admin_sign_off(app_id):
    """Mark permits as signed off and initiate deposit return with Orsid."""
    try:
        application = get_application(app_id)
        update_application_field(app_id, "status", "Project Sign-Off")
        from services.email_templates import sign_off_email
        send_email(
            to=application["shareholder_email"],
            cc=application.get("gc_email") or None,
            subject=f"Permits Signed Off — Apt {application['apartment']} | {app_id}",
            body=sign_off_email(application),
            from_alias=ALTERATIONS_EMAIL,
        )
        log_event(app_id, "Status: Project Sign-Off",
                  f"Permits signed off and closed. Deposit return initiated with Orsid. "
                  f"Shareholder notified at {application['shareholder_email']}.",
                  actor="board", apartment=application.get("apartment", ""))
        flash("Marked as Project Sign-Off. Shareholder notified.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/application/<app_id>/complete", methods=["POST"])
@require_board_login
def admin_complete(app_id):
    """Mark project complete (deposit returned by Orsid). Notifies shareholder and Eddie."""
    try:
        application = get_application(app_id)
        update_application_field(app_id, "status", "Complete")
        from services.email_templates import complete_email
        send_email(
            to=application["shareholder_email"],
            cc=application.get("gc_email") or None,
            subject=f"Alteration Complete — Apt {application['apartment']} | {app_id}",
            body=complete_email(application),
            from_alias=ALTERATIONS_EMAIL,
        )
        # FYI to Eddie
        _s = get_settings()
        eddie_email = _s.get("superintendent_email", "")
        if eddie_email:
            send_email(
                to=eddie_email,
                subject=f"FYI: Alteration Complete — Apt {application['apartment']}",
                body=(f"<p>Hi Eddie,</p><p>The alteration for <strong>Apt {application['apartment']}</strong> "
                      f"({application.get('shareholder_name')}) is now complete and closed out. "
                      f"The security deposit is being returned to the shareholder via Orsid.</p>"),
                from_alias=ALTERATIONS_EMAIL,
            )
        log_event(app_id, "Status: Complete",
                  f"Project complete. Deposit return confirmed. "
                  f"Shareholder and Eddie notified.",
                  actor="board", apartment=application.get("apartment", ""))
        flash("Application marked Complete. Shareholder and Eddie notified.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/application/<app_id>/neighbor-letters", methods=["POST"])
@require_board_login
def admin_neighbor_letters(app_id):
    try:
        application = get_application(app_id)
        # Generate letter draft and email to shareholder to send
        send_email(
            to=application["shareholder_email"],
            subject=f"Action Required: Send Neighbor Notification Letters — Apt {application['apartment']}",
            body=neighbor_letter_email(application),
            from_alias=ALTERATIONS_EMAIL,
        )
        flash("Neighbor letter template sent to shareholder.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/application/<app_id>/withdraw", methods=["POST"])
@require_board_login
def admin_withdraw(app_id):
    from services.sheets_service import get_application, update_application_field, log_event
    try:
        app_data = get_application(app_id)
        if not app_data:
            flash("Application not found.", "error")
            return redirect(url_for("admin_dashboard"))

        reason = request.form.get("reason", "").strip()
        fields = {"status": "Withdrawn"}
        if reason:
            existing_notes = app_data.get("notes", "") or ""
            fields["notes"] = (existing_notes + "\n\n" if existing_notes else "") + f"Withdrawal reason: {reason}"
        update_application_fields(app_id, fields)
        log_event(app_id, "Status: Withdrawn",
                  reason or "Marked withdrawn/canceled by board.",
                  actor="board", apartment=app_data.get("apartment", ""))
        flash(f"Application {app_id} marked as withdrawn.", "info")
    except Exception as e:
        flash(f"Error withdrawing application: {e}", "error")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/application/<app_id>/bill-fee", methods=["POST"])
@require_board_login
def admin_bill_fee(app_id):
    from services.sheets_service import get_application, update_application_field, log_event
    from services.gmail_service import send_email
    from services.email_templates import application_fee_billing_email, APPLICATION_FEE

    app_data = get_application(app_id)
    if not app_data:
        flash("Application not found.", "error")
        return redirect(url_for("admin_dashboard"))

    _s = get_settings()
    ORSID_FEE_TO = _s.get("orsid_fee_billing_emails", "mminter@orsidny.com,EDODAJ@orsidny.com,lbehri@orsidny.com")
    shareholder_email = app_data.get("shareholder_email", "")
    ORSID_FEE_CC = ",".join(filter(None, [_s.get("orsid_coordinator_email", ""), shareholder_email]))

    try:
        body = application_fee_billing_email(app_data)
        send_email(
            to=ORSID_FEE_TO,
            cc=ORSID_FEE_CC,
            subject=f"Alteration Review Fee — Apt {app_data['apartment']} | {app_id}",
            body=body,
            reply_to=BOARD_EMAIL,
        )
        update_application_field(app_id, "application_fee_status", "Billed")
        log_event(app_id, "Application Fee Billed",
                  f"${APPLICATION_FEE} billing request sent to Orsid (Molly Minter, Enriko Dodaj, Livia Behri).",
                  actor="board", apartment=app_data.get("apartment", ""))
        flash(f"✓ Fee billing request sent to Orsid for Apt {app_data['apartment']}.", "success")
    except Exception as e:
        flash(f"Error sending fee billing email: {e}", "error")

    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/admin/check-inbox", methods=["POST"])
@require_board_login
def admin_check_inbox():
    """Manually trigger architect inbox processing."""
    try:
        from services.inbox_service import process_architect_inbox
        processed, errors = process_architect_inbox()
        if processed:
            for msg in processed:
                flash(f"✓ {msg}", "success")
        if errors:
            for err in errors:
                flash(f"⚠ {err}", "warning")
        if not processed and not errors:
            flash("Inbox checked — no new architect emails found.", "info")
    except Exception as e:
        flash(f"Inbox check error: {e}", "error")
    return redirect(url_for("admin_dashboard"))


def _send_vote_reminders() -> dict:
    """
    For every application awaiting a board vote, email pending voters their magic link.
    Called once daily by the cron job — the daily cadence is the throttle.
    Returns a summary dict for logging.
    """
    apps = get_all_applications()
    reminded = 0
    skipped = 0
    for a in apps:
        if a.get("status") != "Awaiting Board Vote":
            continue
        app_id = a.get("app_id", "")
        pending = get_pending_vote_rows(app_id)
        if not pending:
            skipped += 1
            continue
        for voter in pending:
            vote_url = f"{APP_URL}/vote/{app_id}/{voter['token']}"
            try:
                send_email(
                    to=voter["board_member_email"],
                    subject=f"Reminder: Vote Pending — {app_id} Apt {a.get('apartment')}",
                    body=vote_reminder_email(a, voter["board_member_name"], vote_url),
                    reply_to=BOARD_EMAIL,
                )
                reminded += 1
            except Exception:
                pass
        log_event(app_id, "Vote Reminder Sent",
                  f"Reminded {len(pending)} pending voter(s)",
                  actor="system", apartment=a.get("apartment", ""))
    return {"apps_reminded": reminded, "apps_complete": skipped}


@app.route("/cron/check-inbox", methods=["POST"])
def cron_check_inbox():
    """Called by cron job once daily. Protected by CRON_SECRET token."""
    auth = request.headers.get("Authorization", "")
    if not CRON_SECRET or auth != f"Bearer {CRON_SECRET}":
        return jsonify({"error": "Unauthorized"}), 401
    results = {}
    try:
        from services.inbox_service import process_inbox
        processed, errors = process_inbox()
        results["inbox"] = {"processed": processed, "errors": errors}
    except Exception as e:
        results["inbox"] = {"error": str(e)}
    try:
        results["vote_reminders"] = _send_vote_reminders()
    except Exception as e:
        results["vote_reminders"] = {"error": str(e)}
    return jsonify(results), 200


@app.route("/admin/token")
@require_board_login
def admin_show_token():
    """Show the current token.json so it can be copied into GOOGLE_TOKEN_JSON on Render."""
    import json as _json
    from services.google_auth import TOKEN_FILE
    try:
        with open(TOKEN_FILE) as f:
            token_data = _json.load(f)
        token_str = _json.dumps(token_data)
    except FileNotFoundError:
        token_str = None

    return f"""
    <html><head><title>Token — Admin</title>
    <style>body{{font-family:sans-serif;max-width:900px;margin:40px auto;padding:0 20px;}}
    textarea{{width:100%;height:200px;font-family:monospace;font-size:12px;}}
    .note{{background:#fff3cd;border:1px solid #ffc107;padding:12px 16px;border-radius:6px;margin-bottom:20px;}}
    </style></head><body>
    <p><a href="/admin">← Back to Admin</a></p>
    <h2>Current Google Token</h2>
    <div class="note">
      <strong>After re-authorizing:</strong> copy the token below, go to
      <strong>Render → Environment → GOOGLE_TOKEN_JSON</strong> and paste it in.
      This ensures the new scopes survive the next redeploy.
    </div>
    {"<textarea onclick='this.select()'>"+token_str+"</textarea>" if token_str
     else "<p style='color:red;'>No token.json found on disk — re-authorize first at <a href='/auth/login'>/auth/login</a>.</p>"}
    </body></html>
    """


def _parse_board_members(settings: dict) -> list:
    import json as _json
    raw = settings.get("board_members_json", "")
    if raw:
        try:
            return _json.loads(raw)
        except (ValueError, TypeError):
            pass
    return []


def _parse_fee_billing(settings: dict) -> list:
    import json as _json
    raw = settings.get("orsid_fee_billing_json", "")
    if raw:
        try:
            return _json.loads(raw)
        except (ValueError, TypeError):
            pass
    # Fallback: convert legacy comma-separated emails to list with no names
    emails_raw = settings.get("orsid_fee_billing_emails", "")
    if emails_raw:
        return [{"name": "", "role": "Bookkeeper", "email": e.strip()}
                for e in emails_raw.split(",") if e.strip()]
    return []


@app.route("/admin/settings", methods=["GET"])
@require_board_login
def admin_settings():
    settings = get_settings()
    engineers_list = _parse_engineers(settings)
    fee_billing_list = _parse_fee_billing(settings)
    board_members_list = _parse_board_members(settings)
    return render_template("admin/settings.html", settings=settings,
                           engineers_list=engineers_list, fee_billing_list=fee_billing_list,
                           board_members_list=board_members_list)


@app.route("/admin/settings", methods=["POST"])
@require_board_login
def admin_settings_save():
    updates = {
        "engineers_json":             request.form.get("engineers_json", "").strip(),
        "board_members_json":         request.form.get("board_members_json", "").strip(),
        "admin_email":                request.form.get("admin_email", "").strip(),
        "superintendent_name":        request.form.get("superintendent_name", "").strip(),
        "superintendent_email":       request.form.get("superintendent_email", "").strip(),
        "orsid_coordinator_name":     request.form.get("orsid_coordinator_name", "").strip(),
        "orsid_coordinator_email":    request.form.get("orsid_coordinator_email", "").strip(),
        "orsid_fee_billing_json":     request.form.get("orsid_fee_billing_json", "").strip(),
        "orsid_fee_billing_emails":   request.form.get("orsid_fee_billing_emails", "").strip(),
    }
    try:
        save_settings(updates)
        flash("Settings saved.", "success")
    except Exception as e:
        flash(f"Could not save settings: {e}", "error")
    return redirect(url_for("admin_settings"))


# ── Board voting routes ───────────────────────────────────────────────────────

def _send_vote_links(app_id: str, app_data: dict):
    """Generate tokens for all board members, write to Votes tab, send invite emails."""
    settings = get_settings()
    members = _parse_board_members(settings)
    if not members:
        raise ValueError("No board members configured in Settings.")
    members_with_tokens = [
        {"name": m["name"], "email": m["email"], "token": secrets.token_urlsafe(32)}
        for m in members
    ]
    write_vote_tokens(app_id, members_with_tokens)
    for m in members_with_tokens:
        vote_url = f"{APP_URL}/vote/{app_id}/{m['token']}"
        send_email(
            to=m["email"],
            subject=f"Board Vote — {app_id} Apt {app_data.get('apartment')}",
            body=vote_invitation_email(app_data, m["name"], vote_url),
            reply_to=BOARD_EMAIL,
        )


@app.route("/admin/application/<app_id>/send-vote-links", methods=["POST"])
@require_board_login
def admin_send_vote_links(app_id):
    application = get_application(app_id)
    if not application:
        flash("Application not found.", "error")
        return redirect(url_for("admin_dashboard"))
    try:
        _send_vote_links(app_id, application)
        update_application_fields(app_id, {"status": "Awaiting Board Vote"})
        log_event(app_id, "Board Vote Links Sent", "Magic links emailed to all board members",
                  actor="board", apartment=application.get("apartment", ""))
        flash("Vote links sent to all board members.", "success")
    except Exception as e:
        flash(f"Could not send vote links: {e}", "error")
    return redirect(url_for("admin_application", app_id=app_id))


@app.route("/vote/<app_id>/<token>", methods=["GET"])
def vote_page(app_id, token):
    votes = get_votes_for_app(app_id)
    # Verify token belongs to this app (get_votes_for_app strips tokens)
    token_info = lookup_vote_token(app_id, token)
    valid        = token_info["valid"]
    already_voted = token_info["already_voted"]
    voter_name   = token_info["voter_name"]
    if not valid:
        return render_template("vote_invalid.html"), 404
    application = get_application(app_id)
    if not application:
        return render_template("vote_invalid.html"), 404
    approve_count = sum(1 for v in votes if v.get("vote") == "approved")
    return render_template("vote.html", app=application, votes=votes,
                           approve_count=approve_count, already_voted=already_voted,
                           voter_name=voter_name, token=token)


@app.route("/vote/<app_id>/<token>", methods=["POST"])
def vote_submit(app_id, token):
    found_app_id, approve_count = record_vote(token)
    if found_app_id is None:
        return render_template("vote_invalid.html"), 404
    if approve_count == -1:
        return redirect(url_for("vote_page", app_id=app_id, token=token))
    # Check threshold — send alert if just hit
    if approve_count == VOTE_THRESHOLD:
        try:
            application = get_application(found_app_id)
            if application:
                send_email(
                    to=ADMIN_EMAIL,
                    subject=f"Board Vote Threshold Reached — {found_app_id} Apt {application.get('apartment')}",
                    body=vote_threshold_email(application, approve_count),
                )
        except Exception:
            pass  # don't let alert failure block the vote
    return redirect(url_for("vote_page", app_id=app_id, token=token))


@app.route("/admin/application/<app_id>/changes-required", methods=["POST"])
@require_board_login
def admin_changes_required(app_id):
    application = get_application(app_id)
    if not application:
        flash("Application not found.", "error")
        return redirect(url_for("admin_dashboard"))
    reason = request.form.get("reason", "").strip()
    update_application_field(app_id, "status", "Changes Required")
    gc_email = application.get("gc_email", "")
    send_email(
        to=application.get("shareholder_email", ""),
        cc=gc_email if gc_email else None,
        subject=f"Changes Required — {application.get('app_id')} Apt {application.get('apartment')}",
        body=changes_required_email(application, reason),
        reply_to=BOARD_EMAIL,
    )
    log_event(app_id, "Changes Required", reason or "No reason provided",
              actor="board", apartment=application.get("apartment", ""))
    flash("Status set to Changes Required and shareholder notified.", "success")
    return redirect(url_for("admin_application", app_id=app_id))


if __name__ == "__main__":
    app.run(debug=True)
