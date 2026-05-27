import os
import uuid
import json
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)
from dotenv import load_dotenv
from services.google_auth import require_board_login, get_auth_url, handle_callback
from services.drive_service import create_application_folder, upload_file
from services.sheets_service import append_application, update_application_field, get_all_applications, get_application, log_event
from services.gmail_service import send_email
from services.claude_service import review_application
from services.email_templates import (
    receipt_email, board_alert_email, eddie_new_submission_email,
    architect_package_email, approval_email, eddie_approval_email,
    neighbor_letter_email
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

BOARD_EMAIL = os.environ["BOARD_EMAIL"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ALTERATIONS_EMAIL = os.environ["ALTERATIONS_EMAIL"]

# ── Background inbox scheduler ────────────────────────────────────────────────
# Checks alterations@433w34.com for unread architect emails every 5 minutes.
# Guard prevents double-start in Flask debug mode (which forks two processes).
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from services.inbox_service import process_architect_inbox
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(process_architect_inbox, "interval", minutes=5, id="inbox_check",
                           misfire_grace_time=60)
        _scheduler.start()
    except Exception as _e:
        app.logger.warning(f"Inbox scheduler could not start: {_e}")

# ── Public routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/apply", methods=["GET", "POST"])
def apply():
    if request.method == "GET":
        return render_template("intake.html")

    # Build application record from form
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
        "project_type": request.form.get("project_type", ""),  # decoration | alteration
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

    # Upload documents to Google Drive
    folder_url = ""
    try:
        folder_id, folder_url = create_application_folder(app_id, data["apartment"])
        data["drive_folder_url"] = folder_url
        for field_name, file in request.files.items():
            if file and file.filename:
                upload_file(folder_id, file)
    except Exception as e:
        app.logger.error(f"Drive upload failed: {e}")

    # Run Claude AI review
    try:
        review = review_application(data)
        data["ai_review_summary"] = review.get("summary", "")
        data["riser_flag"] = "yes" if review.get("riser_risk") else "no"
    except Exception as e:
        app.logger.error(f"Claude review failed: {e}")
        data["ai_review_summary"] = "Automated review unavailable — please review manually."

    # Save to Google Sheets
    try:
        append_application(data)
        log_event(app_id, "Status: Received",
                  f"Application submitted by {data['shareholder_name']} for Apt {data['apartment']}. "
                  f"Project: {data.get('project_type','').title()}. "
                  f"{'Expedited review requested. ' if data.get('expediting') == 'yes' else ''}"
                  f"Riser flag: {data.get('riser_flag','no')}.",
                  actor="shareholder", apartment=data["apartment"])
    except Exception as e:
        app.logger.error(f"Sheets write failed: {e}")

    # Send emails
    try:
        # Receipt to shareholder
        send_email(
            to=data["shareholder_email"],
            cc=data["gc_email"] if data["gc_email"] else None,
            subject=f"Application Received — Apt {data['apartment']} | {app_id}",
            body=receipt_email(data),
            from_alias=ALTERATIONS_EMAIL,
        )
        # Alert to board + Orsid building management
        orsid_cc = os.environ.get("ORSID_CC_EMAILS", "")
        send_email(
            to=ADMIN_EMAIL,
            cc=orsid_cc if orsid_cc else None,
            subject=f"[ACTION REQUIRED] New Alteration Application — Apt {data['apartment']} | {app_id}",
            body=board_alert_email(data),
            from_alias=ALTERATIONS_EMAIL,
        )
        # FYI to Eddie
        send_email(
            to=os.environ["EDDIE_EMAIL"],
            subject=f"FYI: New Alteration Application — Apt {data['apartment']}",
            body=eddie_new_submission_email(data),
            from_alias=ALTERATIONS_EMAIL,
        )
        log_event(app_id, "Email: Receipt sent",
                  f"Receipt sent to {data['shareholder_email']}"
                  + (f", CC {data['gc_email']}" if data.get('gc_email') else "") + ". Board alerted.",
                  apartment=data["apartment"])
    except Exception as e:
        app.logger.error(f"Email send failed: {e}")

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
    from services.sheets_service import get_application_log
    activity_log = get_application_log(app_id)
    return render_template("admin/application.html", app=application, activity_log=activity_log)


@app.route("/admin/application/<app_id>/assign", methods=["POST"])
@require_board_login
def admin_assign(app_id):
    architect = request.form.get("architect")
    expediting = request.form.get("expediting", "no")
    try:
        application = get_application(app_id)
        update_application_field(app_id, "architect_assigned", architect)
        update_application_field(app_id, "expediting", expediting)
        update_application_field(app_id, "status", "Architect Assigned")

        # Send package to architect
        melone_emails = os.environ.get("MELONE_EMAILS", "").split(",")
        capobianco_email = os.environ.get("CAPOBIANCO_EMAIL", "")
        to_email = ",".join(melone_emails) if architect == "Melone" else capobianco_email

        send_email(
            to=to_email,
            cc=ADMIN_EMAIL,
            subject=f"Alteration Review Request — 433 W 34th St, Apt {application['apartment']} | {app_id}",
            body=architect_package_email(application, architect, expediting == "yes"),
            from_alias=ALTERATIONS_EMAIL,
            reply_to=ALTERATIONS_EMAIL,
        )
        log_event(app_id, "Status: Architect Assigned",
                  f"Assigned to {architect}. {'Expedited review requested.' if expediting == 'yes' else 'Standard review.'} Package emailed to {to_email}.",
                  actor="board", apartment=application.get("apartment", ""))
        flash(f"Application assigned to {architect} and package sent.", "success")
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
        "neighbor_letters_sent", "notes", "riser_flag", "expediting",
    }
    if field not in allowed_fields:
        flash("Invalid field.", "error")
        return redirect(url_for("admin_application", app_id=app_id))
    try:
        application = get_application(app_id)
        update_application_field(app_id, field, value)
        # Log meaningful field changes
        label_map = {
            "status": "Status",
            "payment_status": "Payment",
            "neighbor_letters_sent": "Neighbor Letters",
            "permit_required": "Permit Required",
            "permits": "Permit Details",
            "riser_flag": "Riser Flag",
            "expediting": "Expedited Review",
        }
        if field != "notes" and field in label_map:
            log_event(app_id, f"Updated: {label_map[field]}",
                      f"Set to: {value}",
                      actor="board", apartment=application.get("apartment", "") if application else "")
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
        send_email(
            to=os.environ["EDDIE_EMAIL"],
            subject=f"FYI: Alteration Approved — Apt {application['apartment']}",
            body=eddie_approval_email(application),
            from_alias=ALTERATIONS_EMAIL,
        )
        # CC Orsid building mgmt
        for addr in os.environ.get("ORSID_CC_EMAILS", "").split(","):
            if addr.strip():
                send_email(
                    to=addr.strip(),
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


if __name__ == "__main__":
    app.run(debug=True)
