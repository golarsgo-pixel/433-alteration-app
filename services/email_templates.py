"""
All outbound email bodies for the alteration app.
All functions return HTML strings.
"""
import os
import json

BUILDING = os.environ.get("BUILDING_NAME", "433 West 34th Street Owners Corp.")
ALTERATIONS_EMAIL = os.environ.get("ALTERATIONS_EMAIL", "alterations@433w34.com")
BOARD_EMAIL = os.environ.get("BOARD_EMAIL", "board@433w34.com")
APP_URL = os.environ.get("APP_URL", "https://four33-alteration-app.onrender.com")


def _sig():
    return f"""
<p style="margin-top:24px; color:#555; font-size:13px;">
433 West 34th Street Board of Directors<br>
<a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>
</p>
"""


def _wrap(content: str) -> str:
    return f"""
<html><body style="font-family:Arial,sans-serif; font-size:14px; color:#222; max-width:680px; margin:0 auto; padding:24px;">
{content}
{_sig()}
</body></html>
"""


# ── Shareholder: receipt on submission ────────────────────────────────────────

def receipt_email(app: dict) -> str:
    deposit = _security_deposit(app.get("estimated_cost", "0"))
    project_label = "Decoration Project" if app.get("project_type") == "decoration" else "Full Alteration"

    ai_section = ""
    if app.get("ai_review_summary"):
        ai_section = f"""
<h3 style="color:#1a5276;">Preliminary Review Notes</h3>
<p>{app['ai_review_summary']}</p>
"""

    riser_section = ""
    if app.get("riser_flag") == "yes":
        riser_section = f"""
<div style="background:#fff3cd; border-left:4px solid #f0ad4e; padding:12px 16px; margin:16px 0;">
<strong>Riser Assessment Notice:</strong> Based on your scope, the building superintendent will conduct a
pre-work riser assessment before demo begins. This is to coordinate any building-side pipe work during
your open-wall period — which avoids mid-project delays. We will be in touch.
</div>
"""

    gc_line = f"<p style='color:#555; font-size:13px;'>cc: {app.get('gc_name')} ({app.get('gc_company')})</p>" if app.get('gc_email') else ""

    expediting_note = ""
    if app.get("expediting") == "yes":
        expediting_note = """
<div style="background:#d5f5e3; border-left:4px solid #27ae60; padding:12px 16px; margin:16px 0;">
<strong>Expedited Review Requested.</strong> Your request for expedited architect review has been noted.
The assigned architect will confirm availability and their expediting fee before proceeding.
Expedited review typically takes 4–5 business days from receipt of a complete package.
</div>
"""

    return _wrap(f"""
<p>Dear {app.get('shareholder_name', 'Shareholder')},</p>
{gc_line}

<p>Thank you for submitting your alteration application. We have received it and will be in touch shortly.</p>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Apartment</td>
      <td style="padding:6px 12px;">{app.get('apartment')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Project Type</td>
      <td style="padding:6px 12px;">{project_label}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Status</td>
      <td style="padding:6px 12px;">Received — Under Review</td></tr>
</table>

{expediting_note}

{ai_section}
{riser_section}

<h3 style="color:#1a5276;">Next Steps</h3>
<ol>
  <li>We will review your submission for completeness. If any required documents are missing or incomplete,
      we will contact you at <strong>{app.get('shareholder_email')}</strong>.</li>
  <li>Once all required documents are confirmed, we will assign a reviewing architect and send them your package.
      All communications will go through <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>.</li>
  <li>The architect may send questions or requests for additional information, which will be forwarded to you.</li>
  <li>Once the architect recommends approval, the Board will vote and you will receive written notification.</li>
  <li>No work may begin until you receive written board approval and have sent neighbor notification letters.</li>
</ol>

<h3 style="color:#1a5276;">Security Deposit <span style="font-weight:normal; font-size:13px; color:#888;">(For {app.get('shareholder_name', 'Shareholder')})</span></h3>
<p>A security deposit of <strong>{deposit}</strong> (the greater of $2,000 or 10% of your projected cost)
will be due following board approval. It is payable by check to <em>433 West 34th Street Owners Corp.</em>,
sent to Orsid Realty Corp., 156 West 56th Street, 6th Floor, New York, NY 10019, Attn: Alteration Deposit.
Include your Application ID ({app.get('app_id')}) in the memo.</p>

<p>You can track your application status at any time using your Application ID at:<br>
<strong><a href="{APP_URL}/status/{app.get('app_id')}">
{APP_URL}/status/{app.get('app_id')}</a></strong></p>

<p>Please do not hesitate to reach out with any questions.</p>
""")


# ── Board: alert on new submission ────────────────────────────────────────────

def board_alert_email(app: dict) -> str:
    flags = []
    if app.get("riser_flag") == "yes":
        flags.append("⚠️ <strong>RISER RISK</strong> — scope involves plumbing/kitchen/bath work. Eddie should assess before demo.")

    ai_summary = app.get("ai_review_summary", "Not available.")
    flag_html = "".join(f"<li>{f}</li>" for f in flags) if flags else "<li>None</li>"
    project_label = "Decoration Project" if app.get("project_type") == "decoration" else "Full Alteration"

    return _wrap(f"""
<h2>New Alteration Application</h2>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Apartment</td>
      <td style="padding:6px 12px;">{app.get('apartment')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Shareholder</td>
      <td style="padding:6px 12px;">{app.get('shareholder_name')} — {app.get('shareholder_email')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Project Type</td>
      <td style="padding:6px 12px;">{project_label}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Estimated Cost</td>
      <td style="padding:6px 12px;">${app.get('estimated_cost', 'not provided')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">GC</td>
      <td style="padding:6px 12px;">{app.get('gc_name', '—')} / {app.get('gc_company', '—')}</td></tr>
</table>

<h3>Scope Summary</h3>
<p style="background:#f9f9f9; padding:12px; border-left:3px solid #ccc;">{app.get('scope_description', '—')}</p>

<h3>AI Review Summary</h3>
<p>{ai_summary}</p>

<h3>Flags</h3>
<ul>{flag_html}</ul>

<h3>Documents</h3>
<p>📁 <a href="{app.get('drive_folder_url', '#')}">View submitted documents in Google Drive</a></p>

<div style="margin-top:24px; text-align:center;">
  <a href="{APP_URL}/admin/application/{app.get('app_id')}"
     style="background:#1a5276; color:white; padding:12px 24px; text-decoration:none; border-radius:4px; font-size:15px;">
    Assign Architect →
  </a>
</div>
""")


# ── Eddie: FYI on new submission ──────────────────────────────────────────────

def eddie_new_submission_email(app: dict) -> str:
    riser_section = ""
    if app.get("riser_flag") == "yes":
        riser_section = f"""
<div style="background:#fff3cd; border-left:4px solid #f0ad4e; padding:12px 16px; margin:16px 0;">
<strong>Riser Assessment Needed:</strong> This project involves plumbing work in the kitchen or bathroom.
Please plan to assess the riser condition in Apt {app.get('apartment')} before demo begins.
The board will confirm timing once the project is approved.
</div>
"""
    return _wrap(f"""
<p>Hi Eddie,</p>

<p>This is a heads-up that a new alteration application has been received for <strong>Apt {app.get('apartment')}</strong>.</p>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Shareholder</td>
      <td style="padding:6px 12px;">{app.get('shareholder_name')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Scope (brief)</td>
      <td style="padding:6px 12px;">{app.get('scope_description', '')[:300]}{'...' if len(app.get('scope_description','')) > 300 else ''}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Est. Start Date</td>
      <td style="padding:6px 12px;">{app.get('start_date', 'TBD')}</td></tr>
</table>

{riser_section}

<p>No action required from you at this time. You'll receive another note when the project is approved and ready to begin.
If you have any questions, reply to this email or reach out to the board.</p>
""")


# ── Architect: application package ────────────────────────────────────────────

