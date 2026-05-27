from __future__ import annotations

import yaml
from fastapi.testclient import TestClient

from parquet_gateway.app import create_app, reset_config_cache
from parquet_gateway.auth import TokenAuthenticator
from parquet_gateway.config import load_config
from parquet_gateway.errors import PermissionDenied
from parquet_gateway.feishu import FeishuExchangeRequest, exchange_feishu_code_for_gateway_token


class FakeFeishuOAuthClient:
    def __init__(self):
        self.user_info_requested = False

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        assert code == "auth-code"
        assert redirect_uri == "http://127.0.0.1:8765/callback"
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


def write_feishu_config(base_config_path, target_path):
    raw = yaml.safe_load(base_config_path.read_text(encoding="utf-8"))
    raw["auth"] = {
        "gateway_token_secret": "unit-test-secret",
        "token_ttl_seconds": 3600,
        "feishu": {
            "enabled": True,
            "app_id": "cli_a_test",
            "app_secret": "secret",
            "redirect_uri": "http://127.0.0.1:8765/callback",
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
    assert feishu_client.user_info_requested is True
    principal = TokenAuthenticator(load_config(config_path)).authenticate_header(f"Bearer {payload['access_token']}")
    assert principal.id == "alice"
    assert principal.attributes["regions"] == ["US"]


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
    assert error["details"]["email"] == "alice@example.com"
    assert error["details"]["name"] == "Alice Zhang"
