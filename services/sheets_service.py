import os
from datetime import datetime
from typing import Optional
import gspread
from services.google_auth import get_credentials

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")

# Column order must match COLUMNS list exactly
COLUMNS = [
    "app_id", "submitted_at", "status", "apartment",
    "shareholder_name", "shareholder_email", "shareholder_phone",
    "project_type", "scope_description", "estimated_cost",
    "start_date", "end_date",
    "gc_name", "gc_company", "gc_email", "gc_phone",
    "plumber_name", "electrician_name",
    "involves_plumbing", "involves_electrical", "involves_structural",
    "involves_kitchen", "involves_bathroom",
    "involves_flooring_refinish", "involves_flooring_replace",
    "architect_assigned", "expediting",
    "ai_review_summary", "riser_flag", "scope_change_flag",
    "permit_required", "permits",
    "payment_status", "application_fee_status", "neighbor_letters_sent",
    "drive_folder_url", "notes",
]

# Cached gspread objects — rebuilt on process restart (deploy), not per-request
_gspread_client = None
_spreadsheet_obj = None


def _spreadsheet():
    """Return (and lazily init) the cached gspread Spreadsheet object."""
    global _gspread_client, _spreadsheet_obj
    if _spreadsheet_obj is None:
        _gspread_client = gspread.authorize(get_credentials())
        _spreadsheet_obj = _gspread_client.open_by_key(SHEET_ID)
    return _spreadsheet_obj


def _col_letter(index: int) -> str:
    """Convert 0-based column index to spreadsheet letter (A, B, … Z, AA…)."""
    result = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def ensure_header():
    """Write the header row if the sheet is empty."""
    ws = _spreadsheet().worksheet("Sheet1")
    if not ws.acell("A1").value:
        ws.update("A1", [COLUMNS])


def append_application(data: dict):
    ensure_header()
    row = [str(data.get(col, "")) for col in COLUMNS]
    _spreadsheet().worksheet("Sheet1").append_row(row, value_input_option="RAW")


def get_all_applications() -> list[dict]:
    rows = _spreadsheet().worksheet("Sheet1").get_all_values()
    if len(rows) < 2:
        return []
    header = rows[0]
    return [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in rows[1:]]


def get_application(app_id: str) -> Optional[dict]:
    apps = get_all_applications()
    for a in apps:
        if a.get("app_id") == app_id:
            return a
    return None


def update_application_field(app_id: str, field: str, value: str):
    """Update a single field. Prefer update_application_fields() when changing multiple fields."""
    update_application_fields(app_id, {field: value})


def update_application_fields(app_id: str, updates: dict):
    """Update multiple fields for one application in a single batch call."""
    ws = _spreadsheet().worksheet("Sheet1")
    rows = ws.get_all_values()
    if not rows:
        return
    header = rows[0]
    if "app_id" not in header:
        return
    id_col = header.index("app_id")
    for i, row in enumerate(rows[1:], start=2):
        if (id_col < len(row) and row[id_col] == app_id):
            batch_data = []
            for field, value in updates.items():
                if field in header:
                    col = header.index(field)
                    batch_data.append({
                        "range": f"{_col_letter(col)}{i}",
                        "values": [[str(value)]],
                    })
            if batch_data:
                ws.batch_update(batch_data)
            return


# ── Activity log (separate "Log" tab) ─────────────────────────────────────────

LOG_COLUMNS = ["timestamp", "app_id", "apartment", "event", "detail", "actor"]

# Cached after first confirmed existence — reset on process restart
_log_tab_ready = False


def _ensure_log_tab():
    global _log_tab_ready
    if _log_tab_ready:
        return
    sh = _spreadsheet()
    existing = [ws.title for ws in sh.worksheets()]
    if "Log" not in existing:
        ws = sh.add_worksheet(title="Log", rows=1000, cols=len(LOG_COLUMNS))
        ws.update("A1", [LOG_COLUMNS])
    _log_tab_ready = True


def log_event(app_id: str, event: str, detail: str = "", actor: str = "system", apartment: str = ""):
    try:
        _ensure_log_tab()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [timestamp, app_id, apartment, event, detail, actor]
        _spreadsheet().worksheet("Log").append_row(row, value_input_option="RAW")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"log_event failed: {e}")


def get_application_log(app_id: str) -> list:
    """Return all log entries for a given application, oldest first."""
    try:
        rows = _spreadsheet().worksheet("Log").get_all_values()
        if len(rows) < 2:
            return []
        header = rows[0]
        entries = [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in rows[1:]]
        return [e for e in entries if e.get("app_id") == app_id]
    except Exception:
        return []


