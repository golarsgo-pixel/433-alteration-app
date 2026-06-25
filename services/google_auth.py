import os
import json
import functools
from flask import session, redirect, url_for, request, has_request_context
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import google.auth.transport.requests

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

BOARD_EMAIL = os.environ.get("BOARD_EMAIL", "board@433w34.com")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "token.json")


def _make_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [os.environ["GOOGLE_REDIRECT_URI"]],
            }
        },
        scopes=SCOPES,
        redirect_uri=os.environ["GOOGLE_REDIRECT_URI"],
    )


def get_auth_url():
    flow = _make_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    session["oauth_state"] = state
    return auth_url


def _cred_dict_to_credentials(cred_data: dict) -> Credentials:
    creds = Credentials(
        token=cred_data.get("token"),
        refresh_token=cred_data.get("refresh_token"),
        token_uri=cred_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=cred_data.get("client_id"),
        client_secret=cred_data.get("client_secret"),
        scopes=cred_data.get("scopes", SCOPES),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(google.auth.transport.requests.Request())
    return creds


def _save_token(creds: Credentials):
    """Persist credentials to token.json for server-side (non-session) use."""
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)


def handle_callback(args):
    """Process the OAuth callback. Returns error string or None on success."""
    if "error" in args:
        return args["error"]
    try:
        flow = _make_flow()
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials

        import googleapiclient.discovery
        service = googleapiclient.discovery.build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        email = user_info.get("email", "")

        if email.lower() != BOARD_EMAIL.lower():
            return f"Access denied: {email} is not authorised."

        cred_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or SCOPES),
        }
        session["user_email"] = email
        session["credentials"] = cred_data

        # Persist so server-side (public form) operations can use these credentials
        _save_token(creds)
        return None
    except Exception as e:
        return str(e)


def _bootstrap_token_from_env():
    """Write token.json from GOOGLE_TOKEN_JSON env var if the file doesn't exist yet.
    This lets Render survive redeploys without losing credentials."""
    if os.path.exists(TOKEN_FILE):
        return
    token_json = os.environ.get("GOOGLE_TOKEN_JSON", "").strip()
    if token_json:
        try:
            data = json.loads(token_json)
            with open(TOKEN_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass


def get_credentials():
    """
    Return valid Credentials. Tries session first (admin routes),
    then falls back to token.json (server-side / public routes).
    Raises RuntimeError if neither is available.
    """
    # Restore token.json from env var if missing (e.g. after Render redeploy)
    _bootstrap_token_from_env()

    # 1. Try session (board is actively logged in) — only available inside a request
    cred_data = session.get("credentials") if has_request_context() else None
    if cred_data:
        creds = _cred_dict_to_credentials(cred_data)
        # Refresh session with updated token
        session["credentials"] = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or SCOPES),
        }
        return creds

    # 2. Fall back to stored token.json (used by public form submissions)
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            cred_data = json.load(f)
        creds = _cred_dict_to_credentials(cred_data)
        _save_token(creds)  # Save refreshed token back
        return creds

    raise RuntimeError(
        "No Google credentials available. The board member must log in at /auth/login first "
        "to authorise the application."
    )


def require_board_login(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_email"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated
