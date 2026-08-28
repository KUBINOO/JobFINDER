@echo off
title JobFinder - Spouštěč aplikace
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"

if %errorlevel% neq 0 (
    echo.
    echo ==========================================================
    echo Došlo k chybě při spuštění aplikace JobFinder.
    echo ==========================================================
    pause
)
