from __future__ import annotations

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


def test_datasets_requires_auth(monkeypatch, sample_gateway_config, tmp_path):
    client = make_client(monkeypatch, sample_gateway_config, tmp_path)

    response = client.get("/datasets")

    assert response.status_code == 401


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
