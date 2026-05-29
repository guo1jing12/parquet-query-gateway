from __future__ import annotations

import yaml
from fastapi.testclient import TestClient
from urllib.error import HTTPError
from unittest.mock import patch

from parquet_gateway.app import create_app, reset_config_cache
from parquet_gateway.auth import TokenAuthenticator
from parquet_gateway.config import load_config
from parquet_gateway.errors import AuthError, PermissionDenied
from parquet_gateway.feishu import FeishuExchangeRequest, FeishuOAuthClient, exchange_feishu_code_for_gateway_token


class FakeFeishuOAuthClient:
    def __init__(self, expected_redirect_uri: str = "http://127.0.0.1:8765/callback"):
        self.user_info_requested = False
        self.expected_redirect_uri = expected_redirect_uri

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        assert code == "auth-code"
        assert redirect_uri == self.expected_redirect_uri
        return {
            "access_token": "feishu-user-access-token",
        }

    def get_user_info(self, access_token: str) -> dict:
        assert access_token == "feishu-user-access-token"
        self.user_info_requested = True
        return {
            "open_id": "ou_alice",
            "email": "alice@example.com",
            "name": "Alice Zhang",
        }


def write_feishu_config(base_config_path, target_path, redirect_uri: str = "http://127.0.0.1:8765/callback"):
    raw = yaml.safe_load(base_config_path.read_text(encoding="utf-8"))
    raw["auth"] = {
        "gateway_token_secret": "unit-test-secret",
        "token_ttl_seconds": 3600,
        "feishu": {
            "enabled": True,
            "app_id": "cli_a_test",
            "app_secret": "secret",
            "redirect_uri": redirect_uri,
        },
        "feishu_users": [
            {
                "name": "Alice Zhang",
                "id": "alice",
                "roles": ["analyst"],
                "attributes": {"regions": ["US"]},
            }
        ],
    }
    target_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return target_path