def architect_package_email(app: dict, architect_name: str, expediting: bool) -> str:
    expediting_note = ""
    if expediting:
        expediting_note = """
<div style="background:#d5f5e3; border-left:4px solid #27ae60; padding:12px 16px; margin:16px 0;">
<strong>Expedited Review Requested.</strong> The shareholder has requested expedited review and will pay the
applicable expediting fee. Please confirm your availability and fee with us at your earliest convenience.
</div>
"""
    project_label = "Decoration Project" if app.get("project_type") == "decoration" else "Full Alteration"

    return _wrap(f"""
<p>Dear {architect_name} team,</p>

<p>Please find below the details for a new alteration application at <strong>433 West 34th Street</strong>
requiring your review.</p>

{expediting_note}

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Apartment</td>
      <td style="padding:6px 12px;">{app.get('apartment')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Shareholder</td>
      <td style="padding:6px 12px;">{app.get('shareholder_name')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Project Type</td>
      <td style="padding:6px 12px;">{project_label}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Estimated Cost</td>
      <td style="padding:6px 12px;">${app.get('estimated_cost', 'not provided')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Proposed Start</td>
      <td style="padding:6px 12px;">{app.get('start_date', 'TBD')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Proposed End</td>
      <td style="padding:6px 12px;">{app.get('end_date', 'TBD')}</td></tr>
</table>

<h3>Scope of Work</h3>
<p style="background:#f9f9f9; padding:12px; border-left:3px solid #ccc;">{app.get('scope_description', '—')}</p>

<h3>Submitted Documents</h3>
<p>📁 All submitted documents are available here:<br>
<a href="{app.get('drive_folder_url', '#')}">{app.get('drive_folder_url', 'Link not available')}</a></p>

<h3>Instructions</h3>
<ul>
  <li>Please reply to <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a> with your initial report
      or any questions. Use the Application ID <strong>{app.get('app_id')}</strong> in your subject line.</li>
  <li>Your report will be forwarded to the shareholder and their GC for response.</li>
  <li>When you are satisfied and ready to recommend approval, please send a written recommendation to
      <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>.</li>
  <li>Please also indicate whether a DOB permit (or other permits) will be required for this scope.</li>
</ul>

<p>Thank you — please don't hesitate to reach out with any questions.</p>
""")


# ── Shareholder: board approval ───────────────────────────────────────────────

