import os
import json
from services.ai_usage_logger import log_usage

_anthropic_client = None

def _client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _anthropic_client

ALTERATION_AGREEMENT_CONTEXT = """
You are reviewing alteration applications for 433 West 34th Street Owners Corp., a NYC co-op.

KEY RULES FROM THE ALTERATION AGREEMENT:

PROHIBITED ITEMS (automatic flags):
- Garbage disposals
- Whirlpool tubs, air jet tubs (without board written approval)
- Saunas, steam rooms, steam generators
- Thru-wall or central air conditioning units
- Automatic ice-making refrigerators
- Wall-mounted toilets (without board written approval)
- Concealed-tank toilets, offset flange toilets
- Non-Energy Star appliances
- Lead paint, asbestos-containing materials
- Wood studs (except door openings) and combustible framing in wall/partition construction
  (plywood subfloor is permitted and governed by flooring replacement requirements)
- Satellite dish antennas (unless inside apt)
- Kilns, humidifiers supplying steam/water into ductwork
- No structural cuts, no load-bearing wall removal
- No cutting/channeling of floor slab
- No jackhammer use without written approval
- Wet-over-dry installations prohibited
- Venting of any appliance or equipment into shared building shafts, riser chases, pipe chases, or architectural voids
- Exterior facade penetrations for venting/mechanical without specific written Board approval
- Vented dryer exhaust under any circumstances — condensing (ventless) dryers only
- Smart lock or electronic entry door hardware without prior Board approval (entry door is Corp property)

RISER RISK: Flag as TRUE if the scope includes ANY of:
- Kitchen renovation (plumbing, new sink, relocation of fixtures)
- Bathroom renovation (plumbing, tub/shower work, fixture replacement)
- Any branch plumbing work, pipe replacement, or work near risers
- Removal of existing flooring in kitchen or bathroom
- Any work described as opening walls near kitchen or bath
Riser risk means: the building may need to do parallel riser work. Eddie (super) should assess riser condition before demo begins.

PERMIT LIKELY REQUIRED if scope includes:
- Room partition relocations
- Kitchen or bathroom fixture relocation more than 12 inches
- Division of rooms
- Suspended ceiling work
- Asbestos abatement
- Converting tub to shower
- Any plumbing or electrical work (permit may be required)
- Gas piping changes (DOB permit required, no self-certification)
- Electrical service upgrades or any dedicated circuit of 50 amps or greater (requires Board + Engineer approval)

DOCUMENT COMPLETENESS CHECKLIST:
For Decoration Projects: Simple form + $1,000 deposit
For Full Alterations — all submitted together:
  - Standard Alteration Agreement (signed)
  - Addendum A: Typical Requirements (acknowledged)
  - Addendum B: Project Summary (scope, dates, plans/sketches)
  - Addendum C: Contractor Information + licenses
  - Addendum D: Contractor Insurance (COI naming Corp, Orsid Realty Corp. d/b/a Orsid New York,
    and adjacent neighbors as additional insureds — $1M bodily injury/property damage, $5M umbrella, workers comp)
  - Addendum E: Contractor Indemnity Agreement
  - Addendum F: Neighbor Notification Letter (sent AFTER approval, not at submission)
  - Security deposit: greater of $2,000 or 10% of projected cost
  - Shareholder liability insurance
  - W-9 form
  - EPA Lead certification for contractors
  - If plumbing: plumber's license
  - If electrical: electrician's license
DOB permits are obtained AFTER board approval, before work begins.
Note: "Assumption of Alteration Agreement" (formerly Addendum C) has been eliminated from the current agreement.

COI NAMED INSUREDS: 433 West 34th Street Owners Corp., its Officers, Directors & Shareholders, Orsid Realty Corp.
d/b/a Orsid New York (Managing Agent), the Corporation's Designated Engineer, and the shareholder(s)
in the apartment directly below the work apartment. Adjacent neighbors are NOT required. Terra Holdings is NOT a required named insured.

WASHER/DRYER POLICY: Prohibited as a standalone alteration. May be considered by the Board ONLY in
connection with a full kitchen renovation or the combination of two or more apartments where a new
kitchen is being created. Must be located in the kitchen only. Requires a $5,000 non-refundable license
fee (returned only if Board denies the application) in addition to standard security deposit. Condensing
(ventless) dryer only — no vented exhaust permitted under any circumstances. Detailed technical
requirements apply (stainless steel overflow pan with auto-shutoff, braided stainless supply hoses, etc.).
Flag any washer/dryer mention and note that standalone w/d alteration is not permitted.

MOLD / MOISTURE: If work involves opening walls, floors, or ceilings near a bathroom, kitchen, laundry
area, or plumbing riser, and mold or water damage is discovered, work must STOP in the affected area
and the shareholder must notify the Managing Agent and Superintendent in writing before proceeding.
This is a material obligation — flag scope that involves significant opening of wet-area walls.

BUILDINGLINK: Upon approval, the Managing Agent will register approved contractors in the building's
BuildingLink system. No contractor may enter the building for work-related purposes until confirmed as
registered. Shareholder must notify Managing Agent of any roster changes promptly.

SMART LOCKS / IoT DEVICES: The apartment entry (hallway) door is owned by the Corporation.
Any modification to entry door hardware — including smart locks, electronic locks, keypads — requires
prior written Board approval and must retain a physical key override compatible with the master key.
Self-contained IoT devices entirely inside the apartment and not connected to building systems are
generally permitted without Board approval (undersink sensors, motion sensors, in-kind smart thermostat).
Any IoT device connecting to building electrical, HVAC, plumbing, intercom, or network infrastructure
requires prior written Board approval.

WORK HOURS: Monday–Friday only, 9am–4:30pm. All workers must leave by 4:30pm. No work on holidays.
PLUMBING SHUTDOWNS: Any weekday (Monday–Friday). 48–72 hour advance written notice required.
Requests must specify riser(s) affected, estimated duration, and licensed plumber responsible.
"""


def review_application(data: dict) -> dict:
    """
    Review a submitted application using Claude.
    Returns a dict with: summary, riser_risk, permit_likely, missing_docs, flags, permit_types
    """
    scope = data.get("scope_description", "")
    project_type = data.get("project_type", "alteration")
    estimated_cost = data.get("estimated_cost", "unknown")
    involves_plumbing = data.get("involves_plumbing", "no") == "yes"
    involves_electrical = data.get("involves_electrical", "no") == "yes"
    involves_structural = data.get("involves_structural", "no") == "yes"
    involves_kitchen = data.get("involves_kitchen", "no") == "yes"
    involves_bathroom = data.get("involves_bathroom", "no") == "yes"
    gc_name = data.get("gc_name", "not provided")
    plumber = data.get("plumber_name", "not provided")
    electrician = data.get("electrician_name", "not provided")

    prompt = f"""
{ALTERATION_AGREEMENT_CONTEXT}

APPLICATION DETAILS:
- Apartment: {data.get('apartment')}
- Project type selected: {project_type}
- Estimated cost: ${estimated_cost}
- Involves plumbing: {involves_plumbing}
- Involves electrical: {involves_electrical}
- Involves structural: {involves_structural}
- Involves kitchen: {involves_kitchen}
- Involves bathroom: {involves_bathroom}
- General contractor: {gc_name}
- Plumber listed: {plumber}
- Electrician listed: {electrician}

SCOPE OF WORK (as described by the shareholder/GC):
{scope}

Please review this application and return a JSON object with exactly these keys:
{{
  "summary": "2-4 sentence plain-English summary of what the project involves and the overall status of the review",
  "riser_risk": true or false,
  "permit_likely": true or false,
  "permit_types": ["list of permit types likely needed, e.g. Plumbing, Electrical, LAA, DOB"],
  "project_type_correct": true or false (does the selected project type match the scope?),
  "project_type_note": "explanation if incorrect, otherwise empty string",
  "prohibited_items": ["list any prohibited items or rule violations found in the scope"],
  "missing_docs": ["list any documents that appear to be missing based on the scope"],
  "flags": ["any other concerns or items that need board attention"],
  "riser_note": "plain-English explanation of the riser risk if applicable, otherwise empty string"
}}

Be specific and practical. If riser_risk is true, the riser_note should explain which part of the scope triggers this and what Eddie should check before demo begins. Only flag things that are actually relevant to this specific scope.
"""

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    log_usage("review_application", response.model, response.usage.input_tokens, response.usage.output_tokens)

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    result = json.loads(text)
    return result


