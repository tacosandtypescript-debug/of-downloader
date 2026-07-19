@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "OFDOWNLOADER_PLATFORM=WINDOWS"
set "OFDOWNLOADER_REPO=%SCRIPT_DIR:~0,-1%"

if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo No se encontro el entorno de Python.
    echo Ejecuta primero: instalar-windows.bat
    exit /b 1
)

"%SCRIPT_DIR%.venv\Scripts\python.exe" "%SCRIPT_DIR%app.py" %*
exit /b %ERRORLEVEL%
