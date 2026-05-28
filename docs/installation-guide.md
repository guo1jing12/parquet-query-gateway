# Parquet 查询网关安装指南

> 本文是管理员部署指南，只需要由网关管理员执行一次。普通用户不要按本文启动服务或生成 `production.yml`，请使用 [客户端安装指南](client-installation-guide.md)。

这份指南面向网关管理员，用于第一次部署或重建共享网关。当前推荐路径是：管理员克隆仓库，运行部署脚本，脚本自动安装依赖、扫描数据目录、生成生产配置和 token。

## 给 AI Agent 的管理员部署任务

把下面这段发给 AI Agent 即可：

```text
请帮我安装 Parquet Query Gateway。

安装目标：
- 仓库：https://github.com/guo1jing12/parquet-query-gateway.git
- 数据目录：/home/ai_ds/sd_data_center
- 部署方式：本机 Python 虚拟环境

请按顺序执行：
1. 检查 Python 3.11+、Git 是否可用。
2. 克隆仓库并进入项目目录。
3. 运行 bash scripts/install.sh --data-root /home/ai_ds/sd_data_center。
4. 根据脚本输出启动 parquet-gateway。
5. 使用脚本输出的 admin token 设置 PARQUET_GATEWAY_TOKEN。
6. 运行 parquet-gw smoke-test。
7. 如果安装了 OpenCLI，再运行 opencli parquet smoke-test。

如果中途需要我提供 sudo 权限、开放端口、飞书应用凭证或确认覆盖 production.yml，请先暂停并说明原因。
```

发布前请确认仓库已设置为公开，或安装用户已拥有访问权限。

## 前置条件

服务器或本机需要：

- Python 3.11+
- Git
- 可选：Node.js/npm，用于自动安装 OpenCLI
- 可选：Docker，用于容器部署

如果要使用飞书登录，还需要提前准备飞书应用的 `app_id`、`app_secret`、回调地址和授权 URL。默认安装不依赖飞书，直接使用安装脚本生成的 bearer token。

默认数据根目录：

```text
/home/ai_ds/sd_data_center
```

数据目录结构推荐为：

```text
/home/ai_ds/sd_data_center/
  dataset_a/
    part-000.parquet
  dataset_b/
    000000_0_2026-04
```

每个子目录会被自动识别为一个 dataset。文件可以有 `.parquet` 后缀，也可以是无后缀 Parquet 文件。

## 安装阶段

公开仓库后，用户执行：

```bash
git clone https://github.com/guo1jing12/parquet-query-gateway.git
cd parquet-query-gateway
bash scripts/install.sh --data-root /home/ai_ds/sd_data_center
```

Windows PowerShell：

```powershell
git clone https://github.com/guo1jing12/parquet-query-gateway.git
cd parquet-query-gateway
.\scripts\install.ps1 -DataRoot "/home/ai_ds/sd_data_center"
```

安装脚本会：

1. 创建 `.venv`
2. 安装 Python 包
3. 运行 `parquet-gw init-config`
4. 扫描数据根目录并生成 `config/production.yml`
5. 自动生成 admin/analyst token
6. 如本机有 npm，自动安装 OpenCLI 并注册 `parquet` 插件
7. 输出启动命令和 smoke test 命令

如果 `config/production.yml` 已存在，脚本会拒绝覆盖。确认要重建时使用：

```bash
bash scripts/install.sh --data-root /home/ai_ds/sd_data_center --overwrite-config
```

Windows：

```powershell
.\scripts\install.ps1 -DataRoot "/home/ai_ds/sd_data_center" -OverwriteConfig
```

## 凭证阶段

安装脚本会在终端输出两个静态 bearer token：

- `admin_token`：可查询所有自动生成 dataset，并可查看审计和管理配置
- `analyst_token`：可查询所有自动生成 dataset，但不能访问 admin API

请把 token 保存到安全位置。默认安装不会把 token 写入 shell profile，也不会上传到远端服务。

临时设置访问凭证：

```bash
export PARQUET_GATEWAY_URL=http://127.0.0.1:8080
export PARQUET_GATEWAY_TOKEN=<admin_token>
```

Windows PowerShell：

```powershell
$env:PARQUET_GATEWAY_URL = "http://127.0.0.1:8080"
$env:PARQUET_GATEWAY_TOKEN = "<admin_token>"
```

如需给其他用户使用，请给他们分配 `analyst_token` 或在 `config/production.yml` 中新增用户和角色。

## 自动生成生产配置

也可以单独运行：

```bash
parquet-gw init-config \
  --data-root /home/ai_ds/sd_data_center \
  --output config/production.yml
```

它会生成类似配置：

```yaml
settings:
  data_root: /home/ai_ds/sd_data_center
  max_limit: 1000
  default_limit: 100
  query_timeout_seconds: 30
users:
  - id: admin
    token: pgw-admin-...
    roles: [admin]
    attributes: {}
  - id: analyst
    token: pgw-analyst-...
    roles: [analyst]
    attributes: {}
datasets:
  gy_moojing_all_market_product_item:
    description: gy_moojing_all_market_product_item
    path: gy_moojing_all_market_product_item/*
    roles: [analyst, admin]
    columns:
      analyst: [brand, category, sales_amount]
      admin: [brand, category, sales_amount]
auth:
  gateway_token_secret: ...
  token_ttl_seconds: 28800
```

默认生成的权限策略是：

- `admin` 和 `analyst` 都能访问所有自动发现的 dataset
- 两个角色默认可见所有字段
- 不自动启用行级权限

这是为了保证安装后立即可用。上线前如需精细权限，请编辑 `config/production.yml` 或打开 admin 配置页面调整字段权限、角色和 row policy。