def summarize_architect_report(
    architect_report_text: str,
    application_data: dict,
    round_label: str = "initial",
) -> str:
    """
    Write a brief cover note to accompany the architect's report when forwarding to the shareholder.
    The original PDF is always attached — this is a navigational aid only, not an official document.
    Returns HTML.
    """
    prompt = f"""
You are helping the board of 433 West 34th Street Owners Corp. forward an architect's {round_label} review
report to a shareholder and their contractor.

ARCHITECT'S REPORT TEXT:
---
{architect_report_text[:4000]}
---

Write a brief, professional cover note to accompany the original attached report. The cover note must:

1. Open with one sentence stating that the architect's {round_label} review comments are attached.
2. List each numbered item from the architect's report as a short bullet — use the architect's own words
   closely, do not interpret or add advice. Each bullet should start with the item number.
3. Include a clear instruction block telling the shareholder to:
   - Review the ATTACHED report — it is the official document, not this summary
   - Respond to each item in the same numbered sequence as the report
   - Send their written response to apps@433w34.com with Application ID
     {application_data.get('app_id')} in the subject line
   - Include their contractor's signature/stamp on any technical responses (drawings, specs)
   - Respond within 10 business days

CRITICAL RULES:
- Do NOT rewrite, interpret, or add your own opinions to the architect's items
- Do NOT sign as the architect or imply this is the official report
- The attached PDF is the authoritative document — say so explicitly
- Sign as: 433 West 34th Street Board of Directors
- Return only the email body as HTML (no subject line, no <html>/<body> tags)
"""

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    log_usage("summarize_architect_report", response.model, response.usage.input_tokens, response.usage.output_tokens)
    return response.content[0].text.strip()


def classify_architect_report(report_text: str, app_id: str) -> dict:
    """
    Determine whether an architect email is a final recommendation (review complete)
    or an intermediate round of comments/requests.

    Returns {"is_final": bool, "recommendation": str}
    recommendation values: "approve" | "approve_with_conditions" | "deny" | "more_info"

    Conservative: only marks is_final=True when clearly concluded.
    """
    prompt = f"""You are helping manage a co-op alteration review process at 433 West 34th Street, NYC.

An architect has sent an email regarding application {app_id}. Classify this email:

1. Is this a FINAL recommendation — the architect has CONCLUDED their review and is formally
   recommending approval, approval with conditions, or denial?
   OR is this INTERMEDIATE — the architect is still working through the review (requesting
   more documents, asking questions, sending partial comments, acknowledging receipt)?

2. If final, what is the recommendation?

EMAIL TEXT:
---
{report_text[:3000]}
---

Respond in JSON only — no other text:
{{"is_final": true or false, "recommendation": "approve" | "approve_with_conditions" | "deny" | "more_info"}}

Definitions:
- "approve": architect explicitly recommends approval or states no objections
- "approve_with_conditions": architect recommends approval but requires certain items be addressed first
- "deny": architect recommends the board not approve the application
- "more_info": architect is still in review (asking questions, requesting documents, sending comments for response)

Be CONSERVATIVE — only set is_final=true if you are confident the architect has concluded
their review. When in doubt, use is_final=false and recommendation="more_info"."""

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    log_usage("classify_architect_report", response.model, response.usage.input_tokens, response.usage.output_tokens)
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        return {"is_final": False, "recommendation": "more_info"}


