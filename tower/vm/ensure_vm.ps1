<#
.SYNOPSIS  Starts the VirtualBox VM and watches it until its SSH server really answers.
.DESCRIPTION
  Used by the "Linux VM" buttons of RemoteHub.
   - already running and healthy: does nothing;
   - started by this script but frozen at boot (happens with VirtualBox in NEM mode): reset, up to -MaxTries times;
   - already running before the call (someone is using it): only waits, NEVER restarts it.
  Log: %ProgramData%\RemoteHub\logs\vm-ensure.log
#>
param(
  [string]$VmName = 'RemoteHub-Linux',
  [int]$SshPort = 2223,              # host port forwarded to the guest's SSH (127.0.0.1 only)
  [int]$DeadlineSeconds = 150,
  [int]$MaxTries = 3
)

$vb = if ($env:VBOX_MSI_INSTALL_PATH) { Join-Path $env:VBOX_MSI_INSTALL_PATH 'VBoxManage.exe' } else { 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe' }
if (-not (Test-Path $vb)) { Write-Error "VBoxManage not found ($vb): is VirtualBox installed?"; exit 2 }
$logDir = Join-Path $env:ProgramData 'RemoteHub\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'vm-ensure.log'
function L($m) { "$(Get-Date -Format 'HH:mm:ss') $m" | Out-File $log -Append -Encoding utf8 }

function State {
  $m = (& $vb showvminfo $VmName --machinereadable 2>$null | Select-String '^VMState="(.+)"')
  if ($m) { $m.Matches[0].Groups[1].Value } else { 'unknown' }
}
function SshReady {
  try {
    $c = New-Object Net.Sockets.TcpClient
    $a = $c.BeginConnect('127.0.0.1', $SshPort, $null, $null)
    if (-not $a.AsyncWaitHandle.WaitOne(3000)) { $c.Close(); return $false }
    $c.EndConnect($a); $s = $c.GetStream(); $s.ReadTimeout = 3000
    $b = New-Object byte[] 8; $r = $s.Read($b, 0, 8); $c.Close()
    return ($r -ge 4 -and [Text.Encoding]::ASCII.GetString($b, 0, $r).StartsWith('SSH-'))
  } catch { return $false }
}

$state = State
if ($state -eq 'unknown') { L "VM '$VmName' not found"; Write-Error "VM '$VmName' not found."; exit 3 }
$weStarted = $false
if ($state -eq 'paused') { L 'VM paused: resuming'; & $vb controlvm $VmName resume | Out-Null }
elseif ($state -ne 'running') { L "VM $state : starting"; & $vb startvm $VmName --type headless | Out-Null; $weStarted = $true }
else { L 'VM already running' }

for ($try = 1; $try -le $MaxTries; $try++) {
  $deadline = (Get-Date).AddSeconds($DeadlineSeconds)
  while ((Get-Date) -lt $deadline) {
    if (SshReady) { L "SSH ready (try $try)"; exit 0 }
    Start-Sleep 4
  }
  if (-not $weStarted) { L "SSH not ready after $DeadlineSeconds s, but this script did not start the VM: no reset"; continue }
  L "no SSH after $DeadlineSeconds s (try $try/$MaxTries): resetting the VM"
  & $vb controlvm $VmName reset | Out-Null
}
L "FAILED: the VM does not answer after $MaxTries try(ies)"
exit 1
