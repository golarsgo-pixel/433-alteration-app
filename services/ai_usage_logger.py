import logging
from datetime import datetime
import gspread
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

# Cached gspread objects — rebuilt on process restart, not per-call
_gspread_client = None
_spreadsheet_obj = None
_tab_ready = False


def _spreadsheet():
    global _gspread_client, _spreadsheet_obj
    if _spreadsheet_obj is None:
        _gspread_client = gspread.authorize(get_credentials())
        _spreadsheet_obj = _gspread_client.open_by_key(COST_TRACKER_SHEET_ID)
    return _spreadsheet_obj


def _ensure_tab():
    global _tab_ready
    if _tab_ready:
        return
    sh = _spreadsheet()
    existing = [ws.title for ws in sh.worksheets()]
    if TAB_NAME not in existing:
        ws = sh.add_worksheet(title=TAB_NAME, rows=1000, cols=len(COLUMNS))
        ws.update("A1", [COLUMNS])
    _tab_ready = True


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
        _spreadsheet().worksheet(TAB_NAME).append_row(row, value_input_option="RAW")
    except Exception as e:
        _log.error(f"ai_usage_logger failed: {e}")
