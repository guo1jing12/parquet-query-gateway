# Parquet 查询网关安装指南

以下步骤面向 AI Agent 和本地部署用户。部分步骤需要用户提供 GitHub 私有仓库访问权限、服务器路径和访问 token。

## 环境要求

开始安装前，请确认环境中已安装：

- Python 3.12+
- Git
- OpenCLI
- GitHub CLI `gh`，用于访问私有仓库
- Docker，可选，仅 Docker 部署需要

Parquet 文件默认放在服务器目录：

```text
/home/ai_ds/sd_data_center
```

## 一键交给 AI Agent 安装

把下面这段发给你的 AI Agent：

```text
帮我安装 Parquet 查询网关：

1. 确认 GitHub CLI 已登录：
   gh auth status

2. 克隆私有仓库：
   gh repo clone guo1jing12/parquet-query-gateway

3. 进入项目并安装 Python 包：
   cd parquet-query-gateway
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"

4. 安装 OpenCLI 插件：
   opencli plugin install file://$PWD

5. 根据 README 创建 config/production.yml，并确认 Parquet 文件位于 /home/ai_ds/sd_data_center。

6. 启动服务并验证：
   $env:PARQUET_GATEWAY_CONFIG = "config/production.yml"
   $env:PARQUET_GATEWAY_AUDIT_DB = "audit.sqlite3"
   uvicorn parquet_gateway.app:create_app --factory --host 0.0.0.0 --port 8080
```

如果在 Linux 服务器上安装，把第 3 步激活虚拟环境改为：

```bash
source .venv/bin/activate
```

## 第 1 步 克隆私有仓库

```bash
gh auth status
gh repo clone guo1jing12/parquet-query-gateway
cd parquet-query-gateway
```

如果 `gh auth status` 显示未登录，先执行：

```bash
gh auth login
```

## 第 2 步 安装 Python 服务

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 第 3 步 配置数据集和权限

复制示例配置：

```bash
cp config/example.yml config/production.yml
```

编辑 `config/production.yml`：

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

注意：

- `path` 必须是相对 `/home/ai_ds/sd_data_center` 的路径。
- 不允许写绝对路径。
- 不允许使用 `..` 跳出数据根目录。
- 生产 token 请替换为高强度随机值。

## 第 4 步 启动服务

Windows PowerShell：

```powershell
$env:PARQUET_GATEWAY_CONFIG = "config/production.yml"
$env:PARQUET_GATEWAY_AUDIT_DB = "audit.sqlite3"
uvicorn parquet_gateway.app:create_app --factory --host 0.0.0.0 --port 8080
```

Linux：

```bash
export PARQUET_GATEWAY_CONFIG=config/production.yml
export PARQUET_GATEWAY_AUDIT_DB=audit.sqlite3
uvicorn parquet_gateway.app:create_app --factory --host 0.0.0.0 --port 8080
```

## 第 5 步 安装 OpenCLI 插件

在项目根目录执行：

```bash
opencli plugin install file://$PWD
```

Windows PowerShell 可使用绝对路径：

```powershell
opencli plugin install "file:///C:/Users/guojingjing01/Documents/opencli"
```

## 第 6 步 配置访问网关

Windows PowerShell：

```powershell
$env:PARQUET_GATEWAY_URL = "http://127.0.0.1:8080"
$env:PARQUET_GATEWAY_TOKEN = "replace-with-secret-token"
```

Linux：

```bash
export PARQUET_GATEWAY_URL=http://127.0.0.1:8080
export PARQUET_GATEWAY_TOKEN=replace-with-secret-token
```

## 第 7 步 验证

验证服务：

```bash
curl http://127.0.0.1:8080/health
```

验证 OpenCLI 插件：

```bash
opencli parquet datasets
opencli parquet schema orders
opencli parquet query orders --select order_id,region,amount --limit 10
```

管理员查看审计：

```bash
opencli parquet audit --limit 50
```

## Docker 部署

准备 `config/production.yml` 后执行：

```bash
docker compose up --build -d
```

`docker-compose.yml` 默认会把服务器目录挂载为只读：

```text
/home/ai_ds/sd_data_center:/home/ai_ds/sd_data_center:ro
```

## 飞书授权说明

如果要接飞书授权，建议把飞书 OAuth/OIDC 接在 FastAPI 服务端：

```text
飞书登录
  -> 服务端换取飞书用户身份
  -> 服务端映射内部角色和属性
  -> 服务端签发 PARQUET_GATEWAY_TOKEN
  -> OpenCLI 插件携带 token 查询
```

不要把飞书 App Secret 放进 OpenCLI 插件或用户本机配置。

## 常见问题

### OpenCLI 找不到 `parquet` 命令

重新安装插件：

```bash
opencli plugin install file://$PWD
```

然后重新打开终端。

### 查询返回权限不足

检查：

- `PARQUET_GATEWAY_TOKEN` 是否正确。
- 用户角色是否在 dataset 的 `roles` 中。
- 请求字段是否在该角色的 `columns` 中。
- 行级权限需要的用户属性是否存在。

### 查询不到数据

检查：

- Parquet 文件是否在 `/home/ai_ds/sd_data_center` 下。
- dataset `path` 是否为相对路径。
- `row_policy` 是否过滤掉了全部数据。

### 私有仓库无法克隆

先登录 GitHub CLI：

```bash
gh auth login
gh auth status
```
