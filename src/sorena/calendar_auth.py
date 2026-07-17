"""Google Calendar OAuth: installed-app flow (not a service account -- this
is your personal calendar, not a domain to administer). First call opens a
browser for one-time consent; every call after reads the cached token from
disk and silently refreshes it when it expires.
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CREDENTIALS_PATH = _DATA_DIR / "google_credentials.json"
TOKEN_PATH = _DATA_DIR / "google_token.json"


def _get_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_PATH} -- download an OAuth 'Desktop app' "
                    "client from Google Cloud Console and save it there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


_service: Resource | None = None


def get_calendar_service() -> Resource:
    """Authorized Calendar API client, singleton per process. Opens a
    browser for consent on first-ever call; silent after that."""
    global _service
    if _service is None:
        _service = build("calendar", "v3", credentials=_get_credentials())
    return _service
