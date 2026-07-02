# 上云前本地门禁（Windows）
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $RepoRoot

$Py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

Write-Host "== pytest =="
& $Py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Host "== conformance C1-C7 =="
& $Py -m conformance.run
if ($LASTEXITCODE -ne 0) { throw "conformance failed" }

Write-Host "== plugfest =="
& $Py demo/plugfest.py
if ($LASTEXITCODE -ne 0) { throw "plugfest failed" }

Write-Host "== run_demo =="
& $Py demo/run_demo.py
if ($LASTEXITCODE -ne 0) { throw "run_demo failed" }

Write-Host ""
Write-Host "PRE-DEPLOY GATE OK"
