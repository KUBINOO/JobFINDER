$ErrorActionPreference = "Continue"
$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Nastaveni titulku konzole
$host.UI.RawUI.WindowTitle = "JobFinder AI - Launcher & Server Runner"

Clear-Host
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "                JOBFINDER AI LAUNCHER                     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$venvDir = Join-Path $backendDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$requirementsTxt = Join-Path $backendDir "requirements.txt"
$nodeModulesDir = Join-Path $frontendDir "node_modules"

# -------------------------------------------------------------
# 1. KONTROLA A AUTOMATICKÁ INSTALACE PYTHONU & KNIHOVEN
# -------------------------------------------------------------
if (-not (Test-Path $pythonExe)) {
    Write-Host "[1/3] Virtuální prostředí Pythonu nebylo nalezeno. Spouštím automatickou instalaci..." -ForegroundColor Yellow
    
    # Hledani systemoveho Pythonu
    $sysPython = $null
    if (Get-Command "python.exe" -ErrorAction SilentlyContinue) {
        $sysPython = "python.exe"
    } elseif (Get-Command "py.exe" -ErrorAction SilentlyContinue) {
        $sysPython = "py.exe"
    }

    if (-not $sysPython) {
        Write-Host ""
        Write-Host "----------------------------------------------------------" -ForegroundColor Red
        Write-Host " [CHYBA] Na vašem počítači nebyl nalezen nainstalovaný Python!" -ForegroundColor Red
        Write-Host "----------------------------------------------------------" -ForegroundColor Red
        Write-Host "Pro spuštění aplikace je potřeba Python 3.10 nebo novější." -ForegroundColor White
        Write-Host "1. Stáhněte a nainstalujte Python z: https://www.python.org/downloads/" -ForegroundColor Cyan
        Write-Host "2. PŘI INSTALACI ZAŠKRTNĚTE: 'Add python.exe to PATH'!" -ForegroundColor Yellow
        Write-Host ""
        Read-Host "Stiskněte Enter pro ukončení..."
        exit 1
    }

    Write-Host "  -> Vytvářím virtuální prostředí Pythonu (.venv)..." -ForegroundColor Cyan
    & $sysPython -m venv $venvDir
    if (-not (Test-Path $pythonExe)) {
        Write-Host "❌ Nepodařilo se vytvořit virtuální prostředí v $venvDir" -ForegroundColor Red
        Read-Host "Stiskněte Enter pro ukončení..."
        exit 1
    }

    Write-Host "  -> Instaluji potřebné Python knihovny (FastAPI, AI SDK, Scrapery)..." -ForegroundColor Cyan
    & $pythonExe -m pip install --upgrade pip --quiet
    & $pythonExe -m pip install -r $requirementsTxt
    Write-Host "  ✅ Python backend byl úspěšně připraven!" -ForegroundColor Green
    Write-Host ""
}

# -------------------------------------------------------------
# 2. KONTROLA A AUTOMATICKÁ INSTALACE NODE.JS / NPM & FRONTENDU
# -------------------------------------------------------------
$npmCmd = (Get-Command "npm.cmd" -ErrorAction SilentlyContinue).Source
if (-not $npmCmd) {
    if (Get-Command "npm" -ErrorAction SilentlyContinue) {
        $npmCmd = "npm"
    } else {
        Write-Host ""
        Write-Host "----------------------------------------------------------" -ForegroundColor Red
        Write-Host " [CHYBA] Na vašem počítači nebyl nalezen Node.js (npm)!" -ForegroundColor Red
        Write-Host "----------------------------------------------------------" -ForegroundColor Red
        Write-Host "Pro spuštění frontendu je potřeba Node.js." -ForegroundColor White
        Write-Host "Stáhněte a nainstalujte doporučenou verzi z: https://nodejs.org/" -ForegroundColor Cyan
        Write-Host ""
        Read-Host "Stiskněte Enter pro ukončení..."
        exit 1
    }
}

if (-not (Test-Path $nodeModulesDir)) {
    Write-Host "[2/3] Frontend knihovny (node_modules) nebyly nalezeny. Instaluji..." -ForegroundColor Yellow
    Push-Location $frontendDir
    & $npmCmd install
    Pop-Location
    Write-Host "  ✅ Frontend knihovny byly úspěšně nainstalovány!" -ForegroundColor Green
    Write-Host ""
}

# -------------------------------------------------------------
# 3. SPUŠTĚNÍ SERVERŮ A OTEVŘENÍ V PROHLÍŽEČI
# -------------------------------------------------------------
Write-Host "[1/2] Spouštím Backend (FastAPI na portu 8000)..." -ForegroundColor Green
$backendProcess = Start-Process -FilePath $pythonExe `
    -ArgumentList "-m", "uvicorn", "main:app", "--reload", "--port", "8000" `
    -WorkingDirectory $backendDir `
    -PassThru `
    -NoNewWindow

Write-Host "[2/2] Spouštím Frontend (Vite na portu 3000)..." -ForegroundColor Green
$frontendProcess = Start-Process -FilePath $npmCmd `
    -ArgumentList "run", "dev" `
    -WorkingDirectory $frontendDir `
    -PassThru `
    -NoNewWindow

Write-Host ""
Write-Host "Inicializuji servery a otevírám aplikaci v prohlížeči..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Otevreni v prohlizeci
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🎉 VŠECHNO BYLO ÚSPĚŠNĚ SPUŠTĚNO!" -ForegroundColor Green
Write-Host "     - Aplikace: http://localhost:3000" -ForegroundColor White
Write-Host "     - Backend:  http://localhost:8000 (API Docs: http://localhost:8000/docs)" -ForegroundColor White
Write-Host ""
Write-Host "  -> Aplikace běží ve vašem webovém prohlížeči." -ForegroundColor Cyan
Write-Host "  -> TOTO OKNO NECHTE OTEVŘENÉ (běží v něm oba servery)." -ForegroundColor Yellow
Write-Host "  -> Pro ukončení stiskněte Ctrl+C nebo zavřete toto okno." -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

try {
    while ($true) {
        if ($backendProcess.HasExited) {
            Write-Host "`nBackend proces byl ukončen!" -ForegroundColor Red
            break
        }
        if ($frontendProcess.HasExited) {
            Write-Host "`nFrontend proces byl ukončen!" -ForegroundColor Red
            break
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "`nUkončuji běžící servery..." -ForegroundColor Yellow
    if ($backendProcess -and -not $backendProcess.HasExited) {
        taskkill /PID $backendProcess.Id /T /F 2>$null | Out-Null
    }
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        taskkill /PID $frontendProcess.Id /T /F 2>$null | Out-Null
    }
    Write-Host "Vše bylo úspěšně ukončeno." -ForegroundColor Green
}
