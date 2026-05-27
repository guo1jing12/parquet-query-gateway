from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
import pyarrow.parquet as pq
from pydantic import ValidationError

from parquet_gateway.config import GatewayConfig
from parquet_gateway.errors import BadQuery

SECRET_MASK = "********"


def read_admin_config(config_path: Path) -> dict[str, object]:
    raw = _load_yaml(config_path.read_text(encoding="utf-8"))
    redacted = redact_config(raw)
    return {
        "path": str(config_path),
        "config": redacted,
        "yaml": yaml.safe_dump(redacted, allow_unicode=True, sort_keys=False),
    }


def save_admin_config_yaml(config_path: Path, yaml_text: str) -> dict[str, object]:
    parsed = validate_admin_config_yaml(yaml_text, existing=_load_yaml(config_path.read_text(encoding="utf-8")))
    backup_path = _backup_config(config_path)
    config_path.write_text(yaml.safe_dump(parsed, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"valid": True, "path": str(config_path), "backup_path": str(backup_path)}


def discover_parquet_datasets(config: GatewayConfig) -> dict[str, object]:
    data_root = Path(config.settings.data_root)
    configured = set(config.datasets.keys())
    datasets: list[dict[str, object]] = []
    if not data_root.exists():
        return {"data_root": str(data_root), "datasets": datasets}

    for child in sorted((path for path in data_root.iterdir() if path.is_dir()), key=lambda path: path.name):
        parquet_files = [path for path in sorted(child.iterdir()) if path.is_file() and not path.name.startswith(".")]
        schema = None
        schema_file: Path | None = None
        for parquet_file in parquet_files:
            try:
                schema = pq.read_schema(parquet_file)
                schema_file = parquet_file
                break
            except Exception:
                continue
        if schema is None:
            continue
        columns = [field.name for field in schema]
        path_pattern = f"{child.name}/*.parquet" if schema_file and schema_file.suffix == ".parquet" else f"{child.name}/*"
        datasets.append({
            "id": child.name,
            "path": path_pattern,
            "description": child.name,
            "columns": columns,
            "configured": child.name in configured,
            "file_count": len(parquet_files),
        })
    return {"data_root": str(data_root), "datasets": datasets}


def validate_admin_config_yaml(yaml_text: str, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        parsed = _load_yaml(yaml_text)
        if existing is not None:
            parsed = restore_redacted_secrets(parsed, existing)
        if not parsed.get("users"):
            raise ValueError("gateway config must define at least one user")
        if not parsed.get("datasets"):
            raise ValueError("gateway config must define at least one dataset")
        GatewayConfig.model_validate(parsed)
    except (yaml.YAMLError, ValidationError, ValueError) as exc:
        raise BadQuery(f"invalid gateway config: {exc}") from exc
    return parsed


def restore_redacted_secrets(parsed: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    existing_users = {user.get("id"): user for user in existing.get("users", []) if isinstance(user, dict)}
    for user in parsed.get("users", []):
        if isinstance(user, dict) and user.get("token") == SECRET_MASK:
            existing_token = existing_users.get(user.get("id"), {}).get("token")
            if existing_token:
                user["token"] = existing_token

    auth = parsed.get("auth")
    existing_auth = existing.get("auth", {})
    if isinstance(auth, dict) and isinstance(existing_auth, dict):
        if auth.get("gateway_token_secret") == SECRET_MASK and existing_auth.get("gateway_token_secret"):
            auth["gateway_token_secret"] = existing_auth["gateway_token_secret"]
        feishu = auth.get("feishu")
        existing_feishu = existing_auth.get("feishu", {})
        if isinstance(feishu, dict) and isinstance(existing_feishu, dict):
            if feishu.get("app_secret") == SECRET_MASK and existing_feishu.get("app_secret"):
                feishu["app_secret"] = existing_feishu["app_secret"]
    return parsed


def redact_config(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"gateway_token_secret", "app_secret", "token"} and item:
                redacted[key] = SECRET_MASK
            else:
                redacted[key] = redact_config(item)
        return redacted
    if isinstance(value, list):
        return [redact_config(item) for item in value]
    return value


def _load_yaml(text: str) -> dict[str, Any]:
    raw = yaml.safe_load(text) or {}
    if not isinstance(raw, dict):
        raise ValueError("gateway config must be a YAML mapping")
    return raw


def _backup_config(config_path: Path) -> Path:
    backup_path = config_path.with_name(f"{config_path.name}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak")
    backup_path.write_bytes(config_path.read_bytes())
    return backup_path
