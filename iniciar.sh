#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install ofscraper Pillow customtkinter
fi
.venv/bin/python app.py
