# Current-user Task Scheduler job. No password is collected or stored.
[CmdletBinding()]
param(
    [ValidateSet('install','start','stop','restart','status','remove')][string]$Action = 'install',
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$DataDir
)
$ErrorActionPreference = 'Stop'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$name = 'NetTime-Controller-' + $identity.User.Value
$marker = 'NetTime home controller (loopback only)'
$existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -ne $marker) {
    throw 'A task with this name is not NetTime; refusing to change it.'
}
if ($Action -eq 'install') {
    if (!(Test-Path -LiteralPath (Join-Path $DataDir 'config.json'))) { throw 'Run setup first.' }
    # Windows filenames cannot contain quotes. Quotes protect spaces and non-ASCII paths.
    if ($DataDir.Contains('"') -or $PythonExe.Contains('"')) { throw 'Invalid path.' }
    if ($existing) { Stop-ScheduledTask -TaskName $name }
    $arguments = '-m nettime --data-dir "' + $DataDir.TrimEnd('\') + '" serve'
    $job = New-ScheduledTaskAction -Execute $PythonExe -Argument $arguments -WorkingDirectory $PSScriptRoot
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
    $principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $name -Description $marker -Action $job -Trigger $trigger `
        -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName $name
    Write-Output 'Installed for this account at sign-in. Keep the account signed in and the computer awake.'
} elseif (!$existing) {
    throw 'NetTime background task is not installed.'
} elseif ($Action -eq 'remove') {
    Stop-ScheduledTask -TaskName $name
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
} elseif ($Action -eq 'stop') {
    Stop-ScheduledTask -TaskName $name
} elseif ($Action -eq 'start') {
    Start-ScheduledTask -TaskName $name
} elseif ($Action -eq 'restart') {
    Stop-ScheduledTask -TaskName $name
    Start-ScheduledTask -TaskName $name
} else {
    $existing | Select-Object TaskName, State
    Get-ScheduledTaskInfo -TaskName $name | Select-Object LastRunTime, LastTaskResult, NextRunTime
}
