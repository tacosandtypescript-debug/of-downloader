@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "OFDOWNLOADER_PLATFORM=WINDOWS"
  ".venv\Scripts\python.exe" "ofbackup_cli.py" dashboard
  exit /b %ERRORLEVEL%
)
call "of-windows.cmd" dashboard
