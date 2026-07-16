@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python no esta instalado o no esta disponible en PATH.
    echo Instala Python 3.11, 3.12 o 3.13 desde https://python.org
    pause
    exit /b 1
)
python -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)"
if errorlevel 1 (
    echo Se necesita Python 3.11, 3.12 o 3.13. Python 3.14 no es compatible con OF-Scraper.
    pause
    exit /b 1
)
if not exist ".venv" (
    python -m venv .venv
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
pause
