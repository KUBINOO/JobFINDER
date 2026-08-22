$ErrorActionPreference = "Continue"
$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Nastaveni titulku konzole
$host.UI.RawUI.WindowTitle = "JobFinder App (Backend + Frontend)"

Clear-Host
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "                JOBFINDER LAUNCHER                        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$pythonExe = Join-Path $rootDir "backend\.venv\Scripts\python.exe"
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"

# Kontrola Python venv
if (-not (Test-Path $pythonExe)) {
    Write-Host "[CHYBA] Nenalezen Python v backend\.venv!" -ForegroundColor Red
    Write-Host "Cesta '$pythonExe' neexistuje." -ForegroundColor Yellow
    Read-Host "Stisknete Enter pro ukonceni..."
    exit 1
}

# Kontrola frontend
if (-not (Test-Path (Join-Path $frontendDir "package.json"))) {
    Write-Host "[CHYBA] Nenalezen frontend/package.json!" -ForegroundColor Red
    Read-Host "Stisknete Enter pro ukonceni..."
    exit 1
}

Write-Host "[1/3] Spoustim Backend (FastAPI na portu 8000)..." -ForegroundColor Green
$backendProcess = Start-Process -FilePath $pythonExe `
    -ArgumentList "-m", "uvicorn", "main:app", "--reload", "--port", "8000" `
    -WorkingDirectory $backendDir `
    -PassThru `
    -NoNewWindow

Write-Host "[2/3] Spoustim Frontend (Vite na portu 3000)..." -ForegroundColor Green
$npmCmd = (Get-Command "npm.cmd" -ErrorAction SilentlyContinue).Source
if (-not $npmCmd) { $npmCmd = "npm.cmd" }

$frontendProcess = Start-Process -FilePath $npmCmd `
    -ArgumentList "run", "dev" `
    -WorkingDirectory $frontendDir `
    -PassThru `
    -NoNewWindow

Write-Host "[3/3] Inicializuji servery a oteviram prohlizec..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Otevreni v prohlizeci
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  VSE BYLO USPESNE SPUSTENO!" -ForegroundColor Green
Write-Host "     - Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "     - Backend:  http://localhost:8000 (Docs: http://localhost:8000/docs)" -ForegroundColor White
Write-Host ""
Write-Host "  -> Aplikace byla otevrena ve vasem vychozim prohlizeci." -ForegroundColor Cyan
Write-Host "  -> TOTO OKNO NECHTE OTEVRENE (bezi v nem oba servery)." -ForegroundColor Yellow
Write-Host "  -> Pro ukonceni aplikace stisknete Ctrl+C nebo zavrete toto okno." -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

try {
    while ($true) {
        if ($backendProcess.HasExited) {
            Write-Host "`nBackend proces byl ukoncen!" -ForegroundColor Red
            break
        }
        if ($frontendProcess.HasExited) {
            Write-Host "`nFrontend proces byl ukoncen!" -ForegroundColor Red
            break
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "`nUkoncuji bezici servery..." -ForegroundColor Yellow
    if ($backendProcess -and -not $backendProcess.HasExited) {
        taskkill /PID $backendProcess.Id /T /F 2>$null | Out-Null
    }
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        taskkill /PID $frontendProcess.Id /T /F 2>$null | Out-Null
    }
    Write-Host "Vse bylo ukonceno." -ForegroundColor Green
}
