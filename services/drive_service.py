import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from services.google_auth import get_credentials
import google.oauth2.service_account


ROOT_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")


def _service():
    creds = get_credentials()
    return build("drive", "v3", credentials=creds)


def create_application_folder(app_id: str, apartment: str) -> tuple[str, str]:
    """Create a Drive folder for this application. Returns (folder_id, folder_url)."""
    svc = _service()
    folder_name = f"{app_id} — Apt {apartment}"
    meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if ROOT_FOLDER_ID:
        meta["parents"] = [ROOT_FOLDER_ID]
    folder = svc.files().create(body=meta, fields="id, webViewLink").execute()
    folder_id = folder["id"]
    # Make folder viewable by anyone with the link
    svc.permissions().create(
        fileId=folder_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()
    return folder_id, folder.get("webViewLink", "")


def upload_file(folder_id: str, file_storage) -> str:
    """Upload a Flask FileStorage object to Drive. Returns file URL."""
    svc = _service()
    meta = {"name": file_storage.filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(file_storage.stream, mimetype=file_storage.content_type, resumable=True)
    uploaded = svc.files().create(body=meta, media_body=media, fields="id, webViewLink").execute()
    return uploaded.get("webViewLink", "")


def upload_bytes(folder_id: str, filename: str, data: bytes, mime_type: str = "application/octet-stream") -> str:
    """Upload raw bytes to Drive (e.g. attachment from incoming email). Returns file URL."""
    import io
    svc = _service()
    meta = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=True)
    uploaded = svc.files().create(body=meta, media_body=media, fields="id, webViewLink").execute()
    return uploaded.get("webViewLink", "")