def detect_scope_change(
    original_scope: str,
    new_document_text: str,
    app_id: str,
) -> dict:
    """
    Compare a contractor's revised scope document to the original approved scope.
    Classifies additions as genuine expansion vs. building-required compliance.

    Returns:
    {
        "is_scope_document": bool,
        "has_material_additions": bool,
        "additions": [{"item": str, "type": "expansion"|"compliance"|"minor"}],
        "removals": [str],
        "board_alert": bool,
        "summary": str
    }
    """
    prompt = f"""You are reviewing a contractor document submitted during an ongoing architect review
for an alteration at 433 West 34th Street, NYC co-op (application {app_id}).

ORIGINAL APPROVED SCOPE (what the board and architect are reviewing):
---
{original_scope[:3000]}
---

NEW DOCUMENT SUBMITTED BY CONTRACTOR/SHAREHOLDER:
---
{new_document_text[:3000]}
---

BUILDING COMPLIANCE REQUIREMENTS (items the architect routinely requires that are NOT new scope):
- Branch plumbing replacement back to building risers (copper supply lines, waste/vent lines)
- New shutoff valves at fixtures
- Water hammer arrestors and check valves
- Waterproofing membrane (Laticrete 9235) turned up 4 inches
- Stone saddle at wet/dry transitions
- Subfloor + soundproofing underlayment when flooring is replaced
- Licensed plumber and electrician confirmations

TASK:
1. First, determine: is this new document a revised scope of work (SOW), or is it a text
   response to architect comments with no new scope items? A SOW typically lists work items
   (install, remove, replace, etc.). A response letter quotes architect items and confirms them.

2. If it IS a scope document, compare it to the original and identify:
   - ADDITIONS: work items present in the new doc but NOT in the original
   - REMOVALS: work items in the original that are absent or explicitly removed in the new doc

3. For each addition, classify as:
   - "expansion": new work not in original scope AND not a building compliance requirement
     (e.g., adding a new appliance, extending work to a new room, adding a new fixture type)
   - "compliance": additions that match building requirements listed above — the architect
     likely required these, they do not represent new work the board needs to re-evaluate
   - "minor": small additions unlikely to affect building systems or require re-review
     (e.g., replacing a closet door, painting a room)

4. Set board_alert=true if ANY "expansion" additions are found. These require the board to
   decide whether the expanded scope is acceptable and whether a new review round is needed.

Respond in JSON only:
{{
  "is_scope_document": true or false,
  "has_material_additions": true or false,
  "additions": [
    {{"item": "description of added item", "type": "expansion"|"compliance"|"minor"}}
  ],
  "removals": ["description of removed item"],
  "board_alert": true or false,
  "summary": "2-3 sentence plain-English assessment of what changed and why it matters"
}}

If is_scope_document is false, return additions=[], removals=[], has_material_additions=false,
board_alert=false, and a summary explaining this appears to be a response letter, not a scope revision."""

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        return {
            "is_scope_document": False,
            "has_material_additions": False,
            "additions": [],
            "removals": [],
            "board_alert": False,
            "summary": "Scope change detection failed — manual review recommended.",
        }


_STATUS_DESCRIPTIONS = {
    "Received":            "Application received and under initial review.",
    "Pending Assignment":  "Being assigned to the board's reviewing architect.",
    "Architect Assigned":  "Assigned to the reviewing architect — technical review will begin shortly.",
    "Architect Review":    "Architect technical review is currently in progress.",
    "Awaiting Board Vote": "Architect review is complete. The board is now voting on approval.",
    "Board Approved":      "The board has approved the application. The shareholder will receive formal approval documentation and next steps.",
    "Changes Required":    "The board has requested changes to the application before it can be approved.",
    "Work In Progress":    "Application approved and work is underway.",
    "Project Sign-Off":    "Work is complete and awaiting final sign-off.",
    "Complete":            "Project is complete and the application is closed out.",
    "Withdrawn":           "Application has been withdrawn.",
    "On Hold":             "Application is currently on hold.",
    "Rejected":            "Application has been rejected.",
}


