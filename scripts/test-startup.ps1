# Execute deployment configuration logic on Windows with Docker/network/browser mocks.
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$taskDir=Join-Path ([System.IO.Path]::GetTempPath()) ('zhixue-check-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $taskDir 'scripts') -Force | Out-Null
Copy-Item (Join-Path $taskRoot '.env.example') (Join-Path $taskDir '.env.example')
Copy-Item (Join-Path $PSScriptRoot 'start.ps1') (Join-Path $taskDir 'scripts/start.ps1')
Copy-Item (Join-Path $PSScriptRoot 'setup-models.ps1') (Join-Path $taskDir 'scripts/setup-models.ps1')
$global:taskDockerCalls=[System.Collections.Generic.List[string]]::new()
function global:docker {
    $global:taskDockerCalls.Add(($args -join ' '))
    $global:LASTEXITCODE=0
}
function global:Invoke-RestMethod { param([string]$Uri,[int]$TimeoutSec) return @{status='ok'} }
function global:Start-Process { param([string]$FilePath) }
try {
    foreach($file in @('start.ps1','setup-models.ps1')) {
        $tokens=$null;$parseErrors=$null
        [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $taskDir "scripts/$file"),[ref]$tokens,[ref]$parseErrors) | Out-Null
        if($parseErrors.Count -gt 0) {throw "PowerShell parse failed: $file"}
    }
    & (Join-Path $taskDir 'scripts/setup-models.ps1')
    $config=Get-Content (Join-Path $taskDir '.env')
    foreach($line in @('CHAT_MODEL=qwen3:0.6b','EMBEDDING_MODEL=qwen3-embedding:0.6b','OLLAMA_URL=http://ollama:11434')) {
        if(@($config | Where-Object {$_ -eq $line}).Count -ne 1) {throw "Configuration failed: $line"}
    }
    if(-not (Test-Path (Join-Path $taskDir '.env.before-models'))) {throw 'Configuration backup missing'}
    if(-not $global:taskDockerCalls.Contains('compose exec -T ollama ollama pull qwen3:0.6b')) {throw 'Chat model was not pulled'}
    if(-not $global:taskDockerCalls.Contains('compose up --build -d')) {throw 'Application startup was not called'}
    & (Join-Path $taskDir 'scripts/setup-models.ps1') -ChatModel 'qwen3:1.7b'
    $config=Get-Content (Join-Path $taskDir '.env')
    if(@($config | Where-Object {$_ -match '^CHAT_MODEL='}).Count -ne 1) {throw 'Duplicate model configuration'}
    if(-not ($config -contains 'CHAT_MODEL=qwen3:1.7b')) {throw 'Model replacement failed'}
    Write-Host 'PowerShell syntax, configuration backup, model replacement and startup logic passed. Docker is mocked; this is not a Windows container deployment test.'
} finally {
    Set-Location $taskRoot
    $resolvedTaskDir = [System.IO.Path]::GetFullPath($taskDir)
    $resolvedTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (-not $resolvedTaskDir.StartsWith($resolvedTempRoot,[System.StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolvedTaskDir -Leaf) -notmatch '^zhixue-check-[0-9a-f]{32}$') { throw 'Unsafe temporary cleanup path' }
    Remove-Item -LiteralPath $resolvedTaskDir -Recurse -Force
    Remove-Item function:\docker,function:\Invoke-RestMethod,function:\Start-Process
}
