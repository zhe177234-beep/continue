$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install and start Docker Desktop, then retry.' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker is not running. Start Docker Desktop and wait for the engine.' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
# Docker build authentication needs the proxy in the current process.
if (-not $env:HTTPS_PROXY) {
    $systemProxy = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
    if ($systemProxy.ProxyEnable -eq 1 -and $systemProxy.ProxyServer -match '^[a-zA-Z0-9.-]+:\d+$') {
        $env:HTTPS_PROXY = "http://$($systemProxy.ProxyServer)"
        if (-not $env:HTTP_PROXY) { $env:HTTP_PROXY = $env:HTTPS_PROXY }
        if (-not $env:NO_PROXY) { $env:NO_PROXY = 'localhost,127.0.0.1' }
    }
}
# Container dependency downloads use Docker's own proxy, not Windows loopback.
if (-not $env:BUILD_HTTP_PROXY) {
    $buildProxy = [string](docker info --format '{{.HTTPProxy}}')
    if ($buildProxy -and $buildProxy.Trim()) {
        $env:BUILD_HTTP_PROXY = if ($buildProxy -match '^https?://') { $buildProxy.Trim() } else { 'http://' + $buildProxy.Trim() }
    }
}
if (-not $env:BUILD_HTTPS_PROXY) {
    $buildProxy = [string](docker info --format '{{.HTTPSProxy}}')
    if ($buildProxy -and $buildProxy.Trim()) {
        $env:BUILD_HTTPS_PROXY = if ($buildProxy -match '^https?://') { $buildProxy.Trim() } else { 'http://' + $buildProxy.Trim() }
    }
}
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration validation failed.' }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Deployment failed. Check docker compose logs.' }
$port = 8080
Get-Content '.env' | ForEach-Object { if ($_ -match '^WEB_PORT=(\d+)$') { $port = [int]$Matches[1] } }
$url = "http://localhost:$port"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try { $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 3; if ($health.status -eq 'ok') { $ready=$true; break } } catch {}
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'Service was not ready within two minutes. Check docker compose logs.' }
Write-Host "Ready: $url. Register an account on first use."
Start-Process $url
