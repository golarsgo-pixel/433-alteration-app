# 433 W 34th St — Alteration App: Context & Decision Log

This document captures the reasoning, decisions, and institutional knowledge behind this app
so future Claude Code sessions can pick up without re-explaining everything from scratch.

---

## What This App Does

Replaces Orsid Realty's alteration review service for 433 West 34th Street Owners Corp.
Orsid charged ~$1,000 per alteration and provided limited transparency to shareholders.
This app automates the intake, routing, review, and tracking workflow entirely.

**The flow:**
1. Shareholder submits application at `/apply` with all required documents
2. Claude AI reviews the submission and flags issues (riser risk, missing docs, etc.)
3. Documents upload to a Google Drive folder automatically
4. Application is logged to Google Sheets
5. Board gets an action-required email; Eddie (super) gets an FYI
6. Board logs into `/admin`, reviews, and assigns a reviewing architect
7. Architect gets a packaged email with all documents and the Drive folder link
8. Board approves → shareholder and GC get approval email with next steps
9. Shareholder tracks status at `/status` using their Application ID

---

## Key People & Roles

| Person | Role | Email |
|--------|------|-------|
| Jeremy Kuhn | Board President, app owner | board@433w34.com |
| Eddie Rodriguez | Building superintendent | rodriguezeddie374@gmail.com |
| Connor McGrath | Orsid property manager | cmcgrath@orsidny.com |
| John DeVall | Orsid property manager | jdevall@orsidny.com |
| Melone Architects | Reviewing architect option 1 | jeremy@melonearchitects.com, nick@melonearchitects.com |
| Capobianco Group | Reviewing architect option 2 | tom.sr@capobiancogroup.com |

---

## Two Project Tracks

**Decoration Project** (simpler):
- Painting, floor refinishing, carpeting, like-for-like fixture/appliance replacement
- Requires only the Simple Form for Apartment Alterations
- Security deposit: $1,000

**Full Alteration** (standard):
- Any structural, plumbing, electrical, kitchen/bath renovation, or layout changes
- Requires all Phase 1 + Phase 2 documents at time of submission
- Security deposit: greater of $2,000 or 10% of projected cost

---

## Document Requirements (Full Alteration)

All submitted upfront (no partial submissions):
- Plans / drawings / sketches
- Signed Alteration Agreement + Addenda A, B, C
- Addendum D: Contractor info, licenses, schedule
- Addendum E: Certificate of Insurance — must name the Corp, its officers/directors/shareholders,
  Orsid Realty Corp., the Corp's Designated Engineer, AND shareholders below and adjacent to the
  apartment as additional insureds. Min coverage: $1M GL, $5M umbrella, workers comp.
  *(Verified against actual alteration agreement Section 3(c) — adjacent neighbors DO need to be named)*
- Addendum F: Contractor Indemnity Agreement
- W-9
- Plumber's license (if plumbing work)
- Electrician's license (if electrical work)
- EPA Lead certification
- Shareholder liability insurance (optional)
- Any additional docs (cut sheets, appliance specs, etc.)

Neighbor notification letters are sent AFTER board approval — not at submission.

---

## Workflow Logic & Key Decisions

### Why we check documents before assigning an architect
Architects (Melone or Capobianco) bill back to the shareholder via maintenance charges through Orsid.
If we assign before the package is complete, the architect will kick it back, the shareholder pays
for a wasted review, and it creates frustration. So the workflow is:
1. Receive submission
2. Board confirms package is complete (manually, for now)
3. Then assign architect

The confirmation page and receipt email both reflect this — they say "once your package is confirmed
complete" rather than "within 2 business days of submission."

### Why security deposit is step 5 (after board approval)
The deposit is collected after architect review, not at submission. Reason: if the architect requires
scope changes, the project cost (and therefore deposit amount) could change. No point collecting
before the review is done.

Architect fees are billed via Orsid maintenance charges — they don't need their own step in the checklist.

