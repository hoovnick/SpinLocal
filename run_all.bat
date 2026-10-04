@echo off
title SpinLocal — Full Stack
cd /d "%~dp0"

echo Starting Guardian bot...
start "SpinLocal Guardian" python guardian.py

echo Starting Watchdog (manages main bot)...
python watchdog.py

pause
