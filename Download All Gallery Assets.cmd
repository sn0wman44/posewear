@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
python cache_galleries.py
pause
