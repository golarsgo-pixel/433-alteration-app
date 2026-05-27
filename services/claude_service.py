import os
import json
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

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
- Wood studs (except door openings), combustible framing
- Satellite dish antennas (unless inside apt)
- Kilns, humidifiers supplying steam/water into ductwork
- No structural cuts, no facade penetrations, no load-bearing wall removal
- No cutting/channeling of floor slab
- No jackhammer use without written approval
- Wet-over-dry installations prohibited

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

DOCUMENT COMPLETENESS CHECKLIST:
For Decoration Projects: Simple form + $1,000 deposit
For Full Alterations — Phase 1 required at submission:
  - Standard Alteration Agreement (signed)
  - Addendum A: Typical Requirements (acknowledged)
  - Addendum B: Project Summary (scope, dates, plans/sketches)
  - Addendum C: Assumption of Alteration Agreement
  - Security deposit: greater of $2,000 or 10% of projected cost
  - Shareholder liability insurance
Phase 2 (also required at submission per current policy):
  - Addendum D: Contractor Information + licenses
  - Addendum E: Contractor Insurance (COI naming Corp, Orsid Realty Corp., and adjacent neighbors as additional insureds)
    - $1M bodily injury/property damage, $5M umbrella, workers comp
  - Addendum F: Contractor Indemnity Agreement
  - W-9 form
  - EPA Lead certification for contractors
  - If plumbing: plumber's license
  - If electrical: electrician's license
Neighbor letters are sent AFTER approval, not at submission.
DOB permits are obtained AFTER board approval.

WASHER/DRYER POLICY: Only allowed when replacing a kitchen AND removing a sink & dishwasher. Condensing/self-venting type only. No wall penetrations or window exhaust.

WORK HOURS: Monday–Friday only, 9am–4:30pm. No work on holidays.
PLUMBING SHUTDOWNS: Tuesdays, Wednesdays, Thursdays only. 48–72 hour advance notice required.
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

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

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
   - Send their written response to alterations@433w34.com with Application ID
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

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
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

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
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
        return {"is_final": False, "recommendation": "more_info"}


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
4. Reminds them to reply to alterations@433w34.com and to include their company stamp/signature on any technical responses
5. Sets a polite but firm expectation for timely response (suggest 10 business days)

Write in a professional but warm tone. Sign as "433 West 34th Street Board of Directors".
Return just the email body as plain HTML (no subject line).
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
