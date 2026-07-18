# Chip Orchestra — start backend + frontend in separate console windows.
#
#   .\start-chip-orchestra.ps1           # start stack (install deps on first run)
#   .\start-chip-orchestra.ps1 -Setup    # force-reinstall dependencies
#
# Backend : http://localhost:8000   (API docs at /docs)
# Frontend: http://localhost:5173
#
# If scripts are blocked, run once:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# or bypass for this session:
#   powershell -ExecutionPolicy Bypass -File .\start-chip-orchestra.ps1

[CmdletBinding()]
param(
    [switch]$Setup,
    [switch]$NoDocker
)

$ErrorActionPreference = 'Stop'

$Root = $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'

$BackendHost = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { '0.0.0.0' }
$BackendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }
$FrontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }
$OllamaHost = if ($env:OLLAMA_HOST) { $env:OLLAMA_HOST } else { 'http://localhost:11434' }

function Write-Step([string]$Message) {
  Write-Host "▶ $Message" -ForegroundColor Cyan
}
function Write-Warn([string]$Message) {
  Write-Host "⚠ $Message" -ForegroundColor Yellow
}
function Test-CommandExists([string]$Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}
function Get-PortProcess([int]$Port) {
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if (-not $conn) { return $null }
  return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
}

# --- prerequisites ---------------------------------------------------------
if (-not (Test-CommandExists 'uv')) { throw 'uv is required. Install from https://docs.astral.sh/uv/' }
if (-not (Test-CommandExists 'node')) { throw 'Node.js (>=18) is required. Install from https://nodejs.org/' }

# --- backend setup ---------------------------------------------------------
Push-Location $Backend
try {
  if ($Setup -or -not (Test-Path '.venv')) {
    Write-Step 'Backend: creating venv + installing dependencies (uv)…'
    uv venv --python 3.12
    uv pip install -e .
  }
  if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Step 'Backend: created .env from .env.example'
  }
}
finally {
  Pop-Location
}

# --- optional infra: Postgres + MinIO via Docker ---------------------------
$backendEnvPath = Join-Path $Backend '.env'
$hasDatabaseUrl = $false
if (Test-Path $backendEnvPath) {
  $hasDatabaseUrl = Select-String -Path $backendEnvPath -Pattern '^\s*DATABASE_URL=' -Quiet
}

if (-not $NoDocker -and $env:NO_DOCKER -ne '1' -and $hasDatabaseUrl) {
  if (Test-CommandExists 'docker') {
    try {
      docker ps *> $null
      Write-Step 'Infra: starting Postgres + MinIO (docker compose)…'
      Push-Location $Root
      try {
        docker compose up -d 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
          Write-Warn 'docker compose failed — backend will use the local file store'
        }
      }
      finally {
        Pop-Location
      }
    }
    catch {
      Write-Warn 'Docker not available — Postgres/MinIO skipped; using the local file store.'
    }
  }
  else {
    Write-Warn 'Docker not found — Postgres/MinIO skipped; using the local file store.'
  }
}

# --- frontend setup --------------------------------------------------------
Push-Location $Frontend
try {
  if (-not (Test-Path '.env')) {
    @(
      "VITE_API_BASE_URL=http://localhost:$BackendPort"
      'VITE_USE_MOCKS=true'
    ) | Set-Content -Path '.env' -Encoding utf8
    Write-Step 'Frontend: created .env'
  }

  $viteBin = Join-Path 'node_modules' '.bin' 'vite.cmd'
  if ($Setup -or -not (Test-Path $viteBin)) {
    if (Test-CommandExists 'npm') {
      Write-Step 'Frontend: installing dependencies (npm)…'
      npm install --no-audit --no-fund
    }
    elseif (Test-CommandExists 'pnpm') {
      Write-Step 'Frontend: installing dependencies (pnpm)…'
      pnpm install --ignore-workspace
    }
    else {
      throw 'npm or pnpm is required for the frontend.'
    }
  }
}
finally {
  Pop-Location
}

# --- soft check: Ollama ----------------------------------------------------
try {
  $null = Invoke-WebRequest -Uri "$OllamaHost/api/tags" -UseBasicParsing -TimeoutSec 3
}
catch {
  Write-Warn "Ollama not reachable at $OllamaHost — RTL generation will fail until 'ollama serve' is running."
}

# --- port checks -----------------------------------------------------------
$backendProc = Get-PortProcess $BackendPort
$frontendProc = Get-PortProcess $FrontendPort

if ($backendProc) {
  Write-Warn "Port $BackendPort is already in use (PID $($backendProc.Id), $($backendProc.ProcessName)). Skipping backend start."
}
if ($frontendProc) {
  Write-Warn "Port $FrontendPort is already in use (PID $($frontendProc.Id), $($frontendProc.ProcessName)). Skipping frontend start."
}

if ($backendProc -and $frontendProc) {
  Write-Host ''
  Write-Host 'Chip Orchestra appears to be already running:' -ForegroundColor Green
  Write-Host "  • Frontend → http://localhost:$FrontendPort"
  Write-Host "  • Backend  → http://localhost:$BackendPort (docs: /docs)"
  Write-Host ''
  Write-Host 'Use .\\stop-chip-orchestra.ps1 to stop, then re-run this script.'
  exit 0
}

# --- start services in new windows -----------------------------------------
$backendCmd = @"
Set-Location -LiteralPath '$Backend'
`$host.ui.RawUI.WindowTitle = 'Chip Orchestra — Backend (:$BackendPort)'
Write-Host 'Starting backend on http://localhost:$BackendPort' -ForegroundColor Green
uv run uvicorn chip_orchestra_backend.main:app --host $BackendHost --port $BackendPort
"@

$frontendCmd = @"
Set-Location -LiteralPath '$Frontend'
`$host.ui.RawUI.WindowTitle = 'Chip Orchestra — Frontend (:$FrontendPort)'
Write-Host 'Starting frontend on http://localhost:$FrontendPort' -ForegroundColor Green
& '.\\node_modules\\.bin\\vite.cmd' --host --port $FrontendPort --strictPort
"@

if (-not $backendProc) {
  Write-Step "Starting backend on http://localhost:${BackendPort}"
  Start-Process powershell.exe -ArgumentList '-NoExit', '-NoProfile', '-Command', $backendCmd
}
if (-not $frontendProc) {
  Write-Step "Starting frontend on http://localhost:${FrontendPort}"
  Start-Process powershell.exe -ArgumentList '-NoExit', '-NoProfile', '-Command', $frontendCmd
}

Write-Host ''
Write-Host 'Chip Orchestra is starting:' -ForegroundColor Green
Write-Host "  • Frontend → http://localhost:$FrontendPort"
Write-Host "  • Backend  → http://localhost:$BackendPort (docs: /docs)"

if ($hasDatabaseUrl) {
  Write-Host '  • MinIO    → http://localhost:9001 (console; API :9000)'
  Write-Host '  • Postgres → localhost:5432 (db: chiporchestra)'
}

Write-Host ''
Write-Host 'Logs run in the two PowerShell windows that just opened.'
Write-Host 'Stop with: .\\stop-chip-orchestra.ps1'
Write-Host ''