def approval_email(app: dict) -> str:
    status_url = f"{APP_URL}/status/{app.get('app_id')}"
    deposit = _security_deposit(app.get("estimated_cost", "0"))

    permit_note = ""
    if app.get("permit_required") == "yes":
        permit_note = f"""
<div style="background:#d6eaf8; border-left:4px solid #2980b9; padding:12px 16px; margin:16px 0;">
<strong>Permits Required:</strong> The reviewing architect has indicated that one or more permits are
required before work may begin. Your contractor must file for and obtain all required permits before
commencing work. Email copies to <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>.
</div>
"""

    # Pre-populate the neighbor letter
    start_display = app.get("start_date") or "[your planned start date]"
    duration_display = "[estimated duration]"
    if app.get("start_date") and app.get("end_date"):
        try:
            from datetime import datetime as _dt
            _s = _dt.fromisoformat(app["start_date"])
            _e = _dt.fromisoformat(app["end_date"])
            _days = (_e - _s).days
            duration_display = f"{_days} calendar days"
        except Exception:
            pass

    return _wrap(f"""
<p>Dear {app.get('shareholder_name', 'Shareholder')},</p>

<p>We are pleased to inform you that the Board of Directors has approved your alteration application
for Apartment <strong>{app.get('apartment')}</strong>.</p>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Status</td>
      <td style="padding:6px 12px; color:#27ae60;"><strong>Approved</strong></td></tr>
</table>

{permit_note}

<h3 style="color:#1a5276;">Two Required Steps — Complete These Before Work Begins</h3>

<div style="background:#fffbea; border:2px solid #f0ad4e; border-radius:6px; padding:16px 20px; margin:16px 0;">
  <strong>Step 1 — Mail Your Security Deposit</strong>
  <p style="margin:8px 0 4px;">Send a check for <strong>{deposit}</strong> payable to:</p>
  <p style="margin:4px 0; padding-left:16px;">
    <em>433 West 34th Street Owners Corp.</em><br>
    c/o Orsid Realty Corp., 156 West 56th Street, 6th Floor, New York, NY 10019<br>
    Attn: Alteration Deposit
  </p>
  <p style="margin:4px 0;">Write <strong>{app.get('app_id')}</strong> in the memo line.</p>
  <p style="margin:12px 0 0; font-size:13px; color:#555;">
    ✅ Once mailed, please confirm at your
    <a href="{status_url}"><strong>application status page</strong></a>
    by clicking <strong>"Deposit Check Mailed."</strong>
  </p>
</div>

<div style="background:#fffbea; border:2px solid #f0ad4e; border-radius:6px; padding:16px 20px; margin:16px 0;">
  <strong>Step 2 — Send Neighbor Notification Letters</strong>
  <p style="margin:8px 0;">You must notify the residents of the apartments directly <strong>above, below,
  and on both sides</strong> of yours at least <strong>3 business days before work begins.</strong></p>
  <p style="margin:4px 0; font-size:13px; color:#555;">
    A pre-populated letter template is included at the bottom of this email.
    You may email it or print and slip it under each neighbor's door — no CC to us required.
  </p>
  <p style="margin:12px 0 0; font-size:13px; color:#555;">
    ✅ Once letters have been sent, please confirm at your
    <a href="{status_url}"><strong>application status page</strong></a>
    by clicking <strong>"Neighbor Letters Sent."</strong>
  </p>
</div>

<h3 style="color:#1a5276;">Additional Steps Before Work Begins</h3>
<ul>
  <li><strong>Contractor pre-approval:</strong> Your contractors must be registered with BuildingLink
      before arriving at the building. Contact the super to arrange this.</li>
  <li><strong>Permits:</strong> Obtain all required permits before work starts. Email copies to
      <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>.</li>
</ul>

<h3 style="color:#1a5276;">Work Hours</h3>
<p>Monday through Friday only, 9:00 AM to 4:30 PM. No work on holidays.<br>
Plumbing shutdowns must be scheduled 48–72 hours in advance (any weekday, Mon–Fri).</p>

<p><strong>Do not begin work until both required steps above are complete and you have received
your countersigned alteration agreement.</strong></p>

<p>Congratulations, and please reach out at <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>
with any questions.</p>

<hr style="border:none; border-top:2px solid #eee; margin:32px 0 24px;">

<h3 style="color:#1a5276;">Neighbor Notification Letter Template</h3>
<p style="font-size:13px; color:#555; margin-bottom:16px;">
  Use this letter for each neighbor. You may email it directly or print and slip under their door.
  Fill in the <strong>[bracketed]</strong> fields before sending.
</p>

<div style="background:#f9f9f9; border:1px solid #ddd; border-radius:4px;
            padding:20px 24px; font-family:Georgia,serif; font-size:14px; line-height:1.7;">
<p style="margin:0 0 16px;">[Date: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;]</p>

<p style="margin:0 0 8px;">Dear Neighbor,</p>

<p style="margin:0 0 12px;">Pursuant to the Rules of 433 West 34th Street, I am writing to notify you that on
approximately <strong>{start_display}</strong>, I will commence renovation work in
<strong>Apartment {app.get('apartment')}</strong> at 433 West 34th Street.</p>

<p style="margin:0 0 12px;">I will instruct my contractors to exercise care to minimize noise during construction.
While it is impossible to eliminate all noise, I appreciate your patience during this period.</p>

<p style="margin:0 0 12px;">The renovation is expected to be completed within approximately
<strong>{duration_display}</strong>.</p>

<p style="margin:0 0 12px;">As required by building rules, please be advised that I will indemnify you for any
damages you sustain as a result of this renovation. I request that you allow the superintendent
or my representative to inspect your apartment prior to the start of work.</p>

<p style="margin:0 0 24px;">Please contact me to schedule an inspection at your convenience.</p>

<p style="margin:0 0 4px;">Very truly yours,</p>
<p style="margin:0 0 4px;"><strong>{app.get('shareholder_name')}</strong></p>
<p style="margin:0 0 4px;">Apartment {app.get('apartment')}, 433 West 34th Street</p>
<p style="margin:0 0 16px;">Phone: [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;]</p>

<p style="margin:0; font-size:13px; color:#666;">
cc: The Managing Agent's Designated Alteration Coordinator<br>
Orsid Realty Corp. d/b/a Orsid New York, 156 West 56th Street, 6th Floor, New York, NY 10019
</p>
</div>
""")