def test_loads_feishu_auth_config(sample_gateway_config, tmp_path):
    config = load_config(write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml"))

    assert config.auth is not None
    assert config.auth.feishu.enabled is True
    assert config.auth.feishu_users[0].name == "Alice Zhang"


def test_exchanges_feishu_code_for_gateway_token(monkeypatch, sample_gateway_config, tmp_path):
    config_path = write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml")
    monkeypatch.setenv("PARQUET_GATEWAY_CONFIG", str(config_path))
    monkeypatch.setenv("PARQUET_GATEWAY_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    reset_config_cache()
    feishu_client = FakeFeishuOAuthClient()
    app = create_app(feishu_client=feishu_client)
    client = TestClient(app)

    response = client.post(
        "/auth/feishu/exchange",
        json={"code": "auth-code", "redirect_uri": "http://127.0.0.1:8765/callback"},
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 3600
    assert payload["user"]["name"] == "Alice Zhang"
    assert payload["user"]["open_id"] == "ou_alice"
    assert "email" not in payload["user"]
    assert feishu_client.user_info_requested is True
    principal = TokenAuthenticator(load_config(config_path)).authenticate_header(f"Bearer {payload['access_token']}")
    assert principal.id == "alice"
    assert principal.attributes["regions"] == ["US"]


def test_gateway_hosted_feishu_login_session_completes(monkeypatch, sample_gateway_config, tmp_path):
    redirect_uri = "http://testserver/auth/feishu/callback"
    config_path = write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml", redirect_uri=redirect_uri)
    monkeypatch.setenv("PARQUET_GATEWAY_CONFIG", str(config_path))
    monkeypatch.setenv("PARQUET_GATEWAY_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    reset_config_cache()
    feishu_client = FakeFeishuOAuthClient(expected_redirect_uri=redirect_uri)
    app = create_app(feishu_client=feishu_client)
    client = TestClient(app)

    session_response = client.post("/auth/feishu/login-session")

    assert session_response.status_code == 200, session_response.json()
    session_payload = session_response.json()
    session_id = session_payload["session_id"]
    assert session_payload["redirect_uri"] == redirect_uri
    assert "state=" in session_payload["auth_url"]
    assert "redirect_uri=http%3A%2F%2Ftestserver%2Fauth%2Ffeishu%2Fcallback" in session_payload["auth_url"]

    pending_response = client.get(f"/auth/feishu/login-session/{session_id}")
    assert pending_response.status_code == 200
    assert pending_response.json()["status"] == "pending"

    callback_response = client.get(f"/auth/feishu/callback?state={session_id}&code=auth-code")
    assert callback_response.status_code == 200
    assert "login complete" in callback_response.text

    complete_response = client.get(f"/auth/feishu/login-session/{session_id}")
    assert complete_response.status_code == 200, complete_response.json()
    complete_payload = complete_response.json()
    assert complete_payload["status"] == "complete"
    assert complete_payload["token_type"] == "bearer"
    assert complete_payload["expires_in"] == 3600
    assert complete_payload["user"]["name"] == "Alice Zhang"
    assert complete_payload["user"]["open_id"] == "ou_alice"
    assert "email" not in complete_payload["user"]
    assert feishu_client.user_info_requested is True

    principal = TokenAuthenticator(load_config(config_path)).authenticate_header(
        f"Bearer {complete_payload['access_token']}"
    )
    assert principal.id == "alice"


def test_gateway_hosted_feishu_login_session_returns_unmapped_user_details(
    monkeypatch,
    sample_gateway_config,
    tmp_path,
):
    redirect_uri = "http://testserver/auth/feishu/callback"
    config_path = write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml", redirect_uri=redirect_uri)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["auth"]["feishu_users"] = []
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    monkeypatch.setenv("PARQUET_GATEWAY_CONFIG", str(config_path))
    monkeypatch.setenv("PARQUET_GATEWAY_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    reset_config_cache()
    app = create_app(feishu_client=FakeFeishuOAuthClient(expected_redirect_uri=redirect_uri))
    client = TestClient(app)

    session_payload = client.post("/auth/feishu/login-session").json()
    session_id = session_payload["session_id"]

    callback_response = client.get(f"/auth/feishu/callback?state={session_id}&code=auth-code")
    assert callback_response.status_code == 403
    assert "Alice Zhang" in callback_response.text
    assert "ou_alice" in callback_response.text

    error_response = client.get(f"/auth/feishu/login-session/{session_id}")
    assert error_response.status_code == 200
    payload = error_response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "feishu user is not mapped to gateway permissions"
    assert payload["details"]["name"] == "Alice Zhang"
    assert payload["details"]["open_id"] == "ou_alice"
    assert "email" not in payload["details"]


def test_feishu_name_mapping_does_not_fall_back_to_email(monkeypatch, sample_gateway_config, tmp_path):
    config_path = write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["auth"]["feishu_users"] = [
        {
            "email": "alice@example.com",
            "id": "alice-by-email",
            "roles": ["analyst"],
            "attributes": {},
        }
    ]
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    monkeypatch.setenv("PARQUET_GATEWAY_CONFIG", str(config_path))
    monkeypatch.setenv("PARQUET_GATEWAY_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    reset_config_cache()
    app = create_app(feishu_client=FakeFeishuOAuthClient())
    client = TestClient(app)

    response = client.post(
        "/auth/feishu/exchange",
        json={"code": "auth-code", "redirect_uri": "http://127.0.0.1:8765/callback"},
    )

    assert response.status_code == 403


def test_exchange_requires_user_info_profile(sample_gateway_config, tmp_path):
    class TokenOnlyFeishuClient:
        def exchange_code(self, code: str, redirect_uri: str) -> dict:
            return {"access_token": "feishu-user-access-token"}

    config = load_config(write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml"))

    try:
        exchange_feishu_code_for_gateway_token(
            config,
            TokenOnlyFeishuClient(),
            FeishuExchangeRequest(code="auth-code", redirect_uri="http://127.0.0.1:8765/callback"),
        )
    except AttributeError as exc:
        assert "get_user_info" in str(exc)
    else:
        raise AssertionError("expected Feishu client to fetch user_info")


def test_unmapped_feishu_user_error_includes_profile(monkeypatch, sample_gateway_config, tmp_path):
    config_path = write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw["auth"]["feishu_users"] = []
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    monkeypatch.setenv("PARQUET_GATEWAY_CONFIG", str(config_path))
    monkeypatch.setenv("PARQUET_GATEWAY_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    reset_config_cache()
    app = create_app(feishu_client=FakeFeishuOAuthClient())
    client = TestClient(app)

    response = client.post(
        "/auth/feishu/exchange",
        json={"code": "auth-code", "redirect_uri": "http://127.0.0.1:8765/callback"},
    )

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "permission_denied"
    assert error["details"]["open_id"] == "ou_alice"
    assert error["details"]["name"] == "Alice Zhang"
    assert "email" not in error["details"]


def test_feishu_http_error_becomes_auth_error(sample_gateway_config, tmp_path):
    config = load_config(write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml"))
    client = FeishuOAuthClient(config)
    http_error = HTTPError(
        "https://open.feishu.cn/open-apis/authen/v2/oauth/token",
        400,
        "Bad Request",
        hdrs={},
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        try:
            client.exchange_code("bad-code", "http://127.0.0.1:8765/callback")
        except AuthError as exc:
            assert "feishu token exchange failed" in exc.message
        else:
            raise AssertionError("expected HTTPError to be converted to AuthError")


def test_feishu_oauth_client_accepts_user_access_token_field(sample_gateway_config, tmp_path):
    config = load_config(write_feishu_config(sample_gateway_config, tmp_path / "feishu.yml"))
    client = FeishuOAuthClient(config)
    raw_response = {
        "code": 0,
        "msg": "success",
        "data": {"user_access_token": "feishu-user-token"},
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            import json

            return json.dumps(raw_response).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=FakeResponse()):
        payload = client.exchange_code("auth-code", "http://127.0.0.1:8765/callback")

    assert payload["access_token"] == "feishu-user-token"
