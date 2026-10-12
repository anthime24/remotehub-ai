<#
.SYNOPSIS  Starts JupyterLab on the tower: loopback only, protected by a token (reached through an SSH tunnel).
.PARAMETER Token  Access token (RemoteHub passes `vars.jupyter_token` from config.yaml). Refuses "change-me" and short tokens.
.PARAMETER NotebookDir  Folder served by Jupyter. Default: your user profile.
#>
param([Parameter(Mandatory)][string]$Token, [string]$NotebookDir = $HOME, [string]$Python = 'python')

$ErrorActionPreference = 'Stop'
if ($Token -eq 'change-me' -or $Token.Length -lt 16) {
  throw 'Refusing to start JupyterLab with a weak token: set vars.jupyter_token in config.yaml (16+ random characters).'
}
$logDir = Join-Path $env:ProgramData 'RemoteHub\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

try { Invoke-WebRequest 'http://127.0.0.1:8888/api' -UseBasicParsing -TimeoutSec 2 | Out-Null; return } catch {}

# The token is passed through the environment, not on the command line (visible in process lists).
$env:JUPYTER_TOKEN = $Token
$argsList = "-m jupyterlab --no-browser --ServerApp.ip=127.0.0.1 --ServerApp.port=8888 --ServerApp.port_retries=0 " +
            "--ServerApp.root_dir=`"$NotebookDir`""
Start-Process -FilePath $Python -ArgumentList $argsList -WorkingDirectory $NotebookDir -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'jupyter.out.log') -RedirectStandardError (Join-Path $logDir 'jupyter.err.log')