# ── Eddie: FYI on approval ────────────────────────────────────────────────────

def eddie_approval_email(app: dict) -> str:
    riser_note = ""
    if app.get("riser_flag") == "yes":
        riser_note = """
<div style="background:#fff3cd; border-left:4px solid #f0ad4e; padding:12px 16px; margin:16px 0;">
<strong>Reminder:</strong> This project was flagged for riser assessment. Please confirm with the board
when you are ready to conduct the pre-demo riser inspection.
</div>
"""
    return _wrap(f"""
<p>Hi Eddie,</p>

<p>The Board has approved the alteration application for <strong>Apt {app.get('apartment')}</strong>
({app.get('shareholder_name')}).</p>

{riser_note}

<p>The shareholder will be sending neighbor notification letters and obtaining permits before work begins.
You will be contacted to register the contractor(s) in BuildingLink prior to the start of work.</p>

<p>Please reach out if you have any concerns.</p>
""")


# ── Shareholder: neighbor letter template ─────────────────────────────────────

def neighbor_letter_email(app: dict) -> str:
    return _wrap(f"""
<p>Dear {app.get('shareholder_name', 'Shareholder')},</p>

<p>Now that your alteration has been approved, you must send notification letters to your neighbors
in the apartments directly <strong>above, below, and on both sides</strong> of yours, at least
<strong>3 business days before work begins</strong>.</p>

<p>Please email each neighbor individually and <strong>CC <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a></strong>
so we can log receipt. Below is the standard template — fill in the blanks and adjust as needed.</p>

<hr style="border:none; border-top:1px solid #eee; margin:24px 0;">

<p><em>[Your Name]<br>
[Your Address]<br>
[Date]</em></p>

<p>Dear Neighbor,</p>

<p>Pursuant to the Rules of 433 West 34th Street, I am writing to notify you that on approximately
<strong>[START DATE]</strong>, I will commence renovation work in my apartment.</p>

<p>I will instruct my contractors to exercise care to minimize noise during construction.
While it is impossible to eliminate all noise, I appreciate your patience during this period.</p>

<p>The renovation is expected to be completed within approximately <strong>[NUMBER]</strong> calendar days.</p>

<p>As required by building rules, please be advised that I will indemnify you for any damages you
sustain as a result of this renovation. I request that you allow the superintendent or my representative
to inspect your apartment prior to the start of work.</p>

<p>Please contact me to schedule an inspection at your convenience.</p>

<p>Very truly yours,<br>
[Your Name]<br>
[Phone]</p>

<p>cc: The Managing Agent's Designated Alteration Coordinator<br>
Orsid Realty Corp. d/b/a Orsid New York, 156 West 56th Street, 6th Floor, New York, NY 10019</p>

<hr style="border:none; border-top:1px solid #eee; margin:24px 0;">

<p>Once you have sent the letters, please confirm on your
<a href="{APP_URL}/status/[APP_ID]">application status page</a> so we can update your record.</p>
""")


# ── Architect report forwarding ───────────────────────────────────────────────

def _reply_instructions(app: dict, audience: str = "shareholder") -> str:
    """
    Prominent reply instruction box included in every forwarding email.
    audience: "shareholder" or "architect"
    """
    if audience == "shareholder":
        action = "respond to the architect's comments"
    else:
        action = "submit further comments or your approval recommendation"
    return f"""
<div style="background:#e8f4fd; border:2px solid #2980b9; border-radius:6px;
            padding:16px 20px; margin:20px 0;">
  <strong>📧 How to respond:</strong> Reply directly to this email — your Application ID
  <strong>{app.get('app_id')}</strong> is already in the subject line and will route your
  response automatically. Alternatively, email
  <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a> with
  <strong>{app.get('app_id')}</strong> anywhere in the subject line.<br>
  <span style="font-size:13px; color:#555; margin-top:6px; display:block;">
    All correspondence is logged and stored. Do not email the architect or board directly —
    use this address to keep your application record complete.
  </span>
</div>
"""


