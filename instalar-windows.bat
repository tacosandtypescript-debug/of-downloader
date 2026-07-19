@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar-windows.ps1"
if errorlevel 1 (
    echo.
    echo La instalacion no se completo.
    pause
    exit /b 1
)
echo.
echo Instalacion terminada.
pause
