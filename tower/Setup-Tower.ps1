<#
.SYNOPSIS
  Prepares a Windows PC ("the tower") to be controlled by RemoteHub-AI: SSH server, key login,
  optional hardening, optional firewall restriction, Wake-on-LAN network card settings.

.DESCRIPTION
  Run in an ELEVATED PowerShell on the tower. Every step is idempotent and can be previewed with -DryRun.
  Nothing here opens a port to the Internet: SSH is meant to be reached through Tailscale (or your LAN).

  Fr : prepare la tour Windows pour RemoteHub-AI (serveur SSH, connexion par cle, durcissement,
  pare-feu, Wake-on-LAN). Lancez-le dans un PowerShell ADMINISTRATEUR ; -DryRun pour simuler.

.PARAMETER User
  Windows account that will log in over SSH (default: the current user).
.PARAMETER PublicKey
  Your laptop's PUBLIC key: the text ("ssh-ed25519 AAAA...") or a path to the .pub file.
.PARAMETER DisablePasswordAuth
  Turn password login off in sshd (key only). Refused unless a key is installed. TEST KEY LOGIN FIRST.
.PARAMETER RestrictFirewall
  Allow inbound SSH only from Tailscale (100.64.0.0/10) [+ -LanSubnet]; disable the other inbound rules on port 22.
.PARAMETER LanSubnet
  Optional LAN CIDR also allowed to reach SSH (e.g. 192.168.1.0/24). Requires -RestrictFirewall.
.PARAMETER WolAdapter
  Name of the Ethernet adapter to configure for Wake-on-LAN (default: first physical adapter that is Up).
.PARAMETER DryRun
  Show what would change, change nothing.

.EXAMPLE
  .\Setup-Tower.ps1 -DryRun
.EXAMPLE
  .\Setup-Tower.ps1 -PublicKey "$HOME\laptop_id_ed25519.pub" -RestrictFirewall
.EXAMPLE
  .\Setup-Tower.ps1 -DisablePasswordAuth     # only after you verified that key login works
#>
[CmdletBinding()]
param(
  [string]$User = $env:USERNAME,
  [string]$PublicKey,
  [switch]$DisablePasswordAuth,
  [switch]$RestrictFirewall,
  [string]$LanSubnet = '',
  [string]$WolAdapter = '',
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$stateDir = Join-Path $env:ProgramData 'RemoteHub'
$stamp    = Get-Date -Format 'yyyyMMdd-HHmmss'

function Step([string]$Title) { Write-Host "`n== $Title" -ForegroundColor Cyan }
function Info([string]$Msg)   { Write-Host "   $Msg" }
function Warn([string]$Msg)   { Write-Host "   ! $Msg" -ForegroundColor Yellow }
function Apply([string]$Desc, [scriptblock]$Do) {
  if ($DryRun) { Write-Host "   [dry-run] $Desc" -ForegroundColor DarkGray; return }
  Write-Host "   [apply]   $Desc"
  & $Do
}

# ---------------------------------------------------------------- checks
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Run this script in an elevated (Administrator) PowerShell.'
}
if ($LanSubnet -and -not $RestrictFirewall) { throw '-LanSubnet only makes sense together with -RestrictFirewall.' }
if ($DryRun) { Write-Host 'DRY RUN: nothing will be changed.' -ForegroundColor Yellow }
if (-not (Test-Path $stateDir)) { Apply "create $stateDir" { New-Item -ItemType Directory -Path $stateDir | Out-Null } }