def architect_review_forward_email(app: dict, cover_note: str, round_label: str = "initial") -> str:
    """
    Email sent to shareholder + GC when an architect report arrives.
    cover_note is Claude's navigational summary. The original PDF is always attached separately.
    """
    gc_line = f"<p style='color:#555; font-size:13px;'>cc: {app.get('gc_name')} ({app.get('gc_company')})</p>" if app.get('gc_email') else ""

    if cover_note:
        body = cover_note
    else:
        # Fallback if Claude unavailable
        body = f"""
<p>Dear {app.get('shareholder_name', 'Shareholder')},</p>
{gc_line}
<p>The reviewing architect has submitted their {round_label} comments on your alteration application
for Apartment <strong>{app.get('apartment')}</strong>. Please review the attached report carefully —
it is the official document.</p>
<p>Please respond to each numbered item in writing, in sequence, within 10 business days.</p>
"""

    return _wrap(f"""
{body}
{_reply_instructions(app, audience="shareholder")}
<hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
<p style="font-size:12px; color:#aaa;">
  Application ID: <strong>{app.get('app_id')}</strong> &nbsp;·&nbsp; Apartment {app.get('apartment')}<br>
  Track your application:
  <a href="{APP_URL}/status/{app.get('app_id')}">{APP_URL}/status/{app.get('app_id')}</a>
</p>
""")


def shareholder_response_forward_email(app: dict, sender_name: str, attachment_count: int) -> str:
    """
    Email sent to the architect when a shareholder/GC response is received.
    The original attachments are forwarded separately.
    """
    att_note = f"{attachment_count} document(s) attached." if attachment_count else "No attachments — response was text only."
    return _wrap(f"""
<p>Dear {app.get('architect_assigned', 'Architect')} team,</p>

<p>A response has been received from the shareholder/contractor for
<strong>Apartment {app.get('apartment')}</strong> regarding application
<strong>{app.get('app_id')}</strong>.</p>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Apartment</td>
      <td style="padding:6px 12px;">{app.get('apartment')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Shareholder</td>
      <td style="padding:6px 12px;">{app.get('shareholder_name')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Sent by</td>
      <td style="padding:6px 12px;">{sender_name}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Documents</td>
      <td style="padding:6px 12px;">{att_note}</td></tr>
</table>

<p>The shareholder's response and any attached documents are included with this email.
All documents have also been added to the application's Drive folder.</p>

{_reply_instructions(app, audience="architect")}
""")


# ── Board: architect final recommendation alert ───────────────────────────────

def board_architect_recommendation_email(app: dict, recommendation: str, cover_note: str) -> str:
    """
    Alert sent to the board when Claude detects a final architect recommendation.
    Includes a direct link to the admin panel to review and vote.
    """
    rec_map = {
        "approve": (
            "✅ Recommends Approval",
            "#27ae60",
            "#f0fff4",
            "The architect has completed their review and recommends board approval.",
        ),
        "approve_with_conditions": (
            "⚠️ Recommends Approval with Conditions",
            "#e67e22",
            "#fef9ec",
            "The architect recommends approval subject to conditions stated in their report. "
            "Please review carefully before voting.",
        ),
        "deny": (
            "❌ Recommends Denial",
            "#e74c3c",
            "#fdf2f2",
            "The architect recommends the board <strong>deny</strong> this application. "
            "Please review their report before responding to the shareholder.",
        ),
    }
    label, color, bg, context = rec_map.get(
        recommendation,
        ("Review Complete", "#555", "#f9f9f9", "The architect has completed their review.")
    )
    admin_url = f"{APP_URL}/admin/application/{app.get('app_id')}"

    summary_section = ""
    if cover_note:
        summary_section = f"""
<h3>Architect Report Summary</h3>
<div style="background:#f9f9f9; border-left:3px solid #ccc; padding:12px 16px;
            margin:16px 0; font-size:13px; color:#444;">
{cover_note}
</div>
<p style="font-size:12px; color:#aaa; margin-top:0;">
  The original architect report PDF is attached to this email and filed in the Drive folder.
</p>
"""

    return _wrap(f"""
<h2>Architect Review Complete — Action Required</h2>

<div style="background:{bg}; border:2px solid {color}; border-radius:6px;
            padding:16px 20px; margin:20px 0;">
  <strong style="color:{color}; font-size:16px;">{label}</strong><br>
  <span style="color:#444; margin-top:6px; display:block;">{context}</span>
</div>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Apartment</td>
      <td style="padding:6px 12px;">{app.get('apartment')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Shareholder</td>
      <td style="padding:6px 12px;">{app.get('shareholder_name')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Reviewing Architect</td>
      <td style="padding:6px 12px;">{app.get('architect_assigned', '—')}</td></tr>
</table>

{summary_section}

<p>📁 <a href="{app.get('drive_folder_url', '#')}">View all application documents in Drive</a></p>

<div style="margin-top:24px; text-align:center;">
  <a href="{admin_url}"
     style="background:#1a5276; color:white; padding:14px 28px; text-decoration:none;
            border-radius:4px; font-size:15px; display:inline-block;">
    Review &amp; Vote →
  </a>
</div>

<p style="font-size:12px; color:#aaa; margin-top:24px;">
  This alert was generated automatically. If the architect's email was misclassified as a final
  recommendation, no action is needed — the status can be corrected in the admin panel.
</p>
""")


