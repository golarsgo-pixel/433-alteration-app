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
    permit_note = ""
    if app.get("permit_required") == "yes":
        permit_note = """
<div style="background:#d6eaf8; border-left:4px solid #2980b9; padding:12px 16px; margin:16px 0;">
<strong>Permits Required:</strong> The reviewing architect has indicated that one or more permits are required
before work may begin. Your contractor must file for and obtain all required permits and provide copies to
<a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a> before commencing work.
</div>
""".format(ALTERATIONS_EMAIL=ALTERATIONS_EMAIL)

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

<h3>Before Work May Begin — Required Steps</h3>
<ol>
  <li><strong>Neighbor Notification Letters:</strong> You must send written notification to the residents
      of the apartments directly above, below, and on both sides of yours at least 3 business days before
      work begins. Please CC <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a> on those emails
      (or forward copies to us). A template will be sent to you separately.</li>
  <li><strong>Permits:</strong> Obtain all required permits and email copies to
      <a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>.</li>
  <li><strong>Contractor Pre-Approval:</strong> Your contractors must be registered with BuildingLink
      before arriving at the building. Contractors arriving without pre-approval will be turned away.</li>
  <li><strong>Security Deposit:</strong> Confirm that your security deposit has been received by Orsid.</li>
</ol>

<h3>Work Hours</h3>
<p>Monday through Friday only, 9:00 AM to 4:30 PM. No work on holidays.<br>
Plumbing shutdowns must be requested at least 48–72 hours in advance and are only available
on Tuesdays, Wednesdays, and Thursdays.</p>

<p><strong>Do not begin work until you have confirmed all of the above and received
your countersigned alteration agreement.</strong></p>

<p>Congratulations, and please reach out with any questions.</p>
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

<p>cc: 433 West 34th Street Board of Directors
(<a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a>)</p>

<hr style="border:none; border-top:1px solid #eee; margin:24px 0;">

<p>Once you have sent the letters, please forward confirmations (or CC us directly) to
<a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a> so we can update your application.</p>
""")


# ── Architect report forwarding ───────────────────────────────────────────────

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
<p>Please respond to each numbered item in writing, in sequence, and send your response to
<a href="mailto:{ALTERATIONS_EMAIL}">{ALTERATIONS_EMAIL}</a> with your Application ID
<strong>{app.get('app_id')}</strong> in the subject line. Respond within 10 business days.</p>
"""

    return _wrap(f"""
{body}
<hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
<p style="font-size:12px; color:#aaa;">
  Application ID: <strong>{app.get('app_id')}</strong> &nbsp;·&nbsp; Apartment {app.get('apartment')}<br>
  Track your application:
  <a href="{APP_URL}/status/{app.get('app_id')}">{APP_URL}/status/{app.get('app_id')}</a>
</p>
""")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _security_deposit(estimated_cost_str: str) -> str:
    try:
        cost = float(str(estimated_cost_str).replace(",", "").replace("$", ""))
        deposit = max(2000, cost * 0.10)
        return f"${deposit:,.0f}"
    except (ValueError, TypeError):
        return "$2,000 minimum"
