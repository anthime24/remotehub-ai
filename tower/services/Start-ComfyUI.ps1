<#
.SYNOPSIS  Starts ComfyUI on the tower, listening on the loopback interface only (reached through an SSH tunnel).
.PARAMETER ComfyDir  Folder containing main.py. Default: $env:COMFYUI_DIR, then $HOME\ComfyUI.
.PARAMETER Python    Python to use. Default: the venv python inside ComfyDir if any, else `python`.
.PARAMETER ExtraArgs Extra ComfyUI flags (e.g. "--lowvram" for GPUs with little memory).
#>
param([string]$ComfyDir = '', [string]$Python = '', [string]$ExtraArgs = '')

$ErrorActionPreference = 'Stop'
$logDir = Join-Path $env:ProgramData 'RemoteHub\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not $ComfyDir) { $ComfyDir = if ($env:COMFYUI_DIR) { $env:COMFYUI_DIR } else { Join-Path $HOME 'ComfyUI' } }
if (-not (Test-Path (Join-Path $ComfyDir 'main.py'))) {
  throw "ComfyUI not found in $ComfyDir. Install it, or pass -ComfyDir / set the COMFYUI_DIR environment variable."
}
if (-not $Python) {
  foreach ($c in @('venv\Scripts\python.exe', '.venv\Scripts\python.exe', 'python_embeded\python.exe')) {
    if (Test-Path (Join-Path $ComfyDir $c)) { $Python = Join-Path $ComfyDir $c; break }
  }
  if (-not $Python) { $Python = 'python' }
}

try { Invoke-WebRequest 'http://127.0.0.1:8188/' -UseBasicParsing -TimeoutSec 2 | Out-Null; return } catch {}

$argsList = "main.py --listen 127.0.0.1 --port 8188 $ExtraArgs".Trim()
Start-Process -FilePath $Python -ArgumentList $argsList -WorkingDirectory $ComfyDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'comfyui.out.log') -RedirectStandardError (Join-Path $logDir 'comfyui.err.log')