# ── Shareholder: work in progress ────────────────────────────────────────────

def work_in_progress_email(app: dict) -> str:
    """Sent to shareholder/GC when board marks work as underway."""
    return _wrap(f"""
<p>Dear {app.get('shareholder_name', 'Shareholder')},</p>

<p>This confirms that work on your alteration at Apartment <strong>{app.get('apartment')}</strong>
has been noted as underway.</p>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Status</td>
      <td style="padding:6px 12px; color:#e67e22;"><strong>Work In Progress</strong></td></tr>
</table>

<p>A reminder of the building's work rules:</p>
<ul>
  <li>Work hours: <strong>Monday–Friday, 9:00 AM to 4:30 PM only.</strong> No work on holidays.</li>
  <li>Plumbing shutdowns must be scheduled 48–72 hours in advance (Tuesdays–Thursdays only).</li>
  <li>All contractors must remain pre-registered in BuildingLink before arriving at the building.</li>
  <li>All common areas must be kept clean — debris from your work must be removed same-day.</li>
</ul>

<p>Please reach out to <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a> with any
questions or if your expected completion date changes.</p>
""")


# ── Shareholder: project sign-off (permits closed) ────────────────────────────

def sign_off_email(app: dict) -> str:
    """Sent to shareholder/GC when permits are signed off and deposit return is initiated."""
    return _wrap(f"""
<p>Dear {app.get('shareholder_name', 'Shareholder')},</p>

<p>Good news — the permit(s) for your alteration at Apartment <strong>{app.get('apartment')}</strong>
have been signed off and closed.</p>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Status</td>
      <td style="padding:6px 12px; color:#27ae60;"><strong>Project Sign-Off Complete</strong></td></tr>
</table>

<p>We are now initiating the return of your security deposit with Orsid Realty. You should receive
your deposit check within <strong>4–6 weeks</strong>, provided there are no outstanding issues with
your alteration agreement or building account.</p>

<p>If you have any questions about the deposit return, please contact Orsid Realty directly or
reach out to us at <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>.</p>

<p>Thank you for working with the building through this process. We hope you enjoy your
newly renovated apartment!</p>
""")


# ── Shareholder: project complete (deposit returned) ─────────────────────────

def complete_email(app: dict) -> str:
    """Sent to shareholder/GC when the board confirms the deposit has been returned — project fully closed."""
    return _wrap(f"""
<p>Dear {app.get('shareholder_name', 'Shareholder')},</p>

<p>We are pleased to confirm that your alteration application for Apartment
<strong>{app.get('apartment')}</strong> is now <strong>fully complete</strong>.</p>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app.get('app_id')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Status</td>
      <td style="padding:6px 12px; color:#27ae60;"><strong>Complete</strong></td></tr>
</table>

<p>Your security deposit has been processed for return by Orsid Realty. If you have not yet
received your check, please allow a few additional business days. If there are any issues,
contact Orsid Realty at 212-247-1040 or reach out to us at
<a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>.</p>

<p>Congratulations on completing your renovation. We hope you enjoy your updated home!</p>
""")


