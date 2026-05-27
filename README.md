# Parquet 查询网关

这是一个带权限控制的 Parquet 查询网关。最终用户入口是 **OpenCLI**，后端服务负责认证、授权、审计，并用 DuckDB 原地查询服务器上的 Parquet 文件。

服务不会把真实文件路径暴露给用户。客户端只提交受限 JSON 查询 DSL，服务端会先检查 dataset 权限、字段权限和行级权限，再生成参数化 DuckDB SQL 执行。

Parquet 文件统一放在：

```text
/home/ai_ds/sd_data_center
```

配置里的 dataset 路径必须是相对这个目录的路径，例如 `orders/*.parquet`。服务端会拒绝绝对路径和 `..` 越界路径。

## 安装

完整安装流程见：[Parquet 查询网关安装指南](docs/installation-guide.md)。

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## 启动服务

```bash
$env:PARQUET_GATEWAY_CONFIG = "config/example.yml"
$env:PARQUET_GATEWAY_AUDIT_DB = "audit.sqlite3"
uvicorn parquet_gateway.app:create_app --factory --host 0.0.0.0 --port 8080
```

## 生产配置

在服务器上创建 `config/production.yml`：

```yaml
settings:
  data_root: /home/ai_ds/sd_data_center
  max_limit: 1000
  default_limit: 100
  query_timeout_seconds: 30

users:
  - id: alice
    token: replace-with-secret-token
    roles: [analyst]
    attributes:
      regions: [US, EU]

datasets:
  orders:
    description: Orders dataset
    path: orders/*.parquet
    roles: [analyst, admin]
    columns:
      analyst: [order_id, order_date, region, amount]
      admin: [order_id, order_date, region, amount, margin, customer_email]
    row_policy:
      field: region
      source: attributes.regions
```

权限含义：

- `roles`：哪些角色可以访问这个 dataset。
- `columns`：不同角色能看到哪些字段。
- `row_policy`：服务端强制追加的行级过滤条件。
- `attributes.regions`：从当前用户属性中读取允许访问的区域列表。

## 部署

Docker：

```bash
docker compose up --build -d
```

Systemd：

```bash
sudo mkdir -p /opt/parquet-query-gateway /var/lib/parquet-query-gateway
sudo cp deploy/parquet-gateway.service /etc/systemd/system/parquet-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable --now parquet-gateway
```

## OpenCLI 原生插件使用方式

推荐把本项目作为 OpenCLI 插件安装：

```bash
opencli plugin install file:///absolute/path/to/this/project
```

设置网关地址和访问 token：

```bash
$env:PARQUET_GATEWAY_URL = "http://127.0.0.1:8080"
$env:PARQUET_GATEWAY_TOKEN = "analyst-token"
```

通过 OpenCLI 使用：

```bash
opencli parquet datasets
opencli parquet schema orders
opencli parquet query orders --select order_id,region,amount --where "amount>=10" --limit 100
opencli parquet audit --limit 50
```

本项目也保留了 `parquet-gw` 本地命令，适合调试或在不经过 OpenCLI 时直接调用：

```bash
parquet-gw datasets
parquet-gw schema orders
parquet-gw query orders --select order_id,amount --where "region in [\"US\",\"EU\"]"
parquet-gw audit --limit 50
```

## HTTP 示例

列出当前用户可见的数据集：

```bash
curl -H "Authorization: Bearer analyst-token" http://127.0.0.1:8080/datasets
```

提交查询：

```bash
curl -X POST http://127.0.0.1:8080/query \
  -H "Authorization: Bearer analyst-token" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "orders",
    "select": ["order_date", "region", "amount"],
    "filters": [{"field": "order_date", "op": ">=", "value": "2026-01-01"}],
    "limit": 100
  }'
```

## 查询 DSL

支持的过滤操作符：

```text
=, !=, >, >=, <, <=, in, contains, startswith
```

聚合查询示例：

```json
{
  "dataset": "orders",
  "group_by": ["region"],
  "aggregates": [{"func": "sum", "field": "amount", "as": "total_amount"}],
  "limit": 100
}
```

## 权限模型

权限控制全部在服务端执行，OpenCLI 客户端不能绕过。

- 用户通过 YAML 中配置的 bearer token 认证。
- 用户只能看到自己角色允许访问的 dataset。
- 用户只能选择自己角色允许访问的字段。
- 行级权限由服务端从用户属性中读取并强制注入。
- 客户端不能提交 Parquet 文件路径。
- 客户端不能提交任意 SQL。
- 每次查询都会写入审计数据库。
- `opencli parquet audit` 需要 `admin` 角色。

## 飞书授权

可以接飞书授权，推荐接在服务端，而不是接在 OpenCLI 插件里。

推荐流程：

```text
用户登录飞书
  -> FastAPI 完成飞书 OAuth / OIDC 回调
  -> 服务端根据飞书 open_id / user_id / email 映射内部用户和角色
  -> 服务端签发本项目自己的短期访问 token
  -> OpenCLI 插件携带 PARQUET_GATEWAY_TOKEN 调用网关
```

这样做的原因：

- 权限仍然集中在服务端，OpenCLI 插件不能伪造角色。
- 可以把飞书部门、用户组或邮箱映射成 `analyst`、`admin` 等内部角色。
- 后续也可以替换成公司 SSO/OIDC，不影响 `opencli parquet ...` 命令形态。

第一阶段可以继续使用 YAML token；生产阶段建议把 `users` 替换为飞书登录后的用户映射和短期 token 存储。

## 测试

```bash
pytest
```
