param([string]$ChatModel='qwen3:0.6b',[string]$EmbeddingModel='qwen3-embedding:0.6b')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
docker compose --profile models up -d ollama
if ($LASTEXITCODE -ne 0) { throw 'Model container failed to start. Check Docker Desktop.' }
$ready=$false
for ($i=0;$i -lt 30;$i++) {
    docker compose exec -T ollama ollama list *> $null
    if ($LASTEXITCODE -eq 0) {$ready=$true;break}
    Start-Sleep -Seconds 2
}
if (-not $ready) {throw 'Ollama is not ready. Check container logs.'}
foreach ($model in @($ChatModel,$EmbeddingModel)) {
    if ($model -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$') {throw 'Invalid model name.'}
    docker compose exec -T ollama ollama pull $model
    if ($LASTEXITCODE -ne 0) {throw "Download failed: $model. Retry to resume the download."}
}
Copy-Item '.env' '.env.before-models' -Force
$lines=@(Get-Content '.env' | Where-Object {$_ -notmatch '^(CHAT_MODEL|EMBEDDING_MODEL|OLLAMA_URL)='})
$lines+=@("CHAT_MODEL=$ChatModel","EMBEDDING_MODEL=$EmbeddingModel",'OLLAMA_URL=http://ollama:11434')
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) '.env'),$lines,(New-Object System.Text.UTF8Encoding($false)))
& "$PSScriptRoot/start.ps1"
