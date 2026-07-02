# Mock 节点线上/Staging 冒烟（Windows PowerShell）
#
#   $env:TROODON_NODE_URL = "https://node.example.com"
#   $env:TROODON_ADMIN_TOKEN = "your-secret"
#   $env:RUN_TS_LIFECYCLE = "1"   # 可选
#   .\deploy\scripts\smoke.ps1

$ErrorActionPreference = "Stop"

$BaseUrl = $env:TROODON_NODE_URL
if (-not $BaseUrl) { throw "set TROODON_NODE_URL e.g. https://node.example.com" }
$AdminToken = $env:TROODON_ADMIN_TOKEN
if (-not $AdminToken) { throw "set TROODON_ADMIN_TOKEN" }
$RunTs = if ($env:RUN_TS_LIFECYCLE -eq "1") { $true } else { $false }

$BaseUrl = $BaseUrl.TrimEnd("/")

function Fail($msg) {
    Write-Error "SMOKE FAIL: $msg"
    exit 1
}

function Get-Json($Uri) {
    try {
        return Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 30
    } catch {
        Fail "$Uri -> $($_.Exception.Message)"
    }
}

Write-Host "== [1/6] GET /health =="
$h = Get-Json "$BaseUrl/health"
if ($h.status -ne "ok") { Fail "health status not ok: $($h | ConvertTo-Json -Compress)" }
Write-Host "OK"

Write-Host "== [2/6] GET /.well-known/troodon.json =="
$m = Get-Json "$BaseUrl/.well-known/troodon.json"
if (-not $m.protocol) { Fail "manifest missing protocol" }
Write-Host "OK"

Write-Host "== [3/6] GET /registry/rules =="
$rules = Get-Json "$BaseUrl/registry/rules"
$rulesJson = $rules | ConvertTo-Json -Depth 10 -Compress
if ($rulesJson -notmatch "R-extract-invoice-v1") { Fail "R-extract-invoice-v1 not in registry" }
Write-Host "OK"

Write-Host "== [4/6] POST /admin/sweep without token (expect 401) =="
try {
    Invoke-WebRequest -Uri "$BaseUrl/admin/sweep" -Method Post -TimeoutSec 30 | Out-Null
    Fail "expected 401 without token"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 401) {
        Fail "expected 401, got $($_.Exception.Response.StatusCode.value__)"
    }
}
Write-Host "OK (401)"

Write-Host "== [5/6] POST /admin/sweep with token =="
$headers = @{ "X-Admin-Token" = $AdminToken }
try {
    $sweep = Invoke-RestMethod -Uri "$BaseUrl/admin/sweep" -Method Post -Headers $headers -TimeoutSec 30
} catch {
    Fail "authorized sweep failed: $($_.Exception.Message)"
}
if ($null -eq $sweep.expired) { Fail "sweep response missing expired" }
Write-Host "OK"

if ($RunTs) {
    Write-Host "== [6/6] TS SDK lifecycle (auth) =="
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $TsDir = Join-Path $RepoRoot "sdk\typescript"
    if (-not (Test-Path $TsDir)) { Fail "sdk/typescript not found at $TsDir" }
    Push-Location $TsDir
    try {
        npm run build --silent
        if ($LASTEXITCODE -ne 0) { Fail "npm run build failed" }
        node test/plugfest_lifecycle.mjs $BaseUrl
        if ($LASTEXITCODE -ne 0) { Fail "plugfest_lifecycle.mjs failed" }
    } finally {
        Pop-Location
    }
    Write-Host "OK"
} else {
    Write-Host "== [6/6] TS lifecycle skipped (set RUN_TS_LIFECYCLE=1 to enable) =="
}

Write-Host ""
Write-Host "SMOKE OK: $BaseUrl"
