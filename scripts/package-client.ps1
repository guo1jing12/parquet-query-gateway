param(
    [string]$OutputDir = "output",
    [string]$GatewayUrl = "http://192.168.58.184:8080"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$packageName = "parquet-query-gateway-client"
$staging = Join-Path $root "$OutputDir\$packageName"
$zipPath = Join-Path $root "$OutputDir\$packageName.zip"

if (Test-Path $staging) {
    Remove-Item -Recurse -Force $staging
}
New-Item -ItemType Directory -Force $staging | Out-Null
New-Item -ItemType Directory -Force (Join-Path $staging "scripts") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $staging "docs") | Out-Null

$files = @(
    "opencli-plugin.json",
    "auth-flow.js",
    "gateway-client.js",
    "datasets.js",
    "schema.js",
    "query.js",
    "audit.js",
    "login.js",
    "smoke-test.js",
    "scripts/client-install.ps1",
    "scripts/client-install.sh",
    "docs/client-installation-guide.md"
)

foreach ($file in $files) {
    $source = Join-Path $root $file
    $target = Join-Path $staging $file
    Copy-Item -LiteralPath $source -Destination $target
}

$readme = @(
    "# Parquet Query Gateway Client",
    "",
    "Gateway URL:",
    "",
    $GatewayUrl,
    "",
    "Windows PowerShell install:",
    "",
    ".\scripts\client-install.ps1 -GatewayUrl ""$GatewayUrl""",
    "",
    "Verify after install:",
    "",
    "opencli.cmd parquet smoke-test",
    "opencli.cmd parquet datasets",
    "",
    "See docs/client-installation-guide.md."
) -join "`r`n"

$readme | Set-Content -Encoding UTF8 (Join-Path $staging "README.md")

if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath

Write-Output "Created $zipPath"
