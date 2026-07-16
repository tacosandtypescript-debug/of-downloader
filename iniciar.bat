@echo off
cd /d "%~dp0"
if not exist ".venv" (
    python -m venv .venv
    .venv\Scripts\pip install ofscraper Pillow customtkinter
)
.venv\Scripts\python app.py
pause
