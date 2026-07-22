"""Settings schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AconexSettingsUpdate(BaseModel):
    authorization_url: str | None = None
    token_url: str | None = None
    base_url: str | None = None
    api_audience: str | None = None
    client_id: str | None = None
    client_secret: str | None = None  # plaintext write-only
    redirect_uri: str | None = None
    authorization_state: str | None = None
    token_auth_method: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    refresh_token: str | None = None  # plaintext write-only
    authorization_code: str | None = None  # exchange only, not stored long-term
    default_mail_box: str | None = None
    page_size: int | None = Field(default=None, ge=25, le=500)

    @field_validator("token_auth_method")
    @classmethod
    def validate_auth_method(cls, v: str | None) -> str | None:
        if v is not None and v not in {"basic", "form"}:
            raise ValueError("token_auth_method must be 'basic' or 'form'")
        return v


class AconexSettingsPublic(BaseModel):
    authorization_url: str = ""
    token_url: str = ""
    base_url: str = "https://eu1.aconex.com"
    api_audience: str = "https://api.aconex.com"
    client_id: str = ""
    client_secret_masked: str | None = None
    redirect_uri: str = "http://localhost:8080/callback"
    authorization_state: str = "aconex-local-auth"
    token_auth_method: str = "basic"
    project_id: str = ""
    project_name: str = ""
    has_refresh_token: bool = False
    has_access_token: bool = False
    refresh_token_masked: str | None = None
    access_token_masked: str | None = None
    token_expires_at: datetime | None = None
    default_mail_box: str = "inbox"
    page_size: int = 250
    updated_at: datetime | None = None


class AuthUrlResponse(BaseModel):
    authorization_url: str


class ExchangeCodeRequest(BaseModel):
    code: str = Field(min_length=1)
    redirect_uri: str | None = None


class TokenExchangeResult(BaseModel):
    ok: bool
    message: str
    has_refresh_token: bool = False
    has_access_token: bool = False
    expires_in: int | None = None


class ProjectInfo(BaseModel):
    project_id: str
    project_name: str = ""


class ColumnMapping(BaseModel):
    field: str
    header: str
    order: int = 0


class GoogleSheetsSettingsUpdate(BaseModel):
    spreadsheet_id: str | None = None
    sheet_name: str | None = None
    service_account_json: str | None = None  # write-only plaintext JSON
    column_mapping: list[ColumnMapping] | None = None

    @field_validator("spreadsheet_id")
    @classmethod
    def extract_spreadsheet_id(cls, v: str | None) -> str | None:
        if not v:
            return v
        v = v.strip()
        # Accept full Google Sheets URL
        if "/spreadsheets/d/" in v:
            part = v.split("/spreadsheets/d/")[1]
            return part.split("/")[0].split("?")[0]
        return v


class GoogleSheetsSettingsPublic(BaseModel):
    spreadsheet_id: str = ""
    sheet_name: str = "Workflow Monitor"
    has_service_account: bool = False
    service_account_email_masked: str | None = None
    column_mapping: list[ColumnMapping] = Field(default_factory=list)
    updated_at: datetime | None = None
