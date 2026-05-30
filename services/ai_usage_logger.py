import logging
from datetime import datetime
from googleapiclient.discovery import build
from services.google_auth import get_credentials

COST_TRACKER_SHEET_ID = "1LqyIIsSaSrnWR2sQc_znE7p87d5TVgCFmAsUTgj-kAU"
TAB_NAME = "Usage Log"

COLUMNS = ["Timestamp", "Script", "Function", "Model", "Input Tokens", "Output Tokens", "Est Cost USD"]

# Anthropic list prices per million tokens (mid-2025)
_PRICING = {
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-opus-4-8":   {"input": 15.00, "output": 75.00},
    "claude-haiku-4-5":  {"input": 0.80,  "output": 4.00},
}

_log = logging.getLogger(__name__)


def _service():
    return build("sheets", "v4", credentials=get_credentials())


def _ensure_tab():
    svc = _service()
    meta = svc.spreadsheets().get(spreadsheetId=COST_TRACKER_SHEET_ID).execute()
    names = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if TAB_NAME not in names:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=COST_TRACKER_SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": TAB_NAME}}}]},
        ).execute()
        svc.spreadsheets().values().update(
            spreadsheetId=COST_TRACKER_SHEET_ID,
            range=f"{TAB_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [COLUMNS]},
        ).execute()


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _PRICING.get(model, {"input": 3.00, "output": 15.00})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def log_usage(function_name: str, model: str, input_tokens: int, output_tokens: int):
    try:
        _ensure_tab()
        cost = _estimate_cost(model, input_tokens, output_tokens)
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Alteration App",
            function_name,
            model,
            input_tokens,
            output_tokens,
            round(cost, 6),
        ]
        _service().spreadsheets().values().append(
            spreadsheetId=COST_TRACKER_SHEET_ID,
            range=f"{TAB_NAME}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
    except Exception as e:
        _log.error(f"ai_usage_logger failed: {e}")