## 启动服务

Linux/macOS：

```bash
source .venv/bin/activate
export PARQUET_GATEWAY_CONFIG=config/production.yml
export PARQUET_GATEWAY_AUDIT_DB=audit.sqlite3
parquet-gateway
```

Windows PowerShell：

```powershell
$env:PARQUET_GATEWAY_CONFIG = "config/production.yml"
$env:PARQUET_GATEWAY_AUDIT_DB = "audit.sqlite3"
.\.venv\Scripts\parquet-gateway.exe
```

健康检查：

```bash
curl http://127.0.0.1:8080/health
```

## 验证阶段

设置安装脚本输出的 admin token 后：

```bash
export PARQUET_GATEWAY_URL=http://127.0.0.1:8080
export PARQUET_GATEWAY_TOKEN=pgw-admin-...
```

Windows PowerShell：

```powershell
$env:PARQUET_GATEWAY_URL = "http://127.0.0.1:8080"
$env:PARQUET_GATEWAY_TOKEN = "pgw-admin-..."
```

运行 smoke test：

```bash
parquet-gw smoke-test
```

如果已安装 OpenCLI：

```bash
opencli parquet smoke-test
opencli parquet datasets
opencli parquet schema <dataset_id>
opencli parquet query <dataset_id> --limit 5
```

## OpenCLI 插件

安装脚本会尽量自动安装 OpenCLI。手动安装：

```bash
npm install -g @jackwener/opencli
opencli plugin install "file://$PWD"
```

Windows PowerShell：

```powershell
npm.cmd install -g @jackwener/opencli
opencli plugin install "file:///$((Get-Location).Path.Replace('\', '/'))"
```

常用命令：

```bash
opencli parquet datasets
opencli parquet schema <dataset_id>
opencli parquet query <dataset_id> --select col1,col2 --limit 10
opencli parquet audit --limit 50
```

PowerShell 中 `>` 可能被当作重定向。过滤条件建议用等值条件，或改在 CMD/bash 中执行范围条件。

## Docker 部署

准备配置：

```bash
parquet-gw init-config --data-root /home/ai_ds/sd_data_center --output config/production.yml
```

启动：

```bash
docker compose up --build -d
```

`docker-compose.yml` 默认会把数据根目录只读挂载到容器：

```text
/home/ai_ds/sd_data_center:/home/ai_ds/sd_data_center:ro
```

## Systemd 部署

复制项目到 `/opt/parquet-query-gateway`，创建配置后：

```bash
sudo mkdir -p /var/lib/parquet-query-gateway
sudo cp deploy/parquet-gateway.service /etc/systemd/system/parquet-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable --now parquet-gateway
sudo systemctl status parquet-gateway
```

如果安装位置不是 `/opt/parquet-query-gateway`，请先调整 service 文件里的 `WorkingDirectory`、`Environment` 和 `ExecStart`。

## 飞书登录

默认安装不要求飞书登录，直接使用生成的 bearer token。

如果要启用飞书 OAuth：

1. 编辑 `config/production.yml` 的 `auth.feishu`
2. 配置 `app_id`、`app_secret`、`redirect_uri`
3. 配置 `auth.feishu_users`，普通场景使用飞书姓名 `name` 即可
4. 重启网关
5. 设置网关地址并登录

示例：

```yaml
auth:
  feishu_users:
    - name: 张三
      id: zhangsan
      roles: [analyst]
      attributes: {}
```

`open_id` 是可选字段，更稳定但不要求普通用户自己提供。

```bash
export PARQUET_GATEWAY_URL=http://127.0.0.1:8080
opencli parquet login
```

登录成功后会返回 `PARQUET_GATEWAY_TOKEN`，也会保存到：

```text
~/.parquet-gateway/token.json
```

后续 `opencli parquet ...` 命令会自动读取这个本地 token 文件；如果没有 token 文件，也会通过网关获取飞书授权链接并打开浏览器登录。

如果浏览器不能自动打开，也可以手动获取授权码后执行：

```bash
opencli parquet login <feishu_authorization_code>
```

需要用户在浏览器中完成飞书授权时，AI Agent 应暂停并提示用户完成登录。

## 更新和卸载

更新代码：

```bash
git pull
source .venv/bin/activate
python -m pip install -e ".[dev]"
opencli plugin update parquet
```

如果 OpenCLI 插件更新失败，可以重装：

```bash
opencli plugin uninstall parquet
opencli plugin install "file://$PWD"
```

卸载本地插件：

```bash
opencli plugin uninstall parquet
```

停止 systemd 服务：

```bash
sudo systemctl disable --now parquet-gateway
```

## 常见问题

### 没有发现任何 dataset

确认：

- `--data-root` 指向真实数据根目录
- 数据根目录下是“每个 dataset 一个子目录”
- 子目录里至少有一个可被 PyArrow 读取的 Parquet 文件

### OpenCLI 找不到 parquet 命令

重新安装插件：

```bash
opencli plugin install "file://$PWD"
opencli parquet --help
```

### 查询返回 401

确认 `PARQUET_GATEWAY_TOKEN` 是 `init-config` 或安装脚本输出的 token，不是示例占位符。

### 查询返回权限不足

检查 `config/production.yml`：

- 用户角色是否在 dataset 的 `roles` 中
- 查询字段是否在该角色的 `columns` 中
- 如果配置了 `row_policy`，用户属性是否包含允许值

### 本机 health 正常，其他机器访问失败

这通常是防火墙、端口映射、反向代理或内网策略问题。先在服务器本机验证：

```bash
curl http://127.0.0.1:8080/health
```

再从客户端验证：

```bash
curl http://SERVER_HOST:8080/health
```
