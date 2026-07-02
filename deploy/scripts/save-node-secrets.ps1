# 保存节点密钥到 deploy/env/node.local.env（gitignore）
# 用法：
#   .\deploy\scripts\save-node-secrets.ps1 -Token "从服务器 production.env 复制的值"
#   .\deploy\scripts\save-node-secrets.ps1 -Token "..." -NodeUrl "https://node.novapanda.io"

param(
    [Parameter(Mandatory = $true)]
    [string]$Token,
    [string]$NodeUrl = "https://node.novapanda.io"
)

$ErrorActionPreference = "Stop"
$OutFile = Join-Path (Split-Path $PSScriptRoot -Parent) "env\node.local.env"

@"
# NovaPanda node secrets — local only, do not commit
NOVAPANDA_NODE_URL=$NodeUrl
NOVAPANDA_ADMIN_TOKEN=$Token
"@ | Set-Content -Path $OutFile -Encoding utf8NoBOM

Write-Host "Saved to $OutFile"
Write-Host "Run: `$env:RUN_TS_LIFECYCLE='1'; .\deploy\scripts\smoke.ps1"
