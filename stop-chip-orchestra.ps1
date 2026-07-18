# Chip Orchestra — stop backend + frontend dev servers.
#
#   .\stop-chip-orchestra.ps1
#   .\stop-chip-orchestra.ps1 -StopDocker   # also run docker compose down

[CmdletBinding()]
param(
    [switch]$StopDocker
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

$BackendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }
$FrontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }

function Stop-PortListener([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "Port $Port — nothing listening."
        return
    }

    $pids = $connections.OwningProcess | Sort-Object -Unique
    foreach ($processId in $pids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        $name = if ($proc) { $proc.ProcessName } else { "pid $processId" }
        Write-Host "Stopping $name (PID $processId) on port $Port…"
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Stopping Chip Orchestra dev servers…" -ForegroundColor Cyan
Stop-PortListener $FrontendPort
Stop-PortListener $BackendPort

if ($StopDocker) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Push-Location $Root
        try {
            Write-Host "Stopping Docker infra (docker compose down)…"
            docker compose down
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Host "Docker not found — skipped compose down."
    }
}

Write-Host "Done." -ForegroundColor Green
