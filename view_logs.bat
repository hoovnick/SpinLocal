@echo off
title SpinLocal Logs
cd /d "%~dp0data"

echo ========================================
echo  BOT LOG (last 30 lines)
echo ========================================
powershell -Command "Get-Content bot.log -Tail 30 -ErrorAction SilentlyContinue"

echo.
echo ========================================
echo  WATCHDOG LOG (last 20 lines)
echo ========================================
powershell -Command "Get-Content watchdog.log -Tail 20 -ErrorAction SilentlyContinue"

echo.
echo ========================================
echo  GUARDIAN LOG (last 20 lines)
echo ========================================
powershell -Command "Get-Content guardian.log -Tail 20 -ErrorAction SilentlyContinue"

echo.
pause