# ---------------------------------------------------------------- 1. OpenSSH server
Step '1/5  OpenSSH server'
$cap = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' | Select-Object -First 1
if ($cap.State -ne 'Installed') {
  Apply 'install the OpenSSH.Server Windows capability' { Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
} else { Info 'OpenSSH server already installed' }
$sshd = Get-Service sshd -ErrorAction SilentlyContinue
if ($sshd) {
  if ($sshd.StartType -ne 'Automatic') { Apply 'set the sshd service to start automatically' { Set-Service sshd -StartupType Automatic } }
  if ($sshd.Status -ne 'Running')      { Apply 'start the sshd service' { Start-Service sshd } }
} elseif (-not $DryRun) { throw 'sshd service not found after installation.' }

# ---------------------------------------------------------------- 2. public key
Step "2/5  Public key for '$User'"
$keyInstalled = $false
$isAdminUser = $false
try {
  $isAdminUser = [bool](Get-LocalGroupMember -Group 'Administrators' -ErrorAction Stop |
    Where-Object { $_.Name -like "*\$User" })
} catch { Warn "could not read the Administrators group: $($_.Exception.Message)" }

if ($isAdminUser) {
  # Windows OpenSSH reads administrators_authorized_keys for members of the Administrators group.
  $authFile = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
  $grants   = @('Administrators:F', 'SYSTEM:F')
} else {
  $home_    = (Get-CimInstance Win32_UserProfile | Where-Object { $_.LocalPath -like "*\$User" } | Select-Object -First 1).LocalPath
  if (-not $home_) { $home_ = Join-Path 'C:\Users' $User }
  $authFile = Join-Path $home_ '.ssh\authorized_keys'
  $grants   = @("${User}:F", 'Administrators:F', 'SYSTEM:F')
}
Info "key file: $authFile  (administrator account: $isAdminUser)"

if ($PublicKey) {
  $keyText = if (Test-Path -LiteralPath $PublicKey) { (Get-Content -LiteralPath $PublicKey -Raw).Trim() } else { $PublicKey.Trim() }
  if ($keyText -notmatch '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+|sk-ssh-ed25519@openssh\.com)\s+\S+') {
    throw 'That does not look like a PUBLIC key (expected "ssh-ed25519 AAAA..."). Never pass a private key.'
  }
  $existing = if (Test-Path -LiteralPath $authFile) { Get-Content -LiteralPath $authFile } else { @() }
  if ($existing -contains $keyText) { Info 'key already installed'; $keyInstalled = $true }
  else {
    Apply "append the public key to $authFile" {
      New-Item -ItemType Directory -Force -Path (Split-Path $authFile) | Out-Null
      Add-Content -LiteralPath $authFile -Value $keyText -Encoding ascii
    }
    $keyInstalled = $true
  }
  Apply 'restrict permissions of the key file' {
    $args_ = @($authFile, '/inheritance:r') + ($grants | ForEach-Object { '/grant'; $_ })
    & icacls.exe @args_ | Out-Null
  }
} elseif ((Test-Path -LiteralPath $authFile) -and (Get-Content -LiteralPath $authFile -ErrorAction SilentlyContinue)) {
  Info 'no -PublicKey given, but a key file already exists'
  $keyInstalled = $true
} else {
  Warn 'no public key installed yet: re-run with -PublicKey <laptop key>. Password login stays enabled meanwhile.'
}

# ---------------------------------------------------------------- 3. sshd_config
Step '3/5  sshd configuration'
$cfgPath = Join-Path $env:ProgramData 'ssh\sshd_config'
if (-not (Test-Path $cfgPath)) { Warn "$cfgPath not found (start sshd once, then re-run)"; }
else {
  if ($DisablePasswordAuth -and -not $keyInstalled) { throw 'Refusing -DisablePasswordAuth: no key is installed, you would lock yourself out.' }
  $lines = @('MaxAuthTries 3', 'LoginGraceTime 30', 'PubkeyAuthentication yes', 'AllowTcpForwarding yes')
  if ($DisablePasswordAuth) { $lines += @('PasswordAuthentication no', 'KbdInteractiveAuthentication no') }
  $block = "# BEGIN RemoteHub`r`n" + ($lines -join "`r`n") + "`r`n# END RemoteHub`r`n"
  $current = Get-Content -LiteralPath $cfgPath -Raw
  $clean = [regex]::Replace($current, '(?s)# BEGIN RemoteHub.*?# END RemoteHub\r?\n', '')
  $new = $block + $clean   # first value wins in sshd_config: our block goes on top
  if ($new -eq $current) { Info 'sshd_config already up to date' }
  else {
    $backup = "$cfgPath.remotehub-$stamp.bak"
    Apply "back up sshd_config to $backup and apply: $($lines -join '; ')" {
      Copy-Item -LiteralPath $cfgPath -Destination $backup
      Set-Content -LiteralPath $cfgPath -Value $new -Encoding ascii -NoNewline
      $sshdExe = Join-Path $env:SystemRoot 'System32\OpenSSH\sshd.exe'
      & $sshdExe -t 2>&1 | Out-Null
      if ($LASTEXITCODE -ne 0) {
        Copy-Item -LiteralPath $backup -Destination $cfgPath -Force
        throw 'sshd rejected the new configuration: the backup was restored.'
      }
      Restart-Service sshd
    }
  }
  if (-not $DisablePasswordAuth) { Warn 'password login is still allowed. After testing key login, re-run with -DisablePasswordAuth.' }
}

# ---------------------------------------------------------------- 4. firewall
Step '4/5  Firewall'
$ruleName = 'RemoteHub SSH'
if ($RestrictFirewall) {
  $remote = @('100.64.0.0/10') + $(if ($LanSubnet) { $LanSubnet })
  Apply "allow inbound TCP 22 only from: $($remote -join ', ')" {
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22 `
      -RemoteAddress $remote -Profile Any | Out-Null
  }
  $others = Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -ne $ruleName } |
    Where-Object { ($_ | Get-NetFirewallPortFilter).LocalPort -contains '22' }
  if ($others) {
    $names = $others.DisplayName
    Apply "disable $($names.Count) other inbound rule(s) allowing port 22 (list saved in $stateDir)" {
      $names | Set-Content -LiteralPath (Join-Path $stateDir "disabled-firewall-rules-$stamp.txt") -Encoding utf8
      $others | Disable-NetFirewallRule
    }
    Info ("disabled: " + ($names -join ', '))
    Info 'to undo: Enable-NetFirewallRule -DisplayName "<name>"'
  } else { Info 'no other inbound rule allows port 22' }
} else {
  Info 'skipped (add -RestrictFirewall to limit SSH to Tailscale/LAN)'
  $open = Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True -ErrorAction SilentlyContinue |
    Where-Object { ($_ | Get-NetFirewallPortFilter).LocalPort -contains '22' -and
                   ($_ | Get-NetFirewallAddressFilter).RemoteAddress -contains 'Any' }
  if ($open) { Warn "inbound rules allow SSH from ANY address: $($open.DisplayName -join ', ')" }
}

# ---------------------------------------------------------------- 5. Wake-on-LAN
Step '5/5  Wake-on-LAN (network card + power settings)'
$nic = if ($WolAdapter) { Get-NetAdapter -Name $WolAdapter -ErrorAction Stop }
       else { Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' -and $_.MediaType -eq '802.3' } | Select-Object -First 1 }
if (-not $nic) { Warn 'no wired adapter found: Wake-on-LAN needs Ethernet (use -WolAdapter <name>)'; }
else {
  Info "adapter: $($nic.Name) ($($nic.InterfaceDescription))"
  $mac = $nic.MacAddress -replace '-', ':'
  Apply 'enable wake on magic packet / pattern in the adapter power management' {
    Set-NetAdapterPowerManagement -Name $nic.Name -WakeOnMagicPacket Enabled -WakeOnPattern Enabled `
      -DeviceSleepOnDisconnect Disabled -ErrorAction SilentlyContinue
  }
  foreach ($kw in @(@('*WakeOnMagicPacket', 1), @('*WakeOnPattern', 1), @('S5WakeOnLan', 1),
                    @('*EEE', 0), @('EnableGreenEthernet', 0), @('AdvancedEEE', 0), @('PowerSavingMode', 0))) {
    $prop = Get-NetAdapterAdvancedProperty -Name $nic.Name -RegistryKeyword $kw[0] -ErrorAction SilentlyContinue
    if ($prop) {
      Apply "adapter option $($kw[0]) = $($kw[1])" {
        Set-NetAdapterAdvancedProperty -Name $nic.Name -RegistryKeyword $kw[0] -RegistryValue $kw[1] -ErrorAction SilentlyContinue
      }
    }
  }
  Apply 'disable Windows Fast Startup (it blocks Wake-on-LAN from a full shutdown)' {
    Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -Value 0
  }
  Apply 'never go to sleep/hibernate on AC power' {
    & powercfg.exe /change standby-timeout-ac 0 | Out-Null
    & powercfg.exe /change hibernate-timeout-ac 0 | Out-Null
  }
  Warn 'ALSO in the BIOS/UEFI: enable "Power On By PCI-E / Wake on LAN" and disable "ErP Ready / Deep Sleep".'
}

# ---------------------------------------------------------------- summary
Step 'Values for your config.yaml on the laptop'
$ts = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $ts) { $ts = Get-Command 'C:\Program Files\Tailscale\tailscale.exe' -ErrorAction SilentlyContinue }
$tsIp = if ($ts) { (& $ts.Source ip -4 2>$null | Select-Object -First 1) } else { $null }
Info "connection.name         : $env:COMPUTERNAME"
Info "connection.user         : $User"
Info ("connection.tailscale_ip : " + $(if ($tsIp) { $tsIp } else { '(install Tailscale and sign in on the tower)' }))
if ($nic) { Info "connection.mac           : $mac" }
$lanIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -match '^(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))\.' } | Select-Object -First 1).IPAddress
if ($lanIp) { Info "connection.lan_ip       : $lanIp  (reserve it in your router: static DHCP lease)" }
Write-Host "`nDone." -ForegroundColor Green
