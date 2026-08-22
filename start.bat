@echo off
title JobFinder
cd /d "%~dp0"

:: Spustit powershell skript v tomto samém okně
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"

if %errorlevel% neq 0 (
    echo.
    echo ==========================================================
    echo Došlo k chybě při spuštění.
    echo ==========================================================
    pause
)
