# Parquet 查询网关客户端安装指南

安装前准备好：

- Node.js/npm
- 网关地址：`http://192.168.58.184:8080`
- token，或飞书登录方式

如果没有提供 token，客户端会通过网关获取飞书授权链接并打开浏览器登录。登录成功后 token 会保存到 `~/.parquet-gateway/token.json`，后续命令会自动读取。

## 给 AI Agent 的客户端安装任务

把下面这段发给 AI Agent：

```text
请帮我安装 Parquet Query Gateway 客户端。

注意：只安装客户端，不要启动 parquet-gateway，不要创建 production.yml，不要运行 init-config。

安装目标：
- 客户端安装包：http://192.168.58.184:8080/downloads/parquet-query-gateway-client.zip
- 网关地址：http://192.168.58.184:8080
- 认证方式：token，或飞书登录

请按顺序执行：
1. 检查 Node.js/npm 是否可用。
2. 下载客户端安装包并解压。
3. 运行 scripts/client-install.ps1。
4. 设置 PARQUET_GATEWAY_URL。
5. 如果提供了 PARQUET_GATEWAY_TOKEN，则设置它；如果没有 token，运行 opencli parquet login，或直接运行下一步让命令自动打开飞书登录。
6. 运行 opencli parquet smoke-test。
7. 运行 opencli parquet datasets。

如果无法访问网关地址，请暂停并把网络错误告诉我。
如果网关没有开启飞书登录，且也没有提供 token，请暂停并把认证错误告诉我。
```

## 安装 OpenCLI 客户端

Windows PowerShell：

```powershell
Invoke-WebRequest "http://192.168.58.184:8080/downloads/parquet-query-gateway-client.zip" -OutFile "$env:TEMP\parquet-client.zip"
Expand-Archive "$env:TEMP\parquet-client.zip" "$env:TEMP\parquet-client" -Force
cd "$env:TEMP\parquet-client"
powershell -ExecutionPolicy Bypass -File .\scripts\client-install.ps1 -GatewayUrl "http://192.168.58.184:8080"
```

如果已有 token，也可以一起传入：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\client-install.ps1 -GatewayUrl "http://192.168.58.184:8080" -Token "<your_token>"
```

如果 PowerShell 提示无法运行脚本，确认使用的是上面的 `-ExecutionPolicy Bypass` 命令。

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

如果使用飞书登录，则不需要长期保存静态 token。设置网关地址后登录：

```bash
export PARQUET_GATEWAY_URL=http://192.168.58.184:8080
opencli parquet login
```

如果网关不能自动提供授权链接，也可以手动设置 `PARQUET_FEISHU_AUTH_URL` 后再登录。

登录成功后，命令会返回 `PARQUET_GATEWAY_TOKEN`，也会保存到：

```text
~/.parquet-gateway/token.json
```

`opencli parquet smoke-test`、`opencli parquet datasets` 等命令会优先使用 `PARQUET_GATEWAY_TOKEN`，其次读取上面的本地 token 文件；如果两者都没有，会自动打开飞书登录。

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

```powershell
Invoke-WebRequest "http://192.168.58.184:8080/downloads/parquet-query-gateway-client.zip" -OutFile "$env:TEMP\parquet-client.zip"
Expand-Archive "$env:TEMP\parquet-client.zip" "$env:TEMP\parquet-client" -Force
cd "$env:TEMP\parquet-client"
opencli.cmd plugin update parquet
```

如果更新失败：

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

```powershell
Remove-Item "$env:TEMP\parquet-client" -Recurse -Force
```
