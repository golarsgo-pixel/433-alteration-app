import os
import json
from datetime import datetime
from typing import Optional
from googleapiclient.discovery import build
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


def _service():
    creds = get_credentials()
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


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
    svc = _service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="Sheet1!A1:A1"
    ).execute()
    if not result.get("values"):
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": [COLUMNS]},
        ).execute()


def append_application(data: dict):
    ensure_header()
    row = [str(data.get(col, "")) for col in COLUMNS]
    _service().spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range="Sheet1!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def get_all_applications() -> list[dict]:
    svc = _service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="Sheet1"
    ).execute()
    rows = result.get("values", [])
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
    """Find the row for app_id and update a single field."""
    svc = _service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="Sheet1"
    ).execute()
    rows = result.get("values", [])
    if not rows:
        return
    header = rows[0]
    if "app_id" not in header or field not in header:
        return
    id_col = header.index("app_id")
    field_col = header.index(field)
    for i, row in enumerate(rows[1:], start=2):
        row_id = row[id_col] if id_col < len(row) else ""
        if row_id == app_id:
            cell = f"Sheet1!{_col_letter(field_col)}{i}"
            svc.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range=cell,
                valueInputOption="RAW",
                body={"values": [[str(value)]]},
            ).execute()
            return


# ── Activity log (separate "Log" tab) ─────────────────────────────────────────

LOG_COLUMNS = ["timestamp", "app_id", "apartment", "event", "detail", "actor"]

def _ensure_log_tab():
    """Create the Log tab and header row if they don't exist."""
    svc = _service()
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    sheet_names = [s["properties"]["title"] for s in meta.get("sheets", [])]

    if "Log" not in sheet_names:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": "Log"}}}]},
        ).execute()
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range="Log!A1",
            valueInputOption="RAW",
            body={"values": [LOG_COLUMNS]},
        ).execute()


def log_event(app_id: str, event: str, detail: str = "", actor: str = "system", apartment: str = ""):
    """
    Append one row to the Log tab.
    event:  short label  e.g. "Status: Architect Assigned", "Email: Receipt sent"
    detail: free text    e.g. "Assigned to Melone", "Forwarded to apt8d@email.com"
    actor:  who did it   e.g. "system", "board", "architect"
    """
    try:
        _ensure_log_tab()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [timestamp, app_id, apartment, event, detail, actor]
        _service().spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range="Log!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
    except Exception as e:
        # Log failures should never break the main flow
        import logging
        logging.getLogger(__name__).error(f"log_event failed: {e}")


def get_application_log(app_id: str) -> list:
    """Return all log entries for a given application, oldest first."""
    try:
        svc = _service()
        result = svc.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range="Log"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []
        header = rows[0]
        entries = [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in rows[1:]]
        return [e for e in entries if e.get("app_id") == app_id]
    except Exception:
        return []


# ── Settings (separate "Settings" tab) ────────────────────────────────────────

_SETTINGS_DEFAULTS = {
    "engineers_json":            "",
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


def _ensure_settings_tab():
    svc = _service()
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    sheet_names = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if "Settings" not in sheet_names:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": "Settings"}}}]},
        ).execute()
        # Seed with defaults, pulling from env vars for smooth migration
        seed = dict(_SETTINGS_DEFAULTS)
        seed["engineer_1_emails"]        = os.environ.get("MELONE_EMAILS", "")
        seed["engineer_2_email"]         = os.environ.get("CAPOBIANCO_EMAIL", "")
        seed["admin_email"]              = os.environ.get("ADMIN_EMAIL", "board@433w34.com")
        seed["superintendent_email"]     = os.environ.get("EDDIE_EMAIL", "")
        seed["orsid_coordinator_email"]  = os.environ.get("ORSID_CC_EMAILS", "")
        header = [["key", "value", "updated_at"]]
        rows = [[k, v, datetime.now().strftime("%Y-%m-%d")] for k, v in seed.items()]
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range="Settings!A1",
            valueInputOption="RAW",
            body={"values": header + rows},
        ).execute()


def get_settings() -> dict:
    try:
        _ensure_settings_tab()
        svc = _service()
        result = svc.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range="Settings"
        ).execute()
        rows = result.get("values", [])
        # Start with hardcoded defaults, then layer env vars, then sheet values
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
    svc = _service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="Settings"
    ).execute()
    rows = result.get("values", [])
    existing_keys = {row[0]: i + 2 for i, row in enumerate(rows[1:]) if row}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for key, value in updates.items():
        if key in existing_keys:
            row_num = existing_keys[key]
            svc.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range=f"Settings!B{row_num}:C{row_num}",
                valueInputOption="RAW",
                body={"values": [[str(value), now]]},
            ).execute()
        else:
            svc.spreadsheets().values().append(
                spreadsheetId=SHEET_ID,
                range="Settings!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [[key, str(value), now]]},
            ).execute()
