"""ACONEX OAuth2 authorization code + refresh token flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.models.entities import AconexSettings, utc_now
from app.services.encryption import decrypt_value, encrypt_value, mask_secret


class AuthError(RuntimeError):
    pass


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_in: int | None = None
    scope: str = ""


class AconexAuthService:
    def __init__(self, db: Session, settings_row: AconexSettings | None = None):
        self.db = db
        self.row = settings_row or self._load_or_create()
        self._memory_token: TokenSet | None = None

    def _load_or_create(self) -> AconexSettings:
        row = self.db.query(AconexSettings).filter(AconexSettings.id == 1).first()
        if row is None:
            row = AconexSettings(id=1)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def reload(self) -> AconexSettings:
        self.db.refresh(self.row)
        return self.row

    @property
    def client_secret(self) -> str:
        return decrypt_value(self.row.client_secret_enc) or ""

    @property
    def access_token(self) -> str:
        if self._memory_token and self._memory_token.access_token:
            return self._memory_token.access_token
        return decrypt_value(self.row.access_token_enc) or ""

    @property
    def refresh_token(self) -> str:
        if self._memory_token and self._memory_token.refresh_token:
            return self._memory_token.refresh_token
        return decrypt_value(self.row.refresh_token_enc) or ""

    def public_view(self) -> dict[str, Any]:
        secret = self.client_secret
        refresh = self.refresh_token
        access = self.access_token
        return {
            "authorization_url": self.row.authorization_url or "",
            "token_url": self.row.token_url or "",
            "base_url": self.row.base_url or "https://eu1.aconex.com",
            "api_audience": self.row.api_audience or "https://api.aconex.com",
            "client_id": self.row.client_id or "",
            "client_secret_masked": mask_secret(secret) if secret else None,
            "redirect_uri": self.row.redirect_uri or "http://localhost:8080/callback",
            "authorization_state": self.row.authorization_state or "aconex-local-auth",
            "token_auth_method": self.row.token_auth_method or "basic",
            "project_id": self.row.project_id or "",
            "project_name": self.row.project_name or "",
            "has_refresh_token": bool(refresh),
            "has_access_token": bool(access),
            "refresh_token_masked": mask_secret(refresh) if refresh else None,
            "access_token_masked": mask_secret(access) if access else None,
            "token_expires_at": self.row.token_expires_at,
            "default_mail_box": self.row.default_mail_box or "inbox",
            "page_size": self.row.page_size or 250,
            "updated_at": self.row.updated_at,
        }

    def update_fields(self, data: dict[str, Any]) -> AconexSettings:
        mapping = {
            "authorization_url": "authorization_url",
            "token_url": "token_url",
            "base_url": "base_url",
            "api_audience": "api_audience",
            "client_id": "client_id",
            "redirect_uri": "redirect_uri",
            "authorization_state": "authorization_state",
            "token_auth_method": "token_auth_method",
            "project_id": "project_id",
            "project_name": "project_name",
            "default_mail_box": "default_mail_box",
            "page_size": "page_size",
        }
        for src, dest in mapping.items():
            if src in data and data[src] is not None:
                value = data[src]
                if src == "base_url" and isinstance(value, str):
                    value = value.rstrip("/")
                setattr(self.row, dest, value)
        if data.get("client_secret"):
            self.row.client_secret_enc = encrypt_value(data["client_secret"])
        if data.get("refresh_token"):
            self.row.refresh_token_enc = encrypt_value(data["refresh_token"])
            self._memory_token = None
        self.row.updated_at = utc_now()
        self.db.add(self.row)
        self.db.commit()
        self.db.refresh(self.row)
        return self.row

    def build_authorization_url(self, *, redirect_uri: str | None = None, state: str | None = None) -> str:
        if not self.row.authorization_url:
            raise AuthError("Authorization URL is empty.")
        if not self.row.client_id:
            raise AuthError("Client ID is empty.")
        redirect_uri = redirect_uri or self.row.redirect_uri
        state = self.row.authorization_state if state is None else state
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.row.client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "resource": "ACONEX",
            }
        )
        base = self.row.authorization_url
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}{query}"

    def exchange_authorization_code(self, code: str, *, redirect_uri: str | None = None) -> TokenSet:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or self.row.redirect_uri,
            "audience": self.row.api_audience or "https://api.aconex.com",
        }
        token = self._request_token(data)
        self._persist_token(token)
        return token

    def refresh_access_token(self, refresh_token: str | None = None) -> TokenSet:
        refresh_token = refresh_token or self.refresh_token
        if not refresh_token:
            raise AuthError("No refresh token available.")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "audience": self.row.api_audience or "https://api.aconex.com",
        }
        token = self._request_token(data)
        # Preserve refresh token if server does not rotate it
        if not token.refresh_token:
            token.refresh_token = refresh_token
        self._persist_token(token)
        return token

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        if force_refresh and self.refresh_token:
            return self.refresh_access_token().access_token
        if self._memory_token and self._memory_token.access_token:
            if self.row.token_expires_at:
                expires = self.row.token_expires_at
                if expires.tzinfo is None:
                    # stored as naive UTC
                    if expires > datetime.utcnow() + timedelta(seconds=60):
                        return self._memory_token.access_token
                elif expires > datetime.now(timezone.utc) + timedelta(seconds=60):
                    return self._memory_token.access_token
            else:
                return self._memory_token.access_token
        if self.row.token_expires_at and self.access_token:
            expires = self.row.token_expires_at
            still_valid = expires > datetime.utcnow() + timedelta(seconds=60)
            if still_valid:
                return self.access_token
        if self.refresh_token:
            return self.refresh_access_token().access_token
        if self.access_token:
            return self.access_token
        raise AuthError(
            "No token source configured. Set refresh token or exchange an authorization code."
        )

    def refresh_after_invalid_token(self) -> bool:
        if not self.refresh_token:
            return False
        try:
            self.refresh_access_token()
            return True
        except AuthError:
            return False

    def _persist_token(self, token: TokenSet) -> None:
        self._memory_token = token
        self.row.access_token_enc = encrypt_value(token.access_token)
        if token.refresh_token:
            self.row.refresh_token_enc = encrypt_value(token.refresh_token)
        if token.expires_in:
            self.row.token_expires_at = datetime.utcnow() + timedelta(seconds=int(token.expires_in))
        self.row.updated_at = utc_now()
        self.db.add(self.row)
        self.db.commit()
        self.db.refresh(self.row)

    def _request_token(self, data: dict[str, str]) -> TokenSet:
        if not self.row.token_url:
            raise AuthError("Token URL is empty.")
        if not self.row.client_id:
            raise AuthError("Client ID is empty.")
        secret = self.client_secret
        if not secret:
            raise AuthError("Client secret is empty.")
        method = (self.row.token_auth_method or "basic").lower()
        try:
            with httpx.Client(timeout=60.0) as client:
                if method == "form":
                    form_data = {
                        **data,
                        "client_id": self.row.client_id,
                        "client_secret": secret,
                    }
                    response = client.post(self.row.token_url, data=form_data)
                else:
                    response = client.post(
                        self.row.token_url,
                        data=data,
                        auth=(self.row.client_id, secret),
                    )
        except httpx.HTTPError as exc:
            raise AuthError(f"Token request failed: {exc}") from exc
        if response.status_code >= 400:
            preview = response.text[:300].replace("\n", " ")
            raise AuthError(f"Token request failed: HTTP {response.status_code} {preview}")
        payload = response.json()
        access_token = payload.get("access_token", "")
        if not access_token:
            raise AuthError("Token response did not contain access_token.")
        return TokenSet(
            access_token=access_token,
            refresh_token=payload.get("refresh_token", ""),
            token_type=payload.get("token_type", "Bearer"),
            expires_in=payload.get("expires_in"),
            scope=payload.get("scope", ""),
        )
