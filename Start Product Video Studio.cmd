@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set STUDIO_PORT=8766
start "" http://127.0.0.1:8766
python studio\app.py
pause