# ── Board: scope change alert ────────────────────────────────────────────────

def scope_change_alert_email(app: dict, detection: dict, submitted_by: str, filenames: str) -> str:
    """
    Alert sent to board when a revised scope document contains material additions.
    detection is the dict returned by claude_service.detect_scope_change().
    """
    app_id = app.get("app_id")
    admin_url = f"{APP_URL}/admin/application/{app_id}"

    additions = detection.get("additions", [])
    removals = detection.get("removals", [])

    expansion_rows = ""
    compliance_rows = ""
    minor_rows = ""
    for a in additions:
        item = a.get("item", "")
        t = a.get("type", "minor")
        if t == "expansion":
            expansion_rows += f'<tr><td style="padding:6px 10px;">🔴 {item}</td><td style="padding:6px 10px; color:#c0392b;">Scope expansion — board review needed</td></tr>'
        elif t == "compliance":
            compliance_rows += f'<tr><td style="padding:6px 10px;">🟡 {item}</td><td style="padding:6px 10px; color:#7d6608;">Building-required compliance</td></tr>'
        else:
            minor_rows += f'<tr><td style="padding:6px 10px;">⚪ {item}</td><td style="padding:6px 10px; color:#555;">Minor addition</td></tr>'

    additions_table = ""
    if expansion_rows or compliance_rows or minor_rows:
        additions_table = f"""
<h3 style="margin-top:20px;">Changes in revised scope</h3>
<table style="border-collapse:collapse; width:100%; font-size:13px; margin-bottom:16px;">
  <thead>
    <tr style="background:#f4f6f7;">
      <th style="padding:6px 10px; text-align:left;">Item</th>
      <th style="padding:6px 10px; text-align:left;">Classification</th>
    </tr>
  </thead>
  <tbody>
    {expansion_rows}{compliance_rows}{minor_rows}
  </tbody>
</table>
"""

    removals_section = ""
    if removals:
        removal_items = "".join(f"<li>{r}</li>" for r in removals)
        removals_section = f"""
<h3 style="margin-top:16px;">Items removed from original scope</h3>
<ul style="font-size:13px; color:#555;">{removal_items}</ul>
"""

    return _wrap(f"""
<div style="background:#fdf2f2; border-left:4px solid #c0392b; padding:12px 16px; margin-bottom:20px;">
  <strong>⚠️ Scope Change Detected — Board Review Required</strong><br>
  <span style="font-size:13px;">A revised scope document for Apt <strong>{app.get('apartment')}</strong>
  contains additions that were not part of the original approved scope.</span>
</div>

<table style="border-collapse:collapse; width:100%; margin:16px 0;">
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold; width:40%;">Application ID</td>
      <td style="padding:6px 12px;">{app_id}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Apartment</td>
      <td style="padding:6px 12px;">{app.get('apartment')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Shareholder</td>
      <td style="padding:6px 12px;">{app.get('shareholder_name')}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Submitted by</td>
      <td style="padding:6px 12px;">{submitted_by}</td></tr>
  <tr><td style="padding:6px 12px; background:#f4f6f7; font-weight:bold;">Documents</td>
      <td style="padding:6px 12px;">{filenames}</td></tr>
</table>

<h3>AI Assessment</h3>
<p style="color:#444;">{detection.get('summary', '')}</p>

{additions_table}
{removals_section}

<p style="font-size:13px; color:#555; margin-top:16px;">
  The revised scope has been forwarded to the architect as a normal response.
  If the additions above require re-review, the architect will raise them in their next report.
  No action needed unless you want to discuss with the shareholder proactively.
</p>

<div style="margin-top:20px; text-align:center;">
  <a href="{admin_url}"
     style="background:#1a5276; color:white; padding:12px 24px; text-decoration:none;
            border-radius:4px; font-size:15px;">
    View Application →
  </a>
</div>
""")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _security_deposit(estimated_cost_str: str) -> str:
    try:
        cost = float(str(estimated_cost_str).replace(",", "").replace("$", ""))
        deposit = max(2000, cost * 0.10)
        return f"${deposit:,.0f}"
    except (ValueError, TypeError):
        return "$2,000 minimum"
