# Parquet 查询网关客户端安装指南

安装前准备好：

- Git
- Node.js/npm
- 网关地址：`http://192.168.58.184:8080`
- token，或飞书登录方式

## 给 AI Agent 的客户端安装任务

把下面这段发给 AI Agent：

```text
请帮我安装 Parquet Query Gateway 客户端。

注意：只安装客户端，不要启动 parquet-gateway，不要创建 production.yml，不要运行 init-config。

安装目标：
- 仓库：https://github.com/guo1jing12/parquet-query-gateway.git
- 网关地址：http://192.168.58.184:8080
- 认证方式：token，或飞书登录

请按顺序执行：
1. 检查 Git、Node.js/npm 是否可用。
2. 克隆仓库并进入项目目录。
3. 运行 scripts/client-install.sh 或 scripts/client-install.ps1。
4. 设置 PARQUET_GATEWAY_URL。
5. 设置 PARQUET_GATEWAY_TOKEN，或按飞书方式登录。
6. 运行 opencli parquet smoke-test。
7. 运行 opencli parquet datasets。

如果无法访问网关地址，请暂停并把网络错误告诉我。
```

## 安装 OpenCLI 客户端

Linux/macOS：

```bash
git clone https://github.com/guo1jing12/parquet-query-gateway.git
cd parquet-query-gateway
bash scripts/client-install.sh --gateway-url http://192.168.58.184:8080
```

Windows PowerShell：

```powershell
git clone https://github.com/guo1jing12/parquet-query-gateway.git
cd parquet-query-gateway
.\scripts\client-install.ps1 -GatewayUrl "http://192.168.58.184:8080"
```

如果已有 token，也可以一起传入：

```bash
bash scripts/client-install.sh --gateway-url http://192.168.58.184:8080 --token <your_token>
```

Windows PowerShell：

```powershell
.\scripts\client-install.ps1 -GatewayUrl "http://192.168.58.184:8080" -Token "<your_token>"
```

脚本只会：

1. 检查 npm
2. 安装 `@jackwener/opencli`
3. 注册当前仓库的 `parquet` OpenCLI 插件
4. 输出环境变量设置方式

脚本不会启动任何 HTTP 服务，不会创建服务端配置，不会扫描 Parquet 文件。

## 配置网关地址和 token

Linux/macOS：

```bash
export PARQUET_GATEWAY_URL=http://192.168.58.184:8080
export PARQUET_GATEWAY_TOKEN=<your_token>
```

Windows PowerShell：

```powershell
$env:PARQUET_GATEWAY_URL = "http://192.168.58.184:8080"
$env:PARQUET_GATEWAY_TOKEN = "<your_token>"
```

如果使用飞书登录，则不需要长期保存静态 token。设置网关地址和飞书授权 URL 后登录：

```bash
export PARQUET_GATEWAY_URL=http://192.168.58.184:8080
export PARQUET_FEISHU_AUTH_URL="https://open.feishu.cn/open-apis/authen/v1/authorize?..."
opencli parquet login
```

登录成功后，命令会返回 `PARQUET_GATEWAY_TOKEN`，也会保存到：

```text
~/.parquet-gateway/token.json
```

## 验证

```bash
opencli parquet smoke-test
opencli parquet datasets
```

查看某个 dataset 字段：

```bash
opencli parquet schema <dataset_id>
```

查询前 5 行：

```bash
opencli parquet query <dataset_id> --limit 5
```

聚合示例：

```bash
opencli parquet query <dataset_id> \
  --group-by channel \
  --aggregate sum:sales_amount:total_sales_amount,count::row_count \
  --limit 100
```

PowerShell 中 `>` 可能会被当作重定向。如果要使用 `amount>=100` 这类过滤条件，建议在 CMD/bash 中执行。

## 更新客户端

```bash
cd parquet-query-gateway
git pull
opencli plugin update parquet
```

如果更新失败：

```bash
opencli plugin uninstall parquet
opencli plugin install "file://$PWD"
```

Windows PowerShell：

```powershell
opencli plugin uninstall parquet
opencli plugin install "file:///$((Get-Location).Path.Replace('\', '/'))"
```

## 常见问题

### smoke-test 返回 401

token 不正确或已过期。请重新设置 `PARQUET_GATEWAY_TOKEN`，或重新执行 `opencli parquet login`。

### 连接网关失败

先确认：

```bash
curl http://192.168.58.184:8080/health
```

如果本机无法访问，通常是内网、VPN、防火墙或网关地址问题。不要通过启动本地服务来解决客户端连接失败。
如果网络管理员提供了主机名，也可以把 `192.168.58.184` 替换成对应主机名，例如 `intranet-184`。

### 看不到某个 dataset 或字段

这是权限配置问题。确认你的账号或 token 是否允许访问该 dataset 或字段。

### 需要卸载

```bash
opencli plugin uninstall parquet
```

如需删除本地仓库：

```bash
rm -rf parquet-query-gateway
```