# ── Votes (board vote tracking) ───────────────────────────────────────────────

VOTES_COLUMNS = ["app_id", "board_member_name", "board_member_email", "token", "vote", "voted_at"]

_votes_tab_ready = False


def _ensure_votes_tab():
    global _votes_tab_ready
    if _votes_tab_ready:
        return
    sh = _spreadsheet()
    existing = [ws.title for ws in sh.worksheets()]
    if "Votes" not in existing:
        ws = sh.add_worksheet(title="Votes", rows=500, cols=len(VOTES_COLUMNS))
        ws.update("A1", [VOTES_COLUMNS])
    _votes_tab_ready = True


def write_vote_tokens(app_id: str, members_with_tokens: list):
    """Append one row per board member to the Votes tab. members_with_tokens: [{name, email, token}]"""
    _ensure_votes_tab()
    rows = [[app_id, m["name"], m["email"], m["token"], "", ""] for m in members_with_tokens]
    _spreadsheet().worksheet("Votes").append_rows(rows, value_input_option="RAW")


def record_vote(token: str) -> tuple:
    """
    Find the vote row by token and mark it approved.
    Returns (app_id, approve_count) on success, (app_id, -1) if already voted,
    or (None, 0) if token not found.
    """
    _ensure_votes_tab()
    ws = _spreadsheet().worksheet("Votes")
    rows = ws.get_all_values()
    if len(rows) < 2:
        return None, 0
    header = rows[0]
    try:
        token_col    = header.index("token")
        vote_col     = header.index("vote")
        voted_at_col = header.index("voted_at")  # noqa: F841
        app_id_col   = header.index("app_id")
    except ValueError:
        return None, 0

    for i, row in enumerate(rows[1:], start=2):
        padded = row + [""] * (len(header) - len(row))
        if padded[token_col] != token:
            continue
        app_id = padded[app_id_col]
        if padded[vote_col] == "approved":
            return app_id, -1  # already voted
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        ws.batch_update([
            {"range": f"E{i}", "values": [["approved"]]},
            {"range": f"F{i}", "values": [[now]]},
        ])
        # Count approvals already recorded (before this vote) + 1 for the vote we just wrote
        prev_approvals = sum(
            1 for r in rows[1:]
            if len(r) > app_id_col and r[app_id_col] == app_id
            and len(r) > vote_col and r[vote_col] == "approved"
        )
        return app_id, prev_approvals + 1
    return None, 0


def get_pending_vote_rows(app_id: str) -> list:
    """Return pending (unvoted) rows for an application, INCLUDING tokens, for reminder emails."""
    try:
        _ensure_votes_tab()
        rows = _spreadsheet().worksheet("Votes").get_all_values()
        if len(rows) < 2:
            return []
        header = rows[0]
        entries = [
            dict(zip(header, r + [""] * (len(header) - len(r))))
            for r in rows[1:]
        ]
        return [
            e for e in entries
            if e.get("app_id") == app_id and e.get("vote") != "approved"
        ]
    except Exception:
        return []


def lookup_vote_token(app_id: str, token: str) -> dict:
    """Validate a vote token and return its state (includes token check).
    Returns {"valid": bool, "already_voted": bool, "voter_name": str}."""
    try:
        _ensure_votes_tab()
        rows = _spreadsheet().worksheet("Votes").get_all_values()
        if len(rows) < 2:
            return {"valid": False, "already_voted": False, "voter_name": ""}
        header = rows[0]
        token_col  = header.index("token")
        app_id_col = header.index("app_id")
        vote_col   = header.index("vote")
        name_col   = header.index("board_member_name")
        for row in rows[1:]:
            padded = row + [""] * (len(header) - len(row))
            if padded[token_col] == token and padded[app_id_col] == app_id:
                return {
                    "valid": True,
                    "already_voted": padded[vote_col] == "approved",
                    "voter_name": padded[name_col],
                }
        return {"valid": False, "already_voted": False, "voter_name": ""}
    except Exception:
        return {"valid": False, "already_voted": False, "voter_name": ""}


def get_votes_for_app(app_id: str) -> list:
    """Return all vote rows for an application as list of dicts (token excluded)."""
    try:
        _ensure_votes_tab()
        rows = _spreadsheet().worksheet("Votes").get_all_values()
        if len(rows) < 2:
            return []
        header = rows[0]
        entries = [
            dict(zip(header, r + [""] * (len(header) - len(r))))
            for r in rows[1:]
        ]
        return [
            {k: v for k, v in e.items() if k != "token"}
            for e in entries if e.get("app_id") == app_id
        ]
    except Exception:
        return []


