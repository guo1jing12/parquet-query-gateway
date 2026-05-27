from __future__ import annotations

import pytest

from parquet_gateway.auth import TokenAuthenticator
from parquet_gateway.config import load_config
from parquet_gateway.errors import BadQuery, PermissionDenied
from parquet_gateway.models import QueryRequest
from parquet_gateway.query_builder import compile_query


def compile_for_analyst(config_path, payload):
    config = load_config(config_path)
    principal = TokenAuthenticator(config).authenticate_header("Bearer analyst-token")
    return compile_query(config, principal, QueryRequest.model_validate(payload))


def test_compiles_parameterized_query_with_row_policy(sample_gateway_config):
    compiled = compile_for_analyst(sample_gateway_config, {
        "dataset": "orders",
        "select": ["order_id", "amount"],
        "filters": [{"field": "amount", "op": ">=", "value": 10}],
        "limit": 50,
    })

    assert 'FROM read_parquet(?)' in compiled.sql
    assert '"amount" >= ?' in compiled.sql
    assert '"region" IN (?, ?)' in compiled.sql
    assert compiled.params[1:] == [10, "US", "EU"]
    assert compiled.output_columns == ["order_id", "amount"]


def test_rejects_dataset_paths_outside_data_root(sample_gateway_config, tmp_path):
    import yaml

    raw = yaml.safe_load(sample_gateway_config.read_text(encoding="utf-8"))
    raw["datasets"]["orders"]["path"] = "../secrets/*.parquet"
    bad_config = tmp_path / "bad.yml"
    bad_config.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(PermissionDenied):
        compile_for_analyst(bad_config, {"dataset": "orders", "select": ["order_id"]})


def test_default_select_uses_only_visible_columns(sample_gateway_config):
    compiled = compile_for_analyst(sample_gateway_config, {
        "dataset": "orders",
        "limit": 10,
    })

    assert "customer_email" not in compiled.sql
    assert compiled.output_columns == ["amount", "order_date", "order_id", "region"]


def test_rejects_column_without_permission(sample_gateway_config):
    with pytest.raises(PermissionDenied):
        compile_for_analyst(sample_gateway_config, {
            "dataset": "orders",
            "select": ["customer_email"],
        })


def test_rejects_invalid_identifier(sample_gateway_config):
    with pytest.raises(BadQuery):
        compile_for_analyst(sample_gateway_config, {
            "dataset": "orders",
            "select": ["amount; DROP TABLE x"],
        })


def test_compiles_aggregate_query(sample_gateway_config):
    compiled = compile_for_analyst(sample_gateway_config, {
        "dataset": "orders",
        "group_by": ["region"],
        "aggregates": [{"func": "sum", "field": "amount", "as": "total_amount"}],
        "limit": 10,
    })

    assert 'SELECT "region", sum("amount") AS "total_amount"' in compiled.sql
    assert 'GROUP BY "region"' in compiled.sql


def test_allows_ordering_aggregate_query_by_output_alias(sample_gateway_config):
    compiled = compile_for_analyst(sample_gateway_config, {
        "dataset": "orders",
        "group_by": ["region"],
        "aggregates": [{"func": "sum", "field": "amount", "as": "total_amount"}],
        "order_by": [{"field": "total_amount", "direction": "desc"}],
        "limit": 10,
    })

    assert 'ORDER BY "total_amount" DESC' in compiled.sql


def test_rejects_ordering_by_hidden_column(sample_gateway_config):
    with pytest.raises(PermissionDenied):
        compile_for_analyst(sample_gateway_config, {
            "dataset": "orders",
            "select": ["order_id"],
            "order_by": [{"field": "customer_email", "direction": "asc"}],
            "limit": 10,
        })
