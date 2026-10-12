<#
.SYNOPSIS  Starts the Ollama server on the tower, listening on the loopback interface only.
.DESCRIPTION
  RemoteHub reaches it through an SSH tunnel, so nothing needs to listen on the network.
  Optional: -ModelsDir to store models on a bigger drive (e.g. D:\ollama\models).
#>
param([string]$ModelsDir = '')

$ErrorActionPreference = 'Stop'
$logDir = Join-Path $env:ProgramData 'RemoteHub\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$exe = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $exe) { $exe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
if (-not (Test-Path $exe)) { throw 'Ollama is not installed on the tower (https://ollama.com/download).' }

$env:OLLAMA_HOST = '127.0.0.1:11434'
if ($ModelsDir) { New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null; $env:OLLAMA_MODELS = $ModelsDir }

# Already answering? nothing to do.
try { Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; return } catch {}

# The desktop app also starts a server: stop it so that OLLAMA_HOST above is the one used.
Get-Process 'ollama app', 'ollama' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $logDir 'ollama.out.log') -RedirectStandardError (Join-Path $logDir 'ollama.err.log')
