<#
.SYNOPSIS  Creates an Ubuntu Server VM in VirtualBox on the tower, ready to be driven by RemoteHub-AI.

.DESCRIPTION
  - NAT network only: SSH and RDP are forwarded to 127.0.0.1 of the TOWER (never to the network).
    RemoteHub reaches them through its SSH tunnel.
  - Unattended Ubuntu install (VirtualBox "unattended install"), openssh-server installed at the end;
    with -WithDesktop also XFCE + xrdp for a remote desktop.
  - The password is asked interactively (or passed as a SecureString) and never written to the log.

  Fr : cree une VM Ubuntu Server dans VirtualBox (reseau NAT, ports exposes uniquement sur 127.0.0.1 de la tour).

.PARAMETER IsoPath   Path to an Ubuntu Server 24.04 "live-server" ISO (download from https://ubuntu.com/download/server).
.PARAMETER User      Linux user to create (default: remotehub).
.PARAMETER Password  SecureString. If omitted you are prompted.
.EXAMPLE
  .\Create-LinuxVm.ps1 -IsoPath D:\VM\ubuntu-24.04-live-server-amd64.iso -WithDesktop
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$IsoPath,
  [string]$VmName = 'RemoteHub-Linux',
  [string]$User = 'remotehub',
  [securestring]$Password,
  [string]$BaseFolder = (Join-Path $env:SystemDrive 'VMs'),
  [int]$MemoryMB = 4096,
  [int]$Cpus = 2,
  [int]$DiskGB = 40,
  [int]$SshPort = 2223,
  [int]$RdpPort = 33890,
  [switch]$WithDesktop,
  [string]$Locale = 'en_US',
  [string]$Country = 'US',
  [string]$TimeZone = 'UTC'
)

$ErrorActionPreference = 'Stop'
$vb = if ($env:VBOX_MSI_INSTALL_PATH) { Join-Path $env:VBOX_MSI_INSTALL_PATH 'VBoxManage.exe' } else { 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe' }
if (-not (Test-Path $vb)) { throw 'VirtualBox not found. Install it first:  winget install Oracle.VirtualBox' }
if (-not (Test-Path -LiteralPath $IsoPath)) { throw "ISO not found: $IsoPath" }
if ($User -notmatch '^[a-z_][a-z0-9_-]{0,30}$') { throw 'User must be a valid Linux user name (lowercase letters, digits, - and _).' }

$logDir = Join-Path $env:ProgramData 'RemoteHub\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'vm-create.log'
function L($m) { $line = "$(Get-Date -Format 'HH:mm:ss') $m"; $line | Out-File $log -Append -Encoding utf8; Write-Host $line }
function VB([string[]]$a) {
  $o = (& $vb @a 2>&1 | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { throw "VBoxManage $($a[0]) $($a[1]) failed: $o" }
  $o
}

# --- pre-flight (nothing is overwritten) ---
foreach ($p in $SshPort, $RdpPort) {
  if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { throw "Port $p is already in use on this PC (use -SshPort / -RdpPort)." }
}
if ((& $vb list vms 2>&1) -match [regex]::Escape("`"$VmName`"")) { throw "A VM named $VmName already exists: nothing was changed." }

if (-not $Password) { $Password = Read-Host "Password for Linux user '$User'" -AsSecureString }
$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password))
if ($plain.Length -lt 8) { throw 'Choose a password of at least 8 characters.' }

# --- create the VM ---
L "creating VM $VmName ($MemoryMB MB RAM, $Cpus vCPU, $DiskGB GB dynamic disk)"
[void](VB @('createvm', '--name', $VmName, '--ostype', 'Ubuntu24_LTS_64', '--basefolder', $BaseFolder, '--register'))
[void](VB @('modifyvm', $VmName, '--memory', $MemoryMB, '--cpus', $Cpus, '--ioapic', 'on', '--rtcuseutc', 'on',
            '--graphicscontroller', 'vmsvga', '--vram', '128', '--audio-enabled', 'off', '--clipboard-mode', 'disabled',
            '--nic1', 'nat', '--nictype1', 'virtio',
            '--natpf1', "ssh,tcp,127.0.0.1,$SshPort,,22", '--natpf1', "rdp,tcp,127.0.0.1,$RdpPort,,3389"))
$disk = Join-Path (Join-Path $BaseFolder $VmName) "$VmName.vdi"
[void](VB @('createmedium', 'disk', '--filename', $disk, '--size', ($DiskGB * 1024), '--format', 'VDI', '--variant', 'Standard'))
[void](VB @('storagectl', $VmName, '--name', 'SATA', '--add', 'sata', '--controller', 'IntelAhci', '--portcount', '2'))
[void](VB @('storageattach', $VmName, '--storagectl', 'SATA', '--port', '0', '--device', '0', '--type', 'hdd', '--medium', $disk))
L "VM created. SSH 127.0.0.1:$SshPort -> 22, RDP 127.0.0.1:$RdpPort -> 3389 (loopback of this PC only)"

# --- packages installed at the end of the unattended setup ---
$packages = 'openssh-server'
if ($WithDesktop) { $packages += ' xfce4 xfce4-terminal thunar mousepad dbus-x11 xrdp xorgxrdp fonts-dejavu-core' }
$post = "chroot /target apt-get install -y $packages"

# --- unattended install; the password goes through a temp file, not the command line ---
$pwFile = Join-Path $env:TEMP "rh-vm-pw-$([guid]::NewGuid().ToString('N')).txt"
try {
  Set-Content -LiteralPath $pwFile -Value $plain -Encoding ascii -NoNewline
  $null = & icacls.exe $pwFile /inheritance:r /grant:r "$($env:USERNAME):F" 2>&1
  L 'starting the unattended Ubuntu install (10-25 minutes, headless)'
  $out = VB @('unattended', 'install', $VmName, "--iso=$IsoPath", "--user=$User", "--user-password-file=$pwFile",
              "--full-user-name=$User", '--hostname=remotehub-linux.local', "--locale=$Locale", "--country=$Country",
              "--time-zone=$TimeZone", "--post-install-command=$post", '--start-vm=headless')
  L ('unattended: ' + (($out -replace '\s+', ' ')))
} finally {
  Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue
  $plain = $null
}

L 'DONE (installation is running inside the VM)'
L "wait for it with:  .\ensure_vm.ps1 -VmName $VmName -SshPort $SshPort   (returns 0 once SSH answers)"
L "then, from the laptop: install your SSH key in the VM (see docs/en/04-linux-vm.md)"
