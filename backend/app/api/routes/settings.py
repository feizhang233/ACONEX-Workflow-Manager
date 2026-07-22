"""ACONEX and Google Sheets settings routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import MessageResponse, TestConnectionResult
from app.schemas.settings import (
    AconexSettingsPublic,
    AconexSettingsUpdate,
    AuthUrlResponse,
    ExchangeCodeRequest,
    GoogleSheetsSettingsPublic,
    GoogleSheetsSettingsUpdate,
    ProjectInfo,
    TokenExchangeResult,
)
from app.services.aconex.auth import AconexAuthService, AuthError
from app.services.aconex.client import AconexApiError, AconexClient
from app.services import google_sheets_service as gsheets

router = APIRouter(tags=["settings"])


@router.get("/settings/aconex", response_model=AconexSettingsPublic)
def get_aconex_settings(db: Session = Depends(get_db)):
    auth = AconexAuthService(db)
    return AconexSettingsPublic(**auth.public_view())


@router.put("/settings/aconex", response_model=AconexSettingsPublic)
def put_aconex_settings(body: AconexSettingsUpdate, db: Session = Depends(get_db)):
    auth = AconexAuthService(db)
    data = body.model_dump(exclude_unset=True)
    # authorization_code is handled via exchange endpoint
    data.pop("authorization_code", None)
    auth.update_fields(data)
    return AconexSettingsPublic(**auth.public_view())


@router.get("/settings/aconex/auth-url", response_model=AuthUrlResponse)
def get_auth_url(redirect_uri: str | None = None, db: Session = Depends(get_db)):
    auth = AconexAuthService(db)
    try:
        url = auth.build_authorization_url(redirect_uri=redirect_uri)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthUrlResponse(authorization_url=url)


@router.post("/settings/aconex/exchange-code", response_model=TokenExchangeResult)
def exchange_code(body: ExchangeCodeRequest, db: Session = Depends(get_db)):
    auth = AconexAuthService(db)
    try:
        token = auth.exchange_authorization_code(body.code, redirect_uri=body.redirect_uri)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TokenExchangeResult(
        ok=True,
        message="Token exchanged and stored securely.",
        has_refresh_token=bool(token.refresh_token),
        has_access_token=bool(token.access_token),
        expires_in=token.expires_in,
    )


@router.post("/settings/aconex/refresh-token", response_model=TokenExchangeResult)
def refresh_token(db: Session = Depends(get_db)):
    auth = AconexAuthService(db)
    try:
        token = auth.refresh_access_token()
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TokenExchangeResult(
        ok=True,
        message="Access token refreshed.",
        has_refresh_token=bool(token.refresh_token or auth.refresh_token),
        has_access_token=bool(token.access_token),
        expires_in=token.expires_in,
    )


@router.post("/settings/aconex/test", response_model=TestConnectionResult)
def test_aconex(db: Session = Depends(get_db)):
    try:
        with AconexClient(db) as client:
            result = client.test_connection()
        return TestConnectionResult(**result)
    except (AuthError, AconexApiError) as exc:
        return TestConnectionResult(ok=False, message=str(exc), detail={})


@router.get("/settings/aconex/projects", response_model=list[ProjectInfo])
def list_projects(db: Session = Depends(get_db)):
    try:
        with AconexClient(db) as client:
            projects = client.list_projects()
        return [ProjectInfo(**p) for p in projects]
    except (AuthError, AconexApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/settings/google-sheets", response_model=GoogleSheetsSettingsPublic)
def get_gsheets(db: Session = Depends(get_db)):
    return GoogleSheetsSettingsPublic(**gsheets.public_settings(db))


@router.put("/settings/google-sheets", response_model=GoogleSheetsSettingsPublic)
def put_gsheets(body: GoogleSheetsSettingsUpdate, db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "column_mapping" in data and data["column_mapping"] is not None:
        data["column_mapping"] = [
            c if isinstance(c, dict) else c.model_dump() for c in body.column_mapping or []
        ]
    try:
        gsheets.update_settings(db, data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GoogleSheetsSettingsPublic(**gsheets.public_settings(db))


@router.post("/settings/google-sheets/test", response_model=TestConnectionResult)
def test_gsheets(db: Session = Depends(get_db)):
    result = gsheets.test_connection(db)
    return TestConnectionResult(**result)