# ── Settings (separate "Settings" tab) ────────────────────────────────────────

_SETTINGS_DEFAULTS = {
    "engineers_json":            "",
    "board_members_json":        "",
    "admin_email":               "board@433w34.com",
    "superintendent_name":       "",
    "superintendent_email":      "",
    "orsid_coordinator_name":    "",
    "orsid_coordinator_email":   "",
    "orsid_fee_billing_json":    "",
    "orsid_fee_billing_emails":  "mminter@orsidny.com,EDODAJ@orsidny.com,lbehri@orsidny.com",
    # Legacy keys kept for fallback only — superseded by engineers_json
    "engineer_1_key":            "Melone",
    "engineer_1_label":          "Melone Architects (Jeremy Welsh + Nick Melone)",
    "engineer_1_emails":         "",
    "engineer_2_key":            "Capobianco",
    "engineer_2_label":          "Capobianco Group (Thomas Capobianco, P.E.)",
    "engineer_2_email":          "",
}

# Cached after first confirmed existence — reset on process restart
_settings_tab_ready = False


def _ensure_settings_tab():
    global _settings_tab_ready
    if _settings_tab_ready:
        return
    sh = _spreadsheet()
    existing = [ws.title for ws in sh.worksheets()]
    if "Settings" not in existing:
        ws = sh.add_worksheet(title="Settings", rows=100, cols=3)
        seed = dict(_SETTINGS_DEFAULTS)
        seed["engineer_1_emails"]        = os.environ.get("MELONE_EMAILS", "")
        seed["engineer_2_email"]         = os.environ.get("CAPOBIANCO_EMAIL", "")
        seed["admin_email"]              = os.environ.get("ADMIN_EMAIL", "board@433w34.com")
        seed["superintendent_email"]     = os.environ.get("EDDIE_EMAIL", "")
        seed["orsid_coordinator_email"]  = os.environ.get("ORSID_CC_EMAILS", "")
        header = [["key", "value", "updated_at"]]
        rows = [[k, v, datetime.now().strftime("%Y-%m-%d")] for k, v in seed.items()]
        ws.update("A1", header + rows)
    _settings_tab_ready = True


def get_settings() -> dict:
    try:
        _ensure_settings_tab()
        rows = _spreadsheet().worksheet("Settings").get_all_values()
        settings = dict(_SETTINGS_DEFAULTS)
        settings["engineer_1_emails"]       = os.environ.get("MELONE_EMAILS", settings["engineer_1_emails"])
        settings["engineer_2_email"]        = os.environ.get("CAPOBIANCO_EMAIL", settings["engineer_2_email"])
        settings["admin_email"]             = os.environ.get("ADMIN_EMAIL", settings["admin_email"])
        settings["superintendent_email"]    = os.environ.get("EDDIE_EMAIL", settings["superintendent_email"])
        settings["orsid_coordinator_email"] = os.environ.get("ORSID_CC_EMAILS", settings["orsid_coordinator_email"])
        for row in rows[1:]:
            if len(row) >= 2 and row[0]:
                settings[row[0]] = row[1]
        return settings
    except Exception:
        settings = dict(_SETTINGS_DEFAULTS)
        settings["engineer_1_emails"]       = os.environ.get("MELONE_EMAILS", "")
        settings["engineer_2_email"]        = os.environ.get("CAPOBIANCO_EMAIL", "")
        settings["admin_email"]             = os.environ.get("ADMIN_EMAIL", "board@433w34.com")
        settings["superintendent_email"]    = os.environ.get("EDDIE_EMAIL", "")
        settings["orsid_coordinator_email"] = os.environ.get("ORSID_CC_EMAILS", "")
        return settings


def save_settings(updates: dict):
    _ensure_settings_tab()
    ws = _spreadsheet().worksheet("Settings")
    rows = ws.get_all_values()
    existing_keys = {row[0]: i + 2 for i, row in enumerate(rows[1:]) if row}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    batch_data = []
    new_rows = []
    for key, value in updates.items():
        if key in existing_keys:
            row_num = existing_keys[key]
            batch_data.append({
                "range": f"B{row_num}:C{row_num}",
                "values": [[str(value), now]],
            })
        else:
            new_rows.append([key, str(value), now])

    if batch_data:
        ws.batch_update(batch_data)

    for row in new_rows:
        ws.append_row(row, value_input_option="RAW")
