from __future__ import annotations

import os
import secrets
import time
from functools import lru_cache
from html import escape
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from pydantic import ValidationError

from parquet_gateway.admin_config import discover_parquet_datasets, read_admin_config, save_admin_config_yaml
from parquet_gateway.admin_ui import ADMIN_CONFIG_UI_HTML
from parquet_gateway.audit import AuditEvent, AuditLog
from parquet_gateway.auth import Principal, TokenAuthenticator
from parquet_gateway.config import GatewayConfig, load_config
from parquet_gateway.errors import GatewayError, NotFound
from parquet_gateway.errors import PermissionDenied
from parquet_gateway.executor import DuckDBExecutor
from parquet_gateway.feishu import (
    FeishuExchangeRequest,
    FeishuOAuthClient,
    build_feishu_authorize_url,
    exchange_feishu_code_for_gateway_token,
)
from parquet_gateway.models import QueryRequest, QueryResponse
from parquet_gateway.policy import list_visible_datasets, resolve_dataset_access
from parquet_gateway.query_builder import compile_query


class AdminConfigSaveRequest(BaseModel):
    yaml: str


CLIENT_PACKAGE_NAME = "parquet-query-gateway-client.zip"
CLIENT_GUIDE_NAME = "client-installation-guide.md"
CLIENT_VERSION = "0.1.4"
CLIENT_DOWNLOAD_URL = f"/downloads/{CLIENT_PACKAGE_NAME}"
CLIENT_GUIDE_URL = f"/{CLIENT_GUIDE_NAME}"
LOGIN_SESSION_TTL_SECONDS = 600


