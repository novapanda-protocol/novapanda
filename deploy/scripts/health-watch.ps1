# 连续 health 观察（P2 门禁：7 天无失败）
#
#   .\deploy\scripts\health-watch.ps1
#   .\deploy\scripts\health-watch.ps1 -Url https://node.novapanda.io/health -Days 7

param(
    [string]$Url = "https://node.novapanda.io/health",
    [int]$Days = 7
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSCommandPath
if (-not $ScriptDir) { $ScriptDir = $PSScriptRoot }
$LogDir = Join-Path (Split-Path $ScriptDir -Parent) "logs"
$LogFile = Join-Path $LogDir "health-watch.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
try {
    $resp = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 30
    if ($resp.status -ne "ok") {
        throw "status=$($resp.status)"
    }
    $line = "$ts OK $Url"
    $status = 0
} catch {
    $line = "$ts FAIL $Url :: $($_.Exception.Message)"
    $status = 1
}

Add-Content -Path $LogFile -Value $line -Encoding utf8
Write-Host $line

if (Test-Path $LogFile) {
    $cutoff = (Get-Date).AddDays(-$Days)
    $recent = Get-Content $LogFile | Where-Object {
        if ($_ -match '^(\d{4}-\d{2}-\d{2})') {
            try { [datetime]$matches[1] -ge $cutoff.Date } catch { $false }
        } else { $false }
    }
    $oks = ($recent | Where-Object { $_ -match ' OK ' }).Count
    $fails = ($recent | Where-Object { $_ -match ' FAIL ' }).Count
    Write-Host ""
    Write-Host "Last $Days days: OK=$oks FAIL=$fails (target: 7 consecutive days, 0 FAIL)"
    if ($oks -ge $Days -and $fails -eq 0) {
        Write-Host "P2 health gate: PASSED"
    } else {
        Write-Host "P2 health gate: in progress (run daily)"
    }
}

exit $status
