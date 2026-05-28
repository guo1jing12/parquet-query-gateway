param(
    [Parameter(Mandatory = $true)]
    [string]$GatewayUrl,
    [string]$Token = ""
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd is required to install OpenCLI"
}

if (-not (Get-Command opencli.cmd -ErrorAction SilentlyContinue)) {
    npm.cmd install -g @jackwener/opencli
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install @jackwener/opencli"
    }
}

$pluginPath = "file:///$((Get-Location).Path.Replace('\', '/'))"
opencli.cmd plugin install $pluginPath
if ($LASTEXITCODE -ne 0) {
    Write-Output "Plugin install did not complete; trying update instead."
    opencli.cmd plugin update parquet
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install or update parquet OpenCLI plugin"
    }
}

Write-Output ""
Write-Output "Client installation complete."
Write-Output ""
Write-Output "Set these in PowerShell:"
Write-Output ('  $env:PARQUET_GATEWAY_URL = "' + $GatewayUrl + '"')
if ($Token) {
    Write-Output ('  $env:PARQUET_GATEWAY_TOKEN = "' + $Token + '"')
} else {
    Write-Output "  # No token was provided. The first authenticated command will open Feishu login."
    Write-Output "  # You can also run: opencli parquet login"
}
Write-Output ""
Write-Output "Verify:"
Write-Output "  opencli parquet smoke-test"
Write-Output "  opencli parquet datasets"
