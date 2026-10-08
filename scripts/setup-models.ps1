param([string]$ChatModel='qwen3:0.6b',[string]$EmbeddingModel='qwen3-embedding:0.6b')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
docker compose --profile models up -d ollama
if ($LASTEXITCODE -ne 0) { throw '模型容器启动失败，请检查 Docker Desktop。' }
$ready=$false
for ($i=0;$i -lt 30;$i++) {
    docker compose exec -T ollama ollama list *> $null
    if ($LASTEXITCODE -eq 0) {$ready=$true;break}
    Start-Sleep -Seconds 2
}
if (-not $ready) {throw 'Ollama 未就绪，请检查容器日志。'}
foreach ($model in @($ChatModel,$EmbeddingModel)) {
    if ($model -notmatch '^[a-zA-Z0-9._:/-]+$') {throw '模型名称格式无效。'}
    docker compose exec -T ollama ollama pull $model
    if ($LASTEXITCODE -ne 0) {throw "下载 $model 失败。可以重新执行，已下载内容会保留。"}
}
Copy-Item '.env' '.env.before-models' -Force
$lines=Get-Content '.env' | Where-Object {$_ -notmatch '^(CHAT_MODEL|EMBEDDING_MODEL|OLLAMA_URL)='}
$lines+=@("CHAT_MODEL=$ChatModel","EMBEDDING_MODEL=$EmbeddingModel",'OLLAMA_URL=http://ollama:11434')
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) '.env'),$lines,(New-Object System.Text.UTF8Encoding($false)))
& "$PSScriptRoot/start.ps1"