def draft_auto_reply(email_subject: str, email_body: str, app: dict = None) -> dict:
    """
    Classify an inbound email to the alterations inbox and draft a reply if appropriate.
    Returns {"send_reply": bool, "reply_body": str (plain text)}.
    """
    app_context = ""
    if app:
        status = app.get("status", "")
        status_note = _STATUS_DESCRIPTIONS.get(status, status)
        app_context = f"""
REFERENCED APPLICATION:
- App ID: {app.get('app_id')}
- Apartment: {app.get('apartment')}
- Shareholder: {app.get('shareholder_name')}
- Current Status: {status} — {status_note}
- Project: {app.get('scope_description', '')[:300]}

Use this application context to give a specific, accurate reply about their application and what happens next.
"""

    prompt = f"""You manage inbound emails for the Alteration Review process at 433 West 34th Street Owners Corp., a NYC co-op.

The alterations inbox (apps@433w34.com) has received an email that was not automatically handled by the routing system. Your job:

1. Classify the email as LEGITIMATE (a genuine inquiry, question, or communication related to building alterations, the co-op, or an existing application) or NOT_LEGITIMATE (spam, promotional, clearly misdirected, automated delivery receipts, out-of-office replies, or completely irrelevant).

2. If LEGITIMATE, draft a helpful and professional reply.

KEY FACTS FOR REPLIES:
- Building: 433 West 34th Street, New York, NY 10001
- To start an alteration application: https://four33-alteration-app.onrender.com/apply
- To check application status: https://four33-alteration-app.onrender.com/status
- All alteration work requires board approval before it begins
- Work hours: Monday–Friday, 9am–4:30pm only (no weekends, no holidays)
- Application fee is billed separately through the building's managing agent
- For follow-up questions, people can reply to this email and the board will follow up
- Sign off as: The Alteration Review Team, 433 West 34th Street Owners Corp
{app_context}
INBOUND EMAIL:
Subject: {email_subject}
Body:
{email_body[:2000]}

Respond in JSON only — no other text:
{{"send_reply": true or false, "reply_body": "..."}}

reply_body must be plain text only (no HTML). Paragraphs separated by blank lines.
Start with "Dear [first name if identifiable, otherwise 'Resident']," and end with a professional sign-off.
If send_reply is false, set reply_body to "".
"""

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    log_usage("draft_auto_reply", response.model, response.usage.input_tokens, response.usage.output_tokens)
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        return {"send_reply": False, "reply_body": ""}


def draft_architect_questions_response(
    architect_report_text: str,
    application_data: dict,
) -> str:
    """
    Given an architect's report/questions, draft a response for the shareholder/GC to address.
    Returns HTML-formatted email body.
    """
    prompt = f"""
{ALTERATION_AGREEMENT_CONTEXT}

You are helping the board of 433 West 34th Street Owners Corp. manage an alteration application.

The building's reviewing architect has sent the following report/questions for apartment {application_data.get('apartment')}:

--- ARCHITECT REPORT ---
{architect_report_text}
--- END REPORT ---

The project scope was: {application_data.get('scope_description', '')}

Please draft a clear, professional forwarding email to the shareholder and their GC that:
1. Briefly explains what the architect's report is and what they need to do
2. Lists each item the architect is asking about, in plain English (numbered)
3. Explains that they should respond to each item in writing, with any supporting documentation
4. Reminds them to reply to apps@433w34.com and to include their company stamp/signature on any technical responses
5. Sets a polite but firm expectation for timely response (suggest 10 business days)

Write in a professional but warm tone. Sign as "433 West 34th Street Board of Directors".
Return just the email body as plain HTML (no subject line).
"""

    response = _client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    log_usage("draft_architect_questions_response", response.model, response.usage.input_tokens, response.usage.output_tokens)
    return response.content[0].text.strip()
