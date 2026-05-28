from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_opencli_plugin_manifest_exists():
    manifest = json.loads((ROOT / "opencli-plugin.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "parquet"
    assert manifest["opencli"] == ">=1.0.0"


def test_opencli_plugin_commands_register_parquet_site():
    for filename in ["datasets.js", "schema.js", "query.js", "audit.js", "login.js", "smoke-test.js"]:
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "from '@jackwener/opencli/registry'" in source
        assert "site: 'parquet'" in source
        assert "browser: false" in source


def test_opencli_plugin_login_uses_feishu_exchange():
    source = (ROOT / "login.js").read_text(encoding="utf-8")
    auth_source = (ROOT / "auth-flow.js").read_text(encoding="utf-8")

    assert "/auth/feishu/exchange" in auth_source
    assert "PARQUET_GATEWAY_TOKEN" in source


def test_opencli_plugin_login_is_one_click_flow():
    source = (ROOT / "login.js").read_text(encoding="utf-8")
    auth_source = (ROOT / "auth-flow.js").read_text(encoding="utf-8")

    assert "loginWithFeishu" in source
    assert "createServer" in auth_source
    assert "openBrowser" in auth_source
    assert "waitForCallbackCode" in auth_source
    assert "saveGatewayToken" in auth_source
    assert "PARQUET_FEISHU_AUTH_URL" in auth_source
    assert "/auth/feishu/authorize-url" in auth_source
    assert "http://127.0.0.1:8765/callback" in auth_source


def test_opencli_plugin_query_uses_gateway_not_local_files():
    source = (ROOT / "query.js").read_text(encoding="utf-8")
    client_source = (ROOT / "gateway-client.js").read_text(encoding="utf-8")

    assert "PARQUET_GATEWAY_URL" in client_source
    assert "PARQUET_GATEWAY_TOKEN" in client_source
    assert "readSavedGatewayToken" in client_source
    assert "loginWithFeishu" in client_source
    assert "read_parquet" not in source
    assert "/query" in source


def test_opencli_plugin_has_smoke_test_command():
    source = (ROOT / "smoke-test.js").read_text(encoding="utf-8")

    assert "name: 'smoke-test'" in source
    assert "/health" in source
    assert "/datasets" in source
    assert "/query" in source


def test_client_install_scripts_do_not_start_or_configure_gateway():
    for filename in ["client-install.sh", "client-install.ps1"]:
        source = (ROOT / "scripts" / filename).read_text(encoding="utf-8")
        assert "parquet-gateway" not in source
        assert "init-config" not in source
        assert "production.yml" not in source
        assert "PARQUET_GATEWAY_CONFIG" not in source
        assert "uvicorn" not in source


def test_client_install_guide_is_client_only():
    source = (ROOT / "docs" / "client-installation-guide.md").read_text(encoding="utf-8")

    assert "不会启动" in source
    assert "parquet-gateway" in source
    assert "PARQUET_GATEWAY_URL" in source
    assert "opencli parquet smoke-test" in source
    assert "不要创建 production.yml" in source
