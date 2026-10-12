@echo off
rem RemoteHub-AI launcher (Windows). First run creates a virtual environment and installs the dependencies.
setlocal
cd /d "%~dp0"
if not exist "config.yaml" (
    echo [RemoteHub] No config.yaml yet: copying config.example.yaml.
    copy /y "config.example.yaml" "config.yaml" >nul
    echo [RemoteHub] Edit config.yaml ^(IP, user, MAC...^) then run this file again.
    notepad "config.yaml"
    exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
    echo [RemoteHub] First launch: creating the virtual environment...
    python -m venv .venv || (echo Python 3.10+ not found in PATH & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)
)
start "" ".venv\Scripts\pythonw.exe" main.py
