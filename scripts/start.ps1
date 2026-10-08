$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw '请先安装并启动 Docker Desktop，然后重新运行。' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker 尚未启动，请打开 Docker Desktop 等待运行。' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw '部署配置校验失败。' }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw '部署失败，请检查 docker compose logs。' }
$port = 8080
Get-Content '.env' | ForEach-Object { if ($_ -match '^WEB_PORT=(\d+)$') { $port = [int]$Matches[1] } }
$url = "http://localhost:$port"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try { $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 3; if ($health.status -eq 'ok') { $ready=$true; break } } catch {}
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw '服务未在两分钟内就绪，请执行 docker compose logs 查看原因。' }
Write-Host "智学已就绪：$url。首次使用请注册账号。"
Start-Process $url
