from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import yaml
from fastapi.testclient import TestClient

from parquet_gateway.app import create_app, reset_config_cache


def make_client(monkeypatch, sample_gateway_config, tmp_path):
    monkeypatch.setenv("PARQUET_GATEWAY_CONFIG", str(sample_gateway_config))
    monkeypatch.setenv("PARQUET_GATEWAY_AUDIT_DB", str(tmp_path / "audit.sqlite3"))
    reset_config_cache()
    return TestClient(create_app())


def test_health(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/health")

    assert response.status_code == 200, response.json()
    assert response.json() == {"status": "ok"}


def test_downloads_client_package(monkeypatch, sample_gateway_config, tmp_path):
    package = tmp_path / "parquet-query-gateway-client.zip"
    package.write_bytes(b"zip-bytes")
    monkeypatch.setenv("PARQUET_GATEWAY_CLIENT_PACKAGE", str(package))
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/downloads/parquet-query-gateway-client.zip")

    assert response.status_code == 200
    assert response.content == b"zip-bytes"
    assert response.headers["content-type"] == "application/zip"


def test_downloads_client_package_returns_404_when_missing(monkeypatch, sample_gateway_config, tmp_path):
    monkeypatch.setenv("PARQUET_GATEWAY_CLIENT_PACKAGE", str(tmp_path / "missing.zip"))
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/downloads/parquet-query-gateway-client.zip")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_client_installation_guide_serves_markdown(monkeypatch, sample_gateway_config, tmp_path):
    guide = tmp_path / "client-installation-guide.md"
    guide.write_text("# Client Guide\n\nGateway: http://192.168.58.184:8080\n", encoding="utf-8")
    monkeypatch.setenv("PARQUET_GATEWAY_CLIENT_GUIDE", str(guide))
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/client-installation-guide.md")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "charset=utf-8" in response.headers["content-type"]
    assert "attachment" not in response.headers.get("content-disposition", "")
    assert "Gateway: http://192.168.58.184:8080" in response.text


def test_client_version_endpoint_returns_update_metadata(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/client/version")

    assert response.status_code == 200
    assert response.json() == {
        "client_version": "0.1.4",
        "latest_version": "0.1.4",
        "download_url": "/downloads/parquet-query-gateway-client.zip",
        "guide_url": "/client-installation-guide.md",
    }


def test_response_marks_outdated_client_version(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/health", headers={"X-Parquet-Client-Version": "0.0.1"})

    assert response.status_code == 200
    assert response.headers["X-Parquet-Client-Version-Status"] == "outdated"
    assert response.headers["X-Parquet-Client-Latest-Version"] == "0.1.4"
    assert response.headers["X-Parquet-Client-Download-Url"] == "/downloads/parquet-query-gateway-client.zip"


def test_response_marks_missing_client_version_as_outdated(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Parquet-Client-Version-Status"] == "outdated"
    assert response.headers["X-Parquet-Client-Latest-Version"] == "0.1.4"


def test_datasets_requires_auth(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/datasets")

    assert response.status_code == 401


def test_feishu_authorize_url_is_exposed_without_secret(monkeypatch, sample_gateway_config, tmp_path):
    raw = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    raw["auth"] = {
        "gateway_token_secret": "gateway-secret",
        "feishu": {
            "enabled": True,
            "app_id": "cli_test",
            "app_secret": "feishu-secret",
            "redirect_uri": "http://127.0.0.1:8765/callback",
        },
        "feishu_users": [],
    }
    sample_gateway_config.write_text(yaml.safe_dump(raw), encoding="utf-8")
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/auth/feishu/authorize-url")

    assert response.status_code == 200, response.json()
    payload = response.json()
    parsed = urlparse(payload["auth_url"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.feishu.cn"
    assert params["client_id"] == ["cli_test"]
    assert params["response_type"] == ["code"]
    assert params["redirect_uri"] == ["http://127.0.0.1:8765/callback"]
    assert "feishu-secret" not in payload["auth_url"]


def test_query_applies_permissions_and_audits(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.post(
        "/query",
        headers={"Authorization": "Bearer analyst-token"},
        json={
            "dataset": "orders",
            "select": ["order_id", "region"],
            "order_by": [{"field": "order_id", "direction": "asc"}],
            "limit": 10,
        },
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["row_count"] == 2
    assert payload["rows"] == [
        {"order_id": 1, "region": "US"},
        {"order_id": 2, "region": "EU"},
    ]
    assert client.app.state.audit.recent()[0]["allowed"] is True


def test_query_denies_hidden_column_and_audits(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.post(
        "/query",
        headers={"Authorization": "Bearer analyst-token"},
        json={"dataset": "orders", "select": ["customer_email"]},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
    assert client.app.state.audit.recent()[0]["allowed"] is False


def test_admin_can_read_audit_events(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)
    client.post(
        "/query",
        headers={"Authorization": "Bearer analyst-token"},
        json={"dataset": "orders", "select": ["order_id"], "limit": 1},
    )

    response = client.get("/admin/audit", headers={"Authorization": "Bearer admin-token"})

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["events"][0]["user_id"] == "alice"
    assert payload["events"][0]["dataset"] == "orders"


def test_non_admin_cannot_read_audit_events(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/audit", headers={"Authorization": "Bearer analyst-token"})

    assert response.status_code == 403


def test_admin_can_read_redacted_config(monkeypatch, sample_gateway_config, tmp_path):
    raw = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    raw["auth"] = {
        "gateway_token_secret": "gateway-secret",
        "feishu": {
            "enabled": True,
            "app_id": "cli_test",
            "app_secret": "feishu-secret",
            "redirect_uri": "http://127.0.0.1:8765/callback",
        },
        "feishu_users": [],
    }
    sample_gateway_config.write_text(yaml.safe_dump(raw), encoding="utf-8")
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config", headers={"Authorization": "Bearer admin-token"})

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["path"] == str(sample_gateway_config)
    assert payload["config"]["auth"]["gateway_token_secret"] == "********"
    assert payload["config"]["auth"]["feishu"]["app_secret"] == "********"
    assert "gateway-secret" not in payload["yaml"]
    assert "feishu-secret" not in payload["yaml"]


def test_non_admin_cannot_read_config(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config", headers={"Authorization": "Bearer analyst-token"})

    assert response.status_code == 403


def test_admin_can_validate_and_save_config(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)
    raw = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    raw["auth"] = {
        "gateway_token_secret": "new-gateway-secret",
        "feishu": {
            "enabled": True,
            "app_id": "cli_new",
            "app_secret": "new-feishu-secret",
            "redirect_uri": "http://127.0.0.1:8765/callback",
        },
        "feishu_users": [
            {
                "open_id": "ou_alice",
                "id": "alice-feishu",
                "roles": ["analyst"],
                "attributes": {},
            }
        ],
    }
    new_yaml = yaml.safe_dump(raw)

    response = client.put(
        "/admin/config",
        headers={"Authorization": "Bearer admin-token"},
        json={"yaml": new_yaml},
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["valid"] is True
    assert payload["backup_path"].endswith(".bak")
    saved = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    assert saved["auth"]["feishu"]["app_id"] == "cli_new"
    assert any(sample_gateway_config.parent.glob("gateway.yml.*.bak"))
    reset_config_cache()


def test_admin_can_save_config_with_post(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)
    raw = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    raw["auth"] = {
        "gateway_token_secret": "new-gateway-secret",
        "feishu": {
            "enabled": True,
            "app_id": "cli_post_save",
            "app_secret": "new-feishu-secret",
            "redirect_uri": "http://127.0.0.1:8765/callback",
        },
        "feishu_users": [],
    }

    response = client.post(
        "/admin/config",
        headers={"Authorization": "Bearer admin-token"},
        json={"yaml": yaml.safe_dump(raw)},
    )

    assert response.status_code == 200, response.json()
    saved = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    assert saved["auth"]["feishu"]["app_id"] == "cli_post_save"
    reset_config_cache()


def test_admin_config_save_preserves_redacted_secrets(monkeypatch, sample_gateway_config, tmp_path):
    raw = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    raw["auth"] = {
        "gateway_token_secret": "gateway-secret",
        "feishu": {
            "enabled": True,
            "app_id": "cli_test",
            "app_secret": "feishu-secret",
            "redirect_uri": "http://127.0.0.1:8765/callback",
        },
        "feishu_users": [],
    }
    sample_gateway_config.write_text(yaml.safe_dump(raw), encoding="utf-8")
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)
    payload = client.get("/admin/config", headers={"Authorization": "Bearer admin-token"}).json()

    response = client.put(
        "/admin/config",
        headers={"Authorization": "Bearer admin-token"},
        json={"yaml": payload["yaml"]},
    )

    assert response.status_code == 200, response.json()
    saved = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    assert [user["token"] for user in saved["users"]] == ["analyst-token", "admin-token"]
    assert saved["auth"]["gateway_token_secret"] == "gateway-secret"
    assert saved["auth"]["feishu"]["app_secret"] == "feishu-secret"


def test_admin_config_save_rejects_invalid_yaml(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.put(
        "/admin/config",
        headers={"Authorization": "Bearer admin-token"},
        json={"yaml": "users: []\ndatasets: {}\n"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_query"


def test_admin_config_reload_clears_cached_config(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.post("/admin/config/reload", headers={"Authorization": "Bearer admin-token"})

    assert response.status_code == 200
    assert response.json()["reloaded"] is True


def test_admin_config_ui_serves_html(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config-ui")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Parquet Gateway Config" in response.text
    assert "role-dropdown" in response.text
    assert "role-dropdown-menu" in response.text
    assert "attribute-field" in response.text
    assert "finance" in response.text
    assert "operations" in response.text
    assert "promotion" in response.text
    assert "warehouse" in response.text
    assert "hr" in response.text


def test_admin_config_ui_save_handles_request_failures(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config-ui")

    assert response.status_code == 200
    html = response.text
    assert "async function readJsonResponse" in html
    save_start = html.index("async function saveConfig")
    save_end = html.index("function renderAll")
    save_source = html[save_start:save_end]
    assert "try {" in save_source
    assert "catch (err)" in save_source
    assert "保存失败" in save_source
    assert "finally" in save_source


def test_admin_config_ui_saves_with_post_to_avoid_put_blocks(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config-ui")

    assert response.status_code == 200
    html = response.text
    save_start = html.index("async function saveConfig")
    save_end = html.index("function renderAll")
    save_source = html[save_start:save_end]
    assert 'method: "POST"' in save_source
    assert 'method: "PUT"' not in save_source


def test_admin_config_ui_renders_empty_attributes_as_empty_mapping(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config-ui")

    assert response.status_code == 200
    html = response.text
    assert 'if (!Object.keys(obj).length) return "{}";' in html
    assert 'const prefix = " ".repeat(indent) + "-";' in html
    assert 'return " ".repeat(indent) + key + ": " + rendered;' in html
    assert 'return " ".repeat(indent) + key + ":\\n" + rendered;' in html


def test_admin_config_ui_removing_user_updates_yaml(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config-ui")

    assert response.status_code == 200
    html = response.text
    assert 'node.querySelector(".remove-user").addEventListener("click", () => {' in html
    assert "node.remove();" in html
    assert "syncUsersFromForm();" in html
    assert "renderYaml();" in html


def test_admin_config_ui_adding_user_updates_yaml(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config-ui")

    assert response.status_code == 200
    html = response.text
    assert '$("add-user").addEventListener("click", () => {' in html
    add_start = html.index('$("add-user").addEventListener("click"')
    add_end = html.index('$("sync-users").addEventListener("click"')
    add_source = html[add_start:add_end]
    assert "addUserCard" in add_source
    assert "syncUsersFromForm();" in add_source
    assert "renderYaml();" in add_source


def test_admin_config_ui_user_field_changes_update_yaml(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config-ui")

    assert response.status_code == 200
    html = response.text
    assert "const syncUserCard = () => {" in html
    assert "updateTitle();" in html
    assert "syncUsersFromForm();" in html
    assert "renderYaml();" in html
    assert 'node.querySelectorAll("input,textarea").forEach((el) => el.addEventListener("input", syncUserCard));' in html
    assert "renderRoleDropdown(node.querySelector(\".user-roles\"), user.roles || [], syncUserCard);" in html
    assert "function renderRoleDropdown(container, selected, onChange)" in html
    assert "if (onChange) onChange();" in html


def test_admin_config_save_normalizes_empty_attributes(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)
    raw = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    raw["auth"] = {
        "gateway_token_secret": "gateway-secret",
        "feishu": {
            "enabled": True,
            "app_id": "cli_test",
            "app_secret": "feishu-secret",
            "redirect_uri": "http://127.0.0.1:8765/callback",
        },
        "feishu_users": [
            {
                "name": "Alice",
                "id": "alice-feishu",
                "roles": ["analyst"],
                "attributes": None,
            }
        ],
    }
    raw["users"][0]["attributes"] = None
    raw["users"][1]["attributes"] = None

    response = client.post(
        "/admin/config",
        headers={"Authorization": "Bearer admin-token"},
        json={"yaml": yaml.safe_dump(raw)},
    )

    assert response.status_code == 200, response.json()
    saved = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    assert saved["auth"]["feishu_users"][0]["attributes"] == {}
    assert saved["users"][0]["attributes"] == {}
    assert saved["users"][1]["attributes"] == {}
    reset_config_cache()


def test_admin_can_discover_parquet_datasets(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config/discover-datasets", headers={"Authorization": "Bearer admin-token"})

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["data_root"] == str(tmp_path)
    assert payload["datasets"] == [
        {
            "id": "orders",
            "path": "orders/*.parquet",
            "description": "orders",
            "columns": ["order_id", "order_date", "region", "amount", "margin", "customer_email"],
            "configured": True,
            "file_count": 1,
        }
    ]


def test_non_admin_cannot_discover_parquet_datasets(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config/discover-datasets", headers={"Authorization": "Bearer analyst-token"})

    assert response.status_code == 403


def test_admin_discovery_supports_extensionless_parquet(monkeypatch, sample_gateway_config, tmp_path):
    source = tmp_path / "orders" / "part-000.parquet"
    target = tmp_path / "events" / "000000_0_2026-04"
    target.parent.mkdir()
    target.write_bytes(source.read_bytes())
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/admin/config/discover-datasets", headers={"Authorization": "Bearer admin-token"})

    assert response.status_code == 200, response.json()
    events = next(dataset for dataset in response.json()["datasets"] if dataset["id"] == "events")
    assert events["path"] == "events/*"
    assert events["columns"] == ["order_id", "order_date", "region", "amount", "margin", "customer_email"]
