from __future__ import annotations

import json
import logging
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
import urllib.request

from pydantic import BaseModel

from parquet_gateway.auth import Principal, issue_gateway_token
from parquet_gateway.config import FeishuUserConfig, GatewayConfig
from parquet_gateway.errors import AuthError, PermissionDenied


FEISHU_AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
LOGGER = logging.getLogger(__name__)


class FeishuExchangeRequest(BaseModel):
    code: str
    redirect_uri: str


class FeishuOAuthClientProtocol(Protocol):
    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        ...

    def get_user_info(self, access_token: str) -> dict:
        ...


class FeishuOAuthClient:
    def __init__(self, config: GatewayConfig):
        self.config = config

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        # The concrete Feishu HTTP exchange is intentionally isolated here so
        # tests can inject a fake client and secrets never move into OpenCLI.
        if self.config.auth is None:
            raise AuthError("feishu auth is not configured")
        feishu = self.config.auth.feishu
        payload = json.dumps({
            "grant_type": "authorization_code",
            "client_id": feishu.app_id,
            "client_secret": feishu.app_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/authen/v2/oauth/token",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise AuthError(f"feishu token exchange failed: HTTP {exc.code}") from exc
        except URLError as exc:
            raise AuthError(f"feishu token exchange failed: {exc.reason}") from exc
        if raw.get("code", 0) != 0:
            raise AuthError(f"feishu token exchange failed: {raw.get('msg', 'unknown error')}")
        data = raw.get("data", {})
        LOGGER.info(
            "feishu token exchange response keys: top=%s data=%s",
            sorted(raw.keys()),
            sorted(data.keys()) if isinstance(data, dict) else type(data).__name__,
        )
        return {
            "access_token": (
                data.get("user_access_token")
                or data.get("access_token")
                or data.get("token")
                or raw.get("user_access_token")
                or raw.get("access_token")
            ),
        }

    def get_user_info(self, access_token: str) -> dict:
        if not access_token:
            raise AuthError("feishu token exchange did not return an access_token")
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/authen/v1/user_info",
            method="GET",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise AuthError(f"feishu user info failed: HTTP {exc.code}") from exc
        except URLError as exc:
            raise AuthError(f"feishu user info failed: {exc.reason}") from exc
        if raw.get("code", 0) != 0:
            raise AuthError(f"feishu user info failed: {raw.get('msg', 'unknown error')}")
        data = raw.get("data", {})
        return {
            "open_id": data.get("open_id"),
            "email": data.get("email"),
            "name": data.get("name"),
        }


def build_feishu_authorize_url(config: GatewayConfig, redirect_uri: str | None = None) -> dict[str, str]:
    if config.auth is None or not config.auth.feishu.enabled:
        raise AuthError("feishu auth is not enabled")
    feishu = config.auth.feishu
    if not feishu.app_id:
        raise AuthError("feishu app_id is not configured")
    actual_redirect_uri = redirect_uri or feishu.redirect_uri
    if actual_redirect_uri != feishu.redirect_uri:
        raise AuthError("redirect_uri does not match configured feishu redirect_uri")
    query = urlencode({
        "client_id": feishu.app_id,
        "response_type": "code",
        "redirect_uri": actual_redirect_uri,
    })
    return {
        "auth_url": f"{FEISHU_AUTHORIZE_URL}?{query}",
        "redirect_uri": actual_redirect_uri,
    }


def exchange_feishu_code_for_gateway_token(
    config: GatewayConfig,
    client: FeishuOAuthClientProtocol,
    request: FeishuExchangeRequest,
) -> dict:
    if config.auth is None or not config.auth.feishu.enabled:
        raise AuthError("feishu auth is not enabled")
    if request.redirect_uri != config.auth.feishu.redirect_uri:
        raise AuthError("redirect_uri does not match configured feishu redirect_uri")

    token_payload = client.exchange_code(request.code, request.redirect_uri)
    profile = client.get_user_info(str(token_payload.get("access_token") or ""))
    user = resolve_feishu_user(config.auth.feishu_users, profile)
    principal = Principal.from_feishu_config(user)
    token, ttl = issue_gateway_token(config, principal)
    name = profile.get("name")
    open_id = profile.get("open_id")
    email = profile.get("email")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ttl,
        "user": {
            "id": principal.id,
            "roles": sorted(principal.roles),
            "open_id": open_id,
            "email": email,
            "name": name,
        },
    }


def resolve_feishu_user(users: list[FeishuUserConfig], profile: dict) -> FeishuUserConfig:
    open_id = profile.get("open_id")
    name = profile.get("name")
    for user in users:
        if user.open_id and user.open_id == open_id:
            return user
        if user.name and user.name == name:
            return user
    raise PermissionDenied(
        "feishu user is not mapped to gateway permissions",
        details={
            "open_id": open_id,
            "email": profile.get("email"),
            "name": name,
        },
    )
