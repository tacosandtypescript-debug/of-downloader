@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "OFDOWNLOADER_PLATFORM=WINDOWS"
set "OFDOWNLOADER_REPO=%SCRIPT_DIR:~0,-1%"

if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo No se encontro el entorno de Python.
    echo Ejecuta primero en PowerShell:
    echo powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%instalar-windows.ps1"
    exit /b 1
)

"%SCRIPT_DIR%.venv\Scripts\python.exe" "%SCRIPT_DIR%ofbackup_cli.py" %*
set "EXITCODE=%ERRORLEVEL%"

if "%EXITCODE%"=="43" (
    echo.
    echo Actualizando OF Downloader desde GitHub...
    git -C "%OFDOWNLOADER_REPO%" pull --ff-only origin main
    if errorlevel 1 exit /b 1
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%instalar-windows.ps1"
    if errorlevel 1 exit /b 1
    "%SCRIPT_DIR%.venv\Scripts\python.exe" "%SCRIPT_DIR%ofbackup_cli.py" %*
    exit /b %ERRORLEVEL%
)

exit /b %EXITCODE%