def create_app(feishu_client=None) -> FastAPI:
    config = get_config()
    authenticator = TokenAuthenticator(config)
    audit = AuditLog(os.environ.get("PARQUET_GATEWAY_AUDIT_DB", "audit.sqlite3"))
    executor = DuckDBExecutor(config)
    actual_feishu_client = feishu_client or FeishuOAuthClient(config)
    login_sessions: dict[str, dict[str, object]] = {}

    app = FastAPI(title="Parquet Query Gateway", version="0.1.0")

    @app.middleware("http")
    async def client_version_middleware(request: Request, call_next) -> Response:
        response = await call_next(request)
        client_version = request.headers.get("x-parquet-client-version")
        if not client_version or client_version != CLIENT_VERSION:
            response.headers["X-Parquet-Client-Version-Status"] = "outdated"
            response.headers["X-Parquet-Client-Latest-Version"] = CLIENT_VERSION
            response.headers["X-Parquet-Client-Download-Url"] = CLIENT_DOWNLOAD_URL
            response.headers["X-Parquet-Client-Guide-Url"] = CLIENT_GUIDE_URL
        return response

    def current_principal(authorization: str | None = Header(default=None)) -> Principal:
        return authenticator.authenticate_header(authorization)

    def current_admin(principal: Principal = Depends(current_principal)) -> Principal:
        if "admin" not in principal.roles:
            raise PermissionDenied("admin role is required")
        return principal

    @app.exception_handler(GatewayError)
    async def gateway_error_handler(_, exc: GatewayError) -> JSONResponse:
        error: dict[str, object] = {"code": exc.code, "message": exc.message}
        if exc.details is not None:
            error["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content={"error": error})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(_, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": {"code": "validation_error", "message": str(exc)}})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/client/version")
    def client_version() -> dict[str, str]:
        return {
            "client_version": CLIENT_VERSION,
            "latest_version": CLIENT_VERSION,
            "download_url": CLIENT_DOWNLOAD_URL,
            "guide_url": CLIENT_GUIDE_URL,
        }

    @app.get(f"/downloads/{CLIENT_PACKAGE_NAME}")
    @app.head(f"/downloads/{CLIENT_PACKAGE_NAME}")
    def download_client_package() -> FileResponse:
        package_path = Path(os.environ.get(
            "PARQUET_GATEWAY_CLIENT_PACKAGE",
            str(Path.cwd() / "downloads" / CLIENT_PACKAGE_NAME),
        ))
        if not package_path.is_file():
            raise NotFound("client package is not available")
        return FileResponse(
            package_path,
            media_type="application/zip",
            filename=CLIENT_PACKAGE_NAME,
        )

    @app.get(f"/{CLIENT_GUIDE_NAME}")
    @app.head(f"/{CLIENT_GUIDE_NAME}")
    def client_installation_guide() -> FileResponse:
        guide_path = Path(os.environ.get(
            "PARQUET_GATEWAY_CLIENT_GUIDE",
            str(Path.cwd() / "docs" / CLIENT_GUIDE_NAME),
        ))
        if not guide_path.is_file():
            raise NotFound("client installation guide is not available")
        return FileResponse(
            guide_path,
            media_type="text/plain; charset=utf-8",
        )

    @app.get("/datasets")
    def datasets(principal: Principal = Depends(current_principal)) -> dict[str, object]:
        return {"datasets": list_visible_datasets(config, principal)}

    @app.get("/datasets/{dataset_id}/schema")
    def schema(dataset_id: str, principal: Principal = Depends(current_principal)) -> dict[str, object]:
        access = resolve_dataset_access(config, principal, dataset_id)
        return {
            "dataset": dataset_id,
            "description": access.dataset.description,
            "columns": sorted(access.allowed_columns),
        }

    @app.post("/query", response_model=QueryResponse)
    def query(request: QueryRequest, principal: Principal = Depends(current_principal)) -> QueryResponse:
        start = time.perf_counter()
        try:
            compiled = compile_query(config, principal, request)
            response = executor.execute(compiled)
            audit.record(AuditEvent(
                user_id=principal.id,
                dataset=request.dataset,
                action="query",
                allowed=True,
                details={
                    "columns": response.columns,
                    "filters": [filter_.model_dump() for filter_ in request.filters],
                },
                row_count=response.row_count,
                duration_ms=response.query_ms,
            ))
            return response
        except GatewayError as exc:
            audit.record(AuditEvent(
                user_id=principal.id,
                dataset=request.dataset,
                action="query",
                allowed=False,
                reason=exc.message,
                duration_ms=int((time.perf_counter() - start) * 1000),
            ))
            raise

    @app.get("/admin/audit")
    def audit_events(
        principal: Principal = Depends(current_admin),
        limit: int = 100,
    ) -> dict[str, object]:
        bounded_limit = min(max(limit, 1), 1000)
        return {"events": audit.recent(bounded_limit)}

    @app.get("/admin/config")
    def admin_config(_: Principal = Depends(current_admin)) -> dict[str, object]:
        return read_admin_config(config_path())

    @app.get("/admin/config/discover-datasets")
    def admin_discover_datasets(_: Principal = Depends(current_admin)) -> dict[str, object]:
        return discover_parquet_datasets(config)

    @app.get("/admin/config-ui", response_class=HTMLResponse)
    def admin_config_ui() -> str:
        return ADMIN_CONFIG_UI_HTML

    def save_admin_config_impl(
        request: AdminConfigSaveRequest,
        _: Principal = Depends(current_admin),
    ) -> dict[str, object]:
        result = save_admin_config_yaml(config_path(), request.yaml)
        reset_config_cache()
        return result

    app.put("/admin/config")(save_admin_config_impl)
    app.post("/admin/config")(save_admin_config_impl)

    @app.post("/admin/config/reload")
    def reload_admin_config(_: Principal = Depends(current_admin)) -> dict[str, object]:
        reset_config_cache()
        return {"reloaded": True}

    @app.post("/auth/feishu/exchange")
    def feishu_exchange(request: FeishuExchangeRequest) -> dict[str, object]:
        return exchange_feishu_code_for_gateway_token(config, actual_feishu_client, request)

    @app.get("/auth/feishu/authorize-url")
    def feishu_authorize_url(redirect_uri: str | None = None) -> dict[str, str]:
        return build_feishu_authorize_url(config, redirect_uri)

    def purge_login_sessions() -> None:
        now = time.time()
        expired = [
            session_id
            for session_id, session in login_sessions.items()
            if float(session["expires_at"]) <= now
        ]
        for session_id in expired:
            login_sessions.pop(session_id, None)

    @app.post("/auth/feishu/login-session")
    def create_feishu_login_session() -> dict[str, object]:
        purge_login_sessions()
        session_id = secrets.token_urlsafe(24)
        expires_at = time.time() + LOGIN_SESSION_TTL_SECONDS
        login_sessions[session_id] = {
            "status": "pending",
            "expires_at": expires_at,
        }
        authorize = build_feishu_authorize_url(config, state=session_id)
        return {
            "session_id": session_id,
            "auth_url": authorize["auth_url"],
            "redirect_uri": authorize["redirect_uri"],
            "expires_in": LOGIN_SESSION_TTL_SECONDS,
        }

    @app.get("/auth/feishu/login-session/{session_id}")
    def get_feishu_login_session(session_id: str) -> dict[str, object]:
        purge_login_sessions()
        session = login_sessions.get(session_id)
        if session is None:
            raise NotFound("login session is not available")
        status = session["status"]
        if status == "complete":
            payload = dict(session["payload"])  # type: ignore[arg-type]
            login_sessions.pop(session_id, None)
            payload["status"] = "complete"
            return payload
        if status == "error":
            message = str(session.get("message") or "Feishu login failed")
            details = session.get("details")
            login_sessions.pop(session_id, None)
            response: dict[str, object] = {"status": "error", "message": message}
            if details is not None:
                response["details"] = details
            return response
        return {
            "status": "pending",
            "expires_in": max(0, int(float(session["expires_at"]) - time.time())),
        }

    @app.get("/auth/feishu/callback", response_class=HTMLResponse)
    def feishu_login_callback(
        state: str | None = None,
        code: str | None = None,
        error: str | None = None,
    ) -> HTMLResponse:
        purge_login_sessions()
        if not state or state not in login_sessions:
            return HTMLResponse(
                "<html><body>Parquet Gateway login session is missing or expired.</body></html>",
                status_code=400,
            )
        session = login_sessions[state]
        if error:
            session["status"] = "error"
            session["message"] = error
            return HTMLResponse(
                f"<html><body>Parquet Gateway login failed: {escape(error)}</body></html>",
                status_code=400,
            )
        if not code:
            session["status"] = "error"
            session["message"] = "Feishu callback did not include code"
            return HTMLResponse(
                "<html><body>Parquet Gateway login failed: callback did not include code.</body></html>",
                status_code=400,
            )
        try:
            payload = exchange_feishu_code_for_gateway_token(
                config,
                actual_feishu_client,
                FeishuExchangeRequest(code=code, redirect_uri=config.auth.feishu.redirect_uri),  # type: ignore[union-attr]
            )
        except GatewayError as exc:
            session["status"] = "error"
            session["message"] = exc.message
            if exc.details is not None:
                session["details"] = exc.details
            details_html = ""
            if exc.details:
                detail_items = "".join(
                    f"<li>{escape(str(key))}: {escape(str(value))}</li>"
                    for key, value in exc.details.items()
                    if value is not None
                )
                details_html = f"<p>Details:</p><ul>{detail_items}</ul>"
            return HTMLResponse(
                f"<html><body>Parquet Gateway login failed: {escape(exc.message)}{details_html}</body></html>",
                status_code=exc.status_code,
            )
        session["status"] = "complete"
        session["payload"] = payload
        return HTMLResponse("<html><body>Parquet Gateway login complete. You can close this window.</body></html>")

    app.state.config = config
    app.state.audit = audit
    return app


@lru_cache(maxsize=1)
def get_config() -> GatewayConfig:
    return load_config(config_path())


def config_path() -> Path:
    return Path(os.environ.get("PARQUET_GATEWAY_CONFIG", "config/example.yml"))


def reset_config_cache() -> None:
    get_config.cache_clear()
