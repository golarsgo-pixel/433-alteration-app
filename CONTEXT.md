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

### The Operator concept
`board@433w34.com` is the **institutional operator inbox** — it represents the co-op board as an
institution, not any individual. The current board president monitors it, but the address never
changes when board membership or the president role changes. Individual board members are not tracked
as separate email recipients anywhere in the app. When adding new notification logic, always address
it to the operator inbox, not to a named person's email.

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
| Hosting | Render.com (Starter, $7/month) |
| Code repository | GitHub (private): golarsgo-pixel/433-alteration-app |
| Documents | Google Drive (folder per application) |
| Application data | Google Sheets (one row per application) |
| Email | Gmail API (sends as apps@433w34.com) |
| AI review | Anthropic Claude API |
| Auth | Google OAuth 2.0 (board login only) |

**Render note:** Running on Starter plan ($7/month, 512 MB RAM, no sleep). Plan to upgrade to
Pro when real users are active and memory headroom becomes a concern.

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

## Design Principles: API Efficiency & Render Stability

Render Starter has 512 MB RAM. The Google API client library (`googleapiclient`) is memory-hungry —
building a service client parses a large discovery document and allocates significant heap. These
principles must be followed in every new feature and every change to existing code.

### 1. Cache service clients at module level
Every `build(...)` call fetches and parses the API discovery document. Never call it per-request.

```python
_client = None
def _service():
    global _client
    if _client is None:
        _client = build("sheets", "v4", credentials=get_credentials(), cache_discovery=False)
    return _client
```

This pattern exists in `sheets_service.py`, `gmail_service.py`, and `drive_service.py`.
**If you add a new Google API service, follow the same pattern.**

### 2. Batch Sheets writes — never loop individual `.update()` calls
Each `spreadsheets().values().update()` call is a separate HTTP round trip.
When writing multiple cells or rows, always use `.values().batchUpdate()` with a `data` array.

Bad:
```python
for key, value in updates.items():
    svc.spreadsheets().values().update(...).execute()  # N calls
```

Good:
```python
svc.spreadsheets().values().batchUpdate(
    spreadsheetId=SHEET_ID,
    body={"valueInputOption": "RAW", "data": [{"range": ..., "values": ...}, ...]},
).execute()  # 1 call
```

`save_settings()` and `update_application_fields()` both implement this correctly.
`update_application_field()` (singular) delegates to `update_application_fields()` — use the plural
version directly whenever updating more than one field at once.

### 3. Cache tab existence checks
`_ensure_log_tab()` and `_ensure_settings_tab()` each do a full `spreadsheets().get()` to verify
the tab exists. These are called on every `log_event()` and `get_settings()` call. After the first
run, the tabs never disappear, so the check is wasted work on every subsequent request.

Both functions use a module-level boolean flag (`_log_tab_ready`, `_settings_tab_ready`) that short-
circuits the check after the first confirmation. **If you add a new tab, follow the same pattern.**

### 4. Do the minimum synchronously on form submit; background everything else
The `/apply` submission route is the heaviest request in the app: Drive folder creation, file
uploads, Claude AI review, and multiple emails. Doing all of this before responding to the user
risks a 30-second+ request, a Render worker timeout, or a process restart losing the whole submission.

**The rule:** save the core application record to Sheets first (takes ~1 second), redirect the user
immediately, then do everything else in a daemon thread.

```python
append_application(data)           # Sheets write — data is safe
threading.Thread(target=_background, args=(...), daemon=True).start()
return redirect(url_for("submitted", app_id=app_id))  # user sees this immediately
```

The `_post_submit_background()` function in `app.py` handles Drive → Claude → emails.
If Render restarts mid-thread, the application row already exists in Sheets and is visible
in the admin dashboard. The Drive folder, AI review, and emails just need manual follow-up.

**File uploads:** `request.files` streams close when the HTTP request ends. Read all file bytes
into memory (`file.read()`) before starting the thread, then use `upload_bytes()` in the thread
instead of `upload_file()`.

### 5. Send one email per recipient group — never loop send_email
Each `send_email()` call builds a Gmail API round trip. When notifying multiple addresses in the
same role (e.g. two Orsid coordinators), pass comma-separated addresses as a single `to` or `cc`
argument — the Gmail API and MIME headers handle it correctly. Never loop.

