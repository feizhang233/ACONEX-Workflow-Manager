"""HTTP client for ACONEX API with token refresh and exponential backoff."""

from __future__ import annotations

import random
import time
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.aconex.auth import AconexAuthService, AuthError


class AconexApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AconexClient:
    WORKFLOW_ACCEPT = "application/vnd.aconex.workflow.v1+xml"
    MAIL_ACCEPT = "application/vnd.aconex.mail.v2+xml;charset=UTF-8"

    def __init__(
        self,
        db: Session,
        auth: AconexAuthService | None = None,
        *,
        http_client: httpx.Client | None = None,
    ):
        self.db = db
        self.auth = auth or AconexAuthService(db)
        self._client = http_client
        self._owns_client = http_client is None
        app_settings = get_settings()
        self.timeout = app_settings.aconex_request_timeout
        self.max_retries = app_settings.aconex_max_retries
        self.retry_base = app_settings.aconex_retry_base_seconds

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> AconexClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    @property
    def base_url(self) -> str:
        return (self.auth.row.base_url or "https://eu1.aconex.com").rstrip("/")

    @property
    def project_id(self) -> str:
        return self.auth.row.project_id or ""

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> httpx.Response:
        return self.request("GET", path, params=params, accept=accept)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        data: Any | None = None,
        accept: str | None = None,
        content_type: str | None = None,
        retry_on_invalid_token: bool = True,
    ) -> httpx.Response:
        url = self._url(path)
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            headers = {
                "Authorization": f"Bearer {self.auth.get_access_token()}",
                "Accept": accept or "*/*",
            }
            if content_type:
                headers["Content-Type"] = content_type
            try:
                response = self.client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    data=data,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise AconexApiError(f"Request failed: {exc}") from exc
                self._sleep_backoff(attempt)
                continue

            if retry_on_invalid_token and self._looks_invalid_token(response):
                if self.auth.refresh_after_invalid_token():
                    return self.request(
                        method,
                        path,
                        params=params,
                        json_body=json_body,
                        data=data,
                        accept=accept,
                        content_type=content_type,
                        retry_on_invalid_token=False,
                    )
                raise AconexApiError(
                    "Access token rejected and refresh failed.",
                    status_code=response.status_code,
                    body=response.text[:500],
                )

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt >= self.max_retries:
                    raise AconexApiError(
                        f"HTTP {response.status_code} after retries: {response.text[:300]}",
                        status_code=response.status_code,
                        body=response.text[:500],
                    )
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(int(retry_after), 60))
                else:
                    self._sleep_backoff(attempt)
                continue

            if response.status_code >= 400:
                raise AconexApiError(
                    f"HTTP {response.status_code}: {response.text[:300]}",
                    status_code=response.status_code,
                    body=response.text[:500],
                )
            return response

        raise AconexApiError(f"Request failed: {last_error}")

    def list_projects(self) -> list[dict[str, str]]:
        """Best-effort project list; falls back to configured project."""
        candidates = [
            "/api/projects",
            "/api/user/projects",
        ]
        for path in candidates:
            try:
                response = self.get(path, accept="application/json, application/xml, */*")
            except AconexApiError:
                continue
            projects = self._parse_projects(response)
            if projects:
                return projects
        if self.project_id:
            return [
                {
                    "project_id": self.project_id,
                    "project_name": self.auth.row.project_name or self.project_id,
                }
            ]
        return []

    def test_connection(self) -> dict[str, Any]:
        token = self.auth.get_access_token()
        detail: dict[str, Any] = {
            "base_url": self.base_url,
            "project_id": self.project_id,
            "token_present": bool(token),
        }
        if not self.project_id:
            return {"ok": True, "message": "Token obtained; project ID not set yet.", "detail": detail}
        # Lightweight probe: first page of current workflows
        try:
            self.get(
                f"/api/projects/{self.project_id}/workflows/current",
                params={"page_size": "25", "page_number": "1"},
                accept=self.WORKFLOW_ACCEPT,
            )
            detail["probe"] = "workflows/current"
            return {"ok": True, "message": "ACONEX connection successful.", "detail": detail}
        except AconexApiError as exc:
            # Token might still be valid; endpoint may vary by tenant
            if exc.status_code in {401, 403}:
                return {"ok": False, "message": str(exc), "detail": detail}
            try:
                self.get(
                    f"/api/projects/{self.project_id}/workflows",
                    params={"page_size": "25", "page_number": "1"},
                    accept=self.WORKFLOW_ACCEPT,
                )
                detail["probe"] = "workflows"
                return {"ok": True, "message": "ACONEX connection successful.", "detail": detail}
            except AconexApiError as exc2:
                return {"ok": False, "message": str(exc2), "detail": detail}

    def fetch_workflow_page(
        self,
        *,
        page_number: int = 1,
        page_size: int | None = None,
        status: str | None = None,
        workflow_numbers: list[str] | None = None,
    ) -> httpx.Response:
        page_size = page_size or self.auth.row.page_size or 250
        page_size = max(25, page_size)
        if page_size % 25:
            page_size += 25 - (page_size % 25)
        if not self.project_id:
            raise AconexApiError("Project ID is not configured.")
        if workflow_numbers:
            return self.get(
                f"/api/projects/{self.project_id}/workflows/search",
                params={
                    "workflow_number": ",".join(workflow_numbers),
                    "page_size": str(page_size),
                    "page_number": str(page_number),
                },
                accept=self.WORKFLOW_ACCEPT,
            )
        path = f"/api/projects/{self.project_id}/workflows"
        if status:
            path = f"{path}/{status}"
        return self.get(
            path,
            params={"page_size": str(page_size), "page_number": str(page_number)},
            accept=self.WORKFLOW_ACCEPT,
        )

    def fetch_mail_page(
        self,
        *,
        page_number: int = 1,
        page_size: int | None = None,
        search_query: str | None = None,
        mail_box: str | None = None,
    ) -> httpx.Response:
        if not self.project_id:
            raise AconexApiError("Project ID is not configured.")
        page_size = page_size or self.auth.row.page_size or 250
        mail_box = mail_box or self.auth.row.default_mail_box or "inbox"
        fields = ",".join(
            [
                "allAttachmentCount",
                "closedoutdetails",
                "confidential",
                "corrtypeid",
                "docno",
                "fromUserDetails",
                "hasAttachments",
                "inreftomailno",
                "mailRecipients",
                "reasonforissueid",
                "secondaryattribute",
                "sentdate",
                "subject",
                "tostatusid",
            ]
        )
        params: dict[str, Any] = {
            "mail_box": mail_box,
            "return_fields": fields,
            "search_type": "PAGED",
            "page_size": str(page_size),
            "page_number": str(page_number),
        }
        if search_query:
            params["search_query"] = search_query
        return self.get(
            f"/api/projects/{self.project_id}/mail",
            params=params,
            accept=self.MAIL_ACCEPT,
        )

    def fetch_mail_detail(self, mail_id: str) -> httpx.Response:
        if not self.project_id:
            raise AconexApiError("Project ID is not configured.")
        return self.get(
            f"/api/projects/{self.project_id}/mail/{mail_id}",
            accept=self.MAIL_ACCEPT,
        )

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    def _sleep_backoff(self, attempt: int) -> None:
        delay = self.retry_base * (2**attempt) + random.uniform(0, 0.5)
        time.sleep(min(delay, 30.0))

    @staticmethod
    def _looks_invalid_token(response: httpx.Response) -> bool:
        if response.status_code not in {401, 403}:
            return False
        text = response.text[:1000].upper()
        auth_header = response.headers.get("www-authenticate", "").upper()
        return (
            "INVALID_TOKEN" in text
            or "INVALID_TOKEN" in auth_header
            or "EXPIRED" in text
            or "UNAUTHORIZED" in text
        )

    @staticmethod
    def _parse_projects(response: httpx.Response) -> list[dict[str, str]]:
        content_type = response.headers.get("content-type", "")
        projects: list[dict[str, str]] = []
        if "json" in content_type:
            try:
                payload = response.json()
            except Exception:
                return []
            items = payload if isinstance(payload, list) else payload.get("projects") or payload.get("Project") or []
            if isinstance(items, dict):
                items = [items]
            for item in items:
                if not isinstance(item, dict):
                    continue
                pid = str(item.get("projectId") or item.get("ProjectId") or item.get("id") or "")
                name = str(item.get("projectName") or item.get("ProjectName") or item.get("name") or pid)
                if pid:
                    projects.append({"project_id": pid, "project_name": name})
            return projects
        # XML fallback
        from app.services.aconex.xml_utils import attr, descendants, parse_xml_bytes, text_of

        root = parse_xml_bytes(response.content)
        if root is None:
            return []
        for node in descendants(root, "Project"):
            pid = attr(node, "ProjectId", "projectId") or text_of(node, "ProjectId")
            name = text_of(node, "ProjectName") or text_of(node, "Name") or pid
            if pid:
                projects.append({"project_id": pid, "project_name": name})
        return projects
