"""Google Sheets CRM adapter.

Appends one row per completed call to a user-owned Google Sheet.
Auth uses a Google Service Account — the user pastes the full service-account
JSON as the ``api_key``.  No extra pip packages: JWT signing is done with the
``cryptography`` library already in requirements.txt.

Setup (one-time, done by the platform user):
  1. GCP Console → APIs & Services → Enable "Google Sheets API"
  2. IAM → Service Accounts → Create → Download JSON key
  3. Open the target sheet → Share with the service-account email (Editor)
  4. Paste the JSON key into the API-key field here; set the Spreadsheet ID.

Row format (auto-header written on first use):
  Timestamp | Phone | Name | Email | Disposition | Duration (s) |
  Sentiment | Quality Score | Summary | Recording URL | Transcript URL | Run ID
"""

from __future__ import annotations

import base64
import json
import math
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from loguru import logger

from api.services.integrations.crm.base import CallLog, CRMProvider, CRMSyncResult

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"

_HEADERS = [
    "Timestamp", "Phone", "Name", "Email", "Disposition",
    "Duration (s)", "Sentiment", "Quality Score", "Summary",
    "Recording URL", "Transcript URL", "Run ID",
]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_jwt(sa_email: str, private_key_pem: str) -> str:
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "iss": sa_email,
        "scope": _SCOPE,
        "aud": _TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }).encode())
    signing_input = f"{header}.{payload}".encode()
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(), password=None
    )
    sig = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())  # type: ignore[arg-type]
    return f"{header}.{payload}.{_b64url(sig)}"


class GoogleSheetsProvider(CRMProvider):
    name = "google_sheets"

    def __init__(
        self,
        service_account_json: str,
        spreadsheet_id: str,
        sheet_name: str = "Calls",
        timeout: float = 15.0,
    ):
        self._sa_json = service_account_json
        self._spreadsheet_id = spreadsheet_id
        self._sheet_name = sheet_name
        self._timeout = timeout

    def _parse_sa(self) -> tuple[str, str]:
        """Return (client_email, private_key_pem) from service-account JSON."""
        sa = json.loads(self._sa_json)
        return sa["client_email"], sa["private_key"]

    async def _get_access_token(self, client: httpx.AsyncClient) -> str:
        email, key_pem = self._parse_sa()
        jwt = _make_jwt(email, key_pem)
        resp = await client.post(
            _TOKEN_URL,
            data={"grant_type": _GRANT_TYPE, "assertion": jwt},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def sync_call(self, call: CallLog) -> CRMSyncResult:
        try:
            sa = json.loads(self._sa_json)
            _ = sa["client_email"], sa["private_key"]
        except Exception as exc:
            return CRMSyncResult(ok=False, detail=f"invalid_service_account_json: {exc}")

        if not self._spreadsheet_id:
            return CRMSyncResult(ok=False, detail="spreadsheet_id_missing")

        sheet_range = f"{self._sheet_name}!A1"
        values_url = f"{_SHEETS_BASE}/{self._spreadsheet_id}/values"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                token = await self._get_access_token(client)
                headers = {"Authorization": f"Bearer {token}"}

                # Check if the header row exists (A1 empty → write it first).
                check = await client.get(
                    f"{values_url}/{sheet_range}",
                    headers=headers,
                    params={"majorDimension": "ROWS"},
                )
                existing = (check.json().get("values") or []) if check.is_success else []
                if not existing:
                    await client.post(
                        f"{values_url}/{self._sheet_name}!A1:append",
                        headers=headers,
                        params={"valueInputOption": "RAW"},
                        json={"values": [_HEADERS]},
                    )

                # Build the data row.
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                quality = (
                    str(math.floor(call.quality_score))
                    if call.quality_score is not None
                    else ""
                )
                row = [
                    ts,
                    call.phone,
                    call.name,
                    call.email,
                    call.disposition,
                    str(call.duration_seconds),
                    call.sentiment,
                    quality,
                    call.summary,
                    call.recording_url,
                    call.transcript_url,
                    call.external_id,
                ]

                append_url = f"{values_url}/{self._sheet_name}!A1:append"
                resp = await client.post(
                    append_url,
                    headers=headers,
                    params={"valueInputOption": "RAW"},
                    json={"values": [row]},
                )

        except Exception as exc:
            logger.warning(f"Google Sheets sync failed (network): {exc}")
            return CRMSyncResult(ok=False, detail=f"network_error: {exc}")

        if not resp.is_success:
            body = resp.text[:200]
            logger.warning(f"Google Sheets append failed: {resp.status_code} {body}")
            return CRMSyncResult(ok=False, detail=f"sheets_error_{resp.status_code}: {body}")

        updates = resp.json().get("updates", {})
        updated_range = updates.get("updatedRange", "?")
        logger.info(f"Google Sheets: appended row to {updated_range} for run {call.external_id}")
        return CRMSyncResult(ok=True, detail=f"row_appended:{updated_range}")
