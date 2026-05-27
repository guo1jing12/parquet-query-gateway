from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from parquet_gateway.auth import Principal
from parquet_gateway.config import GatewayConfig
from parquet_gateway.errors import BadQuery, PermissionDenied
from parquet_gateway.models import Aggregate, Filter, QueryRequest
from parquet_gateway.policy import DatasetAccess, resolve_attribute, resolve_dataset_access

ALLOWED_IDENTIFIER_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


@dataclass(frozen=True)
class CompiledQuery:
    dataset_id: str
    sql: str
    params: list[Any]
    output_columns: list[str]


def compile_query(config: GatewayConfig, principal: Principal, request: QueryRequest) -> CompiledQuery:
    access = resolve_dataset_access(config, principal, request.dataset)
    validate_query_fields(access, request)

    limit = request.limit or config.settings.default_limit
    if limit > config.settings.max_limit:
        raise BadQuery(f"limit cannot exceed {config.settings.max_limit}")

    select_sql, output_columns = build_select_clause(access, request)
    params: list[Any] = [access.parquet_path]
    where_sql = build_where_clause(access, principal, request.filters, params)
    group_sql = build_group_clause(request)
    order_sql = build_order_clause(request, output_columns)

    sql = f"SELECT {select_sql} FROM read_parquet(?){where_sql}{group_sql}{order_sql} LIMIT {int(limit)}"
    return CompiledQuery(dataset_id=request.dataset, sql=sql, params=params, output_columns=output_columns)


def validate_query_fields(access: DatasetAccess, request: QueryRequest) -> None:
    requested = set(request.select) | set(request.group_by)
    requested.update(filter_.field for filter_ in request.filters)
    requested.update(aggregate.field for aggregate in request.aggregates if aggregate.field)
    for field in requested:
        validate_identifier(field)
        if field not in access.allowed_columns:
            raise PermissionDenied(f"field {field!r} is not visible in dataset {access.dataset_id!r}")

    aliases = [aggregate.alias for aggregate in request.aggregates]
    for alias in aliases:
        validate_identifier(alias)
    if len(aliases) != len(set(aliases)):
        raise BadQuery("aggregate aliases cannot contain duplicates")

    orderable_fields = set(request.select) | set(request.group_by) | set(aliases)
    if not request.aggregates and not request.select:
        orderable_fields = set(access.allowed_columns)
    for order in request.order_by:
        validate_identifier(order.field)
        if order.field not in aliases and order.field not in access.allowed_columns:
            raise PermissionDenied(f"field {order.field!r} is not visible in dataset {access.dataset_id!r}")
        if order.field not in orderable_fields:
            raise BadQuery(f"order field {order.field!r} must be selected")

    if request.aggregates and request.select:
        raise BadQuery("use group_by, not select, when aggregates are present")
    if not request.aggregates and request.group_by:
        raise BadQuery("group_by requires at least one aggregate")


def validate_identifier(value: str) -> None:
    if not value or value[0].isdigit() or any(ch not in ALLOWED_IDENTIFIER_CHARS for ch in value):
        raise BadQuery(f"invalid field identifier {value!r}")


def quote_identifier(value: str) -> str:
    validate_identifier(value)
    return f'"{value}"'


def build_select_clause(access: DatasetAccess, request: QueryRequest) -> tuple[str, list[str]]:
    if request.aggregates:
        pieces = [quote_identifier(field) for field in request.group_by]
        columns = list(request.group_by)
        for aggregate in request.aggregates:
            pieces.append(aggregate_sql(aggregate))
            columns.append(aggregate.alias)
        return ", ".join(pieces), columns

    fields = request.select or sorted(access.allowed_columns)
    return ", ".join(quote_identifier(field) for field in fields), fields


def aggregate_sql(aggregate: Aggregate) -> str:
    alias = quote_identifier(aggregate.alias)
    if aggregate.func == "count" and aggregate.field is None:
        return f"count(*) AS {alias}"
    return f"{aggregate.func}({quote_identifier(aggregate.field or '')}) AS {alias}"


def build_where_clause(access: DatasetAccess, principal: Principal, filters: list[Filter], params: list[Any]) -> str:
    pieces: list[str] = []
    for filter_ in filters:
        pieces.append(filter_sql(filter_, params))

    if access.dataset.row_policy is not None:
        policy = access.dataset.row_policy
        if policy.field not in access.allowed_columns:
            raise PermissionDenied(f"row policy field {policy.field!r} is not visible to user {principal.id!r}")
        value = resolve_attribute(principal, policy.source)
        values = value if isinstance(value, list) else [value]
        if not values:
            raise PermissionDenied(f"row policy source {policy.source!r} is empty for user {principal.id!r}")
        placeholders = ", ".join("?" for _ in values)
        pieces.append(f"{quote_identifier(policy.field)} IN ({placeholders})")
        params.extend(values)

    return "" if not pieces else " WHERE " + " AND ".join(f"({piece})" for piece in pieces)


def filter_sql(filter_: Filter, params: list[Any]) -> str:
    field = quote_identifier(filter_.field)
    if filter_.op == "in":
        values = list(filter_.value)
        if not values:
            raise BadQuery("operator 'in' requires at least one value")
        params.extend(values)
        return f"{field} IN ({', '.join('?' for _ in values)})"
    if filter_.op == "contains":
        params.append(f"%{filter_.value}%")
        return f"CAST({field} AS VARCHAR) LIKE ?"
    if filter_.op == "startswith":
        params.append(f"{filter_.value}%")
        return f"CAST({field} AS VARCHAR) LIKE ?"
    params.append(filter_.value)
    return f"{field} {filter_.op} ?"


def build_group_clause(request: QueryRequest) -> str:
    if not request.group_by:
        return ""
    return " GROUP BY " + ", ".join(quote_identifier(field) for field in request.group_by)


def build_order_clause(request: QueryRequest, output_columns: list[str]) -> str:
    if not request.order_by:
        return ""
    output_set = set(output_columns)
    pieces = []
    for order in request.order_by:
        if output_columns != ["*"] and order.field not in output_set:
            raise BadQuery(f"order field {order.field!r} must be selected")
        pieces.append(f"{quote_identifier(order.field)} {order.direction.upper()}")
    return " ORDER BY " + ", ".join(pieces)
