# 注册 Windows 计划任务：每天自动跑 health-watch（无需手敲命令）
# 用法（PowerShell 管理员）：
#   .\deploy\scripts\install-health-watch-task.ps1
# 删除：
#   Unregister-ScheduledTask -TaskName NovaPanda-HealthWatch -Confirm:$false

$ErrorActionPreference = "Stop"
$TaskName = "NovaPanda-HealthWatch"
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Script = Join-Path $RepoRoot "deploy\scripts\health-watch.ps1"

if (-not (Test-Path $Script)) {
    throw "not found: $Script"
}

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""

$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00"

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "NovaPanda node daily health check (P2 gate)" `
    -Force | Out-Null

Write-Host "Registered: $TaskName (daily 09:00)"
Write-Host "Log: $RepoRoot\deploy\logs\health-watch.log"
Write-Host "Test now: .\deploy\scripts\health-watch.ps1"