### Email account setup
- `apps@433w34.com` — the service account. Used for OAuth login, all outbound emails,
  and the public-facing contact address. Set up under Google Workspace.
- `board@433w34.com` — Jeremy's actual inbox. Receives board action alerts and inbound forwards.
- Gmail forwarding is set up so anything sent TO apps@433w34.com forwards to board@433w34.com.
  Jeremy replies from his board account personally (for now — auto-reply is a deferred feature).

### Why ADMIN_EMAIL ≠ BOARD_EMAIL in the code
BOARD_EMAIL is the account the app authenticates with (apps@433w34.com).
ADMIN_EMAIL is where board action alerts go (board@433w34.com, Jeremy's inbox).
They're separate env vars so the app can send alerts to the right place without conflating
the service account with Jeremy's personal board inbox.

### Riser flag
The Claude AI review checks for riser risk (any plumbing work near building risers).
If flagged, a warning banner appears on the shareholder's status page:
"The building superintendent will assess riser condition before demo begins."
Eddie is already CC'd on submissions so he sees it, but the flag creates a visible
reminder for the board too.

---

## Technical Architecture

| Component | Platform |
|-----------|----------|
| Web app | Python / Flask |
| Hosting | Render.com (free tier) |
| Code repository | GitHub (private): golarsgo-pixel/433-alteration-app |
| Documents | Google Drive (folder per application) |
| Application data | Google Sheets (one row per application) |
| Email | Gmail API (sends as apps@433w34.com) |
| AI review | Anthropic Claude API |
| Auth | Google OAuth 2.0 (board login only) |

**Render note:** Free tier sleeps after 15 min inactivity — first request after idle takes ~30 sec.
Upgrade to $7/month plan if that becomes annoying.

---

## How to Make Code Changes

1. Open Claude Code from this folder (`Dropbox/433 W 34 St Board/AI Projects/Alteration App`)
2. Make changes with Claude
3. Push to GitHub (requires token from 1Password: "GitHub token — 433 alteration app"):
   - Claude will run the git commands; you just provide the token when asked
4. Render auto-deploys within ~2 minutes

**Never set `OAUTHLIB_INSECURE_TRANSPORT=1` on Render** — that's a local-only dev setting.

---

## Google Sheet

- One row per application, 35 columns
- If columns are ever added to `services/sheets_service.py`, clear ALL rows including the
  header before the next submission so the fresh header is written correctly
- Sheet ID: `1_3LeHvkCN9L3cvuQc00cdphNK-ICstgxZqqZBsZ4xgA`

---

## Google OAuth & Token Persistence

The app uses OAuth to authenticate with Google (Gmail, Drive, Sheets).
On Render, the filesystem resets on every redeploy — so `token.json` would be lost.
Fix: `GOOGLE_TOKEN_JSON` environment variable on Render stores the token as a JSON string.
On startup, `google_auth.py` writes it to `token.json` automatically if the file is missing.

If Google ever revokes the token (rare), visit `https://four33-alteration-app.onrender.com/auth/login`,
log in with `apps@433w34.com`, then update the `GOOGLE_TOKEN_JSON` env var on Render
with the new contents of your local `token.json`.

---

## Deferred Features (not yet built)

- **Save draft on intake form** — would require server-side session storage or localStorage
- **Auto-reply to inbound emails** — monitor apps@433w34.com, pass to Claude, send response
- **Architect fee tracking** — currently handled by Orsid via maintenance charges, not in app

---

## Live URLs

| Page | URL |
|------|-----|
| Home | https://four33-alteration-app.onrender.com |
| Submit application | https://four33-alteration-app.onrender.com/apply |
| Check status | https://four33-alteration-app.onrender.com/status |
| Board admin panel | https://four33-alteration-app.onrender.com/admin |
| Board login | https://four33-alteration-app.onrender.com/auth/login |
