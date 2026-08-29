@echo off
REM Alias de of-windows.cmd. Conservado para no romper accesos antiguos.
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

call "%SCRIPT_DIR%of-windows.cmd" %*
exit /b %ERRORLEVEL%
