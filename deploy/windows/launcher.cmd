@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
set "OFDOWNLOADER_PLATFORM=WINDOWS"
set "OFDOWNLOADER_REPO=%REPO_ROOT%"
set "OFDOWNLOADER_UPDATE_STATUS=unknown"

where git >nul 2>&1
if not errorlevel 1 (
    git -C "%OFDOWNLOADER_REPO%" fetch --quiet origin main >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%A in ('git -C "%OFDOWNLOADER_REPO%" rev-parse HEAD 2^>nul') do set "CURRENT=%%A"
        for /f "delims=" %%A in ('git -C "%OFDOWNLOADER_REPO%" rev-parse origin/main 2^>nul') do set "REMOTE=%%A"
        if defined CURRENT if defined REMOTE (
            if "!CURRENT!"=="!REMOTE!" (
                set "OFDOWNLOADER_UPDATE_STATUS=current"
            ) else (
                git -C "%OFDOWNLOADER_REPO%" merge-base --is-ancestor "!CURRENT!" "!REMOTE!" >nul 2>&1
                if not errorlevel 1 (set "OFDOWNLOADER_UPDATE_STATUS=available") else (set "OFDOWNLOADER_UPDATE_STATUS=diverged")
            )
        )
    ) else (
        set "OFDOWNLOADER_UPDATE_STATUS=offline"
    )
)

if not exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    echo No se encontro el entorno de Python.
    echo Ejecuta primero en PowerShell:
    echo powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%\instalar-windows.ps1"
    exit /b 1
)

"%REPO_ROOT%\.venv\Scripts\python.exe" "%REPO_ROOT%\ofbackup_cli.py" %*
set "EXITCODE=%ERRORLEVEL%"

if "%EXITCODE%"=="43" (
    echo.
    echo Actualizando OF Downloader desde GitHub...
    git -C "%OFDOWNLOADER_REPO%" pull --ff-only origin main
    if errorlevel 1 exit /b 1
    powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%\deploy\windows\instalar.ps1"
    if errorlevel 1 exit /b 1
    "%REPO_ROOT%\.venv\Scripts\python.exe" "%REPO_ROOT%\ofbackup_cli.py" %*
    exit /b %ERRORLEVEL%
)

exit /b %EXITCODE%