---

## Design Principles: Configurability & Operational Settings

### Secrets vs. operational config — what goes where
Two categories of configuration, stored in two different places:

| Type | Where | Examples |
|------|-------|---------|
| **Secrets** | Render env vars only | `SECRET_KEY`, `GOOGLE_TOKEN_JSON`, `CRON_SECRET`, API keys |
| **Operational config** | Google Sheets Settings tab (editable via `/admin/settings`) | Contact names, email addresses, engineer list |

The rule: if a non-technical board member might ever need to update it (a contact changes, a new engineer is added), it belongs in Settings. If it would be dangerous in the wrong hands or is a credential, it stays in Render env vars and never touches the sheet.

### Settings priority chain
Settings are resolved in this order (highest priority wins):

```
Google Sheets Settings tab  →  Render env var  →  Hardcoded default
```

This means:
- The sheet always wins once populated — changes via the admin UI take effect immediately
- Env vars serve as a fallback for values not yet in the sheet (useful during migration)
- Hardcoded defaults ensure the app never crashes if both are missing

When adding a new configurable value, add it to `_SETTINGS_DEFAULTS` in `sheets_service.py`
and wire it through `get_settings()` following this pattern.

### Dynamic lists, not fixed slots
Any config that could ever need a third entry must be stored as a JSON array in the Settings sheet,
not as `_1` / `_2` fixed keys. We learned this with engineers — starting with `engineer_1_key` /
`engineer_2_key` meant adding a third firm required a code change. Now `engineers_json` is a list
and adding a firm is a UI action.

Apply the same pattern to anything list-like: fee billing contacts, future notification groups, etc.
Store as `[{"key": ..., "label": ..., ...}]` JSON, parse with a `_parse_*()` helper that falls
back to legacy keys if the JSON key is empty.

### No-redeploy rule for operational changes
Any contact, label, or workflow setting that might change over time must be editable from the
`/admin/settings` UI without touching code or Render env vars. Before adding a new hardcoded value
(name, email, label, toggle), ask: "Would a board member ever need to change this?" If yes, put it
in Settings.

---

## Design Principles: Templates & Frontend

### Jinja2 auto-escaping — use `&` not `&amp;` in expressions
Jinja2 auto-escapes HTML inside `{{ }}` expressions. If you write `&amp;` inside an expression,
it gets double-escaped and renders literally as `&amp;` in the browser.

```html
<!-- Wrong — renders as "Assign &amp; Notify" -->
{{ 'Assign &amp; Notify Engineer' }}

<!-- Correct — Jinja2 escapes & to &amp; for you -->
{{ 'Assign & Notify Engineer' }}
```

Outside of `{{ }}` expressions (plain HTML), write `&amp;` as normal.

### Currency formatting — always use the `comma` filter
Any dollar amount that could exceed $999 must use the `| comma` Jinja2 filter to render with
a thousands separator. The filter is registered in `app.py` and handles strings, ints, and floats.

```html
${{ app.estimated_cost | comma }}   {# renders as $25,000 not $25000 #}
```

---

## Deferred Features (not yet built)

- **Save draft on intake form** — would require server-side session storage or localStorage
- **Auto-reply to inbound emails** — monitor apps@433w34.com, pass to Claude, send response
- **Architect fee tracking** — currently handled by Orsid via maintenance charges, not in app
- **Stripe application fee ($250)** — collect at submission; do alongside the ownership migrations below
- **GitHub repo → 433-owned org** — currently under golarsgo-pixel (Jeremy's personal account);
  move to a 433 W 34 St org so it survives board member transitions
- **Render account → 433-owned account** — same reason; do at the same time as GitHub migration
  so both happen in one coordinated handoff

---

## Live URLs

| Page | URL |
|------|-----|
| Home | https://four33-alteration-app.onrender.com |
| Submit application | https://four33-alteration-app.onrender.com/apply |
| Check status | https://four33-alteration-app.onrender.com/status |
| Board admin panel | https://four33-alteration-app.onrender.com/admin |
| Board login | https://four33-alteration-app.onrender.com/auth/login |
