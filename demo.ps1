#Requires -Version 5.1
<#
.SYNOPSIS
    orchid · Cognitive Blueprint -- one-command demo launcher.

.DESCRIPTION
    1.  Kills every process currently occupying the API and dashboard ports.
    2.  Loads .env into the current process environment.
    3.  Verifies Docker is running.
    4.  Discovers the virtualenv Python executable.
    5.  Starts all Docker Compose services (project name: orchid).
    6.  Waits for Postgres, Zookeeper, Kafka, Schema Registry, Qdrant, Neo4j,
        Airflow webserver, and the candidate sandbox to be healthy/running.
    7.  Opens a new PowerShell window for the FastAPI server  (port 8000).
    8.  Opens a new PowerShell window for the Next.js dashboard (port 3000).
    9.  Waits for the API to respond, then opens the browser.
    10. Prints a URL summary.

.EXAMPLE
    .\demo.ps1
#>

# ── Bootstrap ─────────────────────────────────────────────────────────────────

$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
Set-Location $RepoRoot

$ComposeProject = 'orchid'

# ── Color helpers ─────────────────────────────────────────────────────────────

function Write-Step { param([string]$Msg)
    Write-Host ""
    Write-Host "  >> $Msg" -ForegroundColor Cyan
}
function Write-Ok   { param([string]$Msg) Write-Host "  OK  $Msg" -ForegroundColor Green  }
function Write-Warn { param([string]$Msg) Write-Host "  !!  $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "  XX  $Msg" -ForegroundColor Red    }

function Exit-Script {
    param([string]$Reason)
    Write-Fail $Reason
    Read-Host "`n  Press Enter to exit"
    exit 1
}

# ── Banner ────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  ======================================================" -ForegroundColor DarkCyan
Write-Host "     orchid  --  Cognitive Blueprint Demo Launcher      " -ForegroundColor Cyan
Write-Host "  ======================================================" -ForegroundColor DarkCyan
Write-Host ""

# =============================================================================
# STEP 1 -- Kill processes on app ports (FastAPI + Next.js only)
#
# Only clears the two processes we launch ourselves. Docker service ports
# (Airflow, Qdrant, Neo4j, Sandbox, etc.) are left untouched so a running
# stack is not disrupted between demo runs.
# =============================================================================

$AppPorts = @(8000, 3000)

Write-Step "Clearing app ports: $($AppPorts -join '  ')"

foreach ($port in $AppPorts) {
    $matchedLines = netstat -ano 2>$null | Where-Object { $_ -match ":$port\s" }

    foreach ($line in $matchedLines) {
        $parts  = ($line.Trim()) -split '\s+'
        $pidStr = $parts[-1]

        if ($pidStr -match '^\d+$') {
            $pidInt = [int]$pidStr
            if ($pidInt -le 4) { continue }

            try {
                Stop-Process -Id $pidInt -Force -ErrorAction SilentlyContinue
                Write-Warn "  Killed PID $pidInt (was on :$port)"
            } catch { }
        }
    }
}

Write-Ok "App ports cleared"

# =============================================================================
# STEP 2 -- Load .env
# =============================================================================

Write-Step "Loading environment variables"

$EnvFile = Join-Path $RepoRoot '.env'

if (-not (Test-Path $EnvFile)) {
    $ExampleFile = Join-Path $RepoRoot '.env.example'
    if (Test-Path $ExampleFile) {
        Copy-Item $ExampleFile $EnvFile
        Write-Warn ".env not found -- copied from .env.example"
        Write-Warn "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, and API_SECRET_KEY in .env before use"
    } else {
        Exit-Script ".env and .env.example are both missing from $RepoRoot"
    }
}

$envVarsLoaded = 0
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line -match '^\s*#') { return }

    if ($line -match '^([^=]+)=(.*)$') {
        $key   = $matches[1].Trim()
        $value = $matches[2].Trim()
        # strip inline comments (everything after unquoted #)
        $value = $value -replace '\s+#.*$', ''
        $value = $value -replace '^[''"]|[''"]$', ''
        [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
        $envVarsLoaded++
    }
}

Write-Ok "$envVarsLoaded variables loaded from .env"

# =============================================================================
# STEP 3 -- Verify Docker daemon
# =============================================================================

Write-Step "Checking Docker daemon"

$dockerReady = $false
for ($attempt = 1; $attempt -le 18; $attempt++) {
    docker info > $null 2> $null
    if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
    $elapsed = ($attempt - 1) * 5
    Write-Warn "Docker not yet ready -- ${elapsed}s elapsed (will keep trying up to 90s) ..."
    Start-Sleep 5
}
if (-not $dockerReady) {
    Exit-Script "Docker did not become ready after 90s. Open Docker Desktop, wait for the tray icon to stop animating, then retry."
}

Write-Ok "Docker is running"

# =============================================================================
# STEP 4 -- Locate Python executable
# =============================================================================

Write-Step "Locating Python"

$pythonExe = $null

$venvCandidates = @(
    (Join-Path $RepoRoot '.venv\Scripts\python.exe'),
    (Join-Path $RepoRoot  'venv\Scripts\python.exe')
)

foreach ($candidate in $venvCandidates) {
    if (Test-Path $candidate) {
        $pythonExe = $candidate
        break
    }
}

if (-not $pythonExe) {
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPython) {
        $pythonExe = $sysPython.Source
        Write-Warn "No virtualenv found -- using system Python at $pythonExe"
        Write-Warn "Run: python -m venv .venv && .venv\Scripts\activate && pip install -r services\api\requirements.txt"
    }
}

if (-not $pythonExe) {
    Exit-Script "Python not found. Run: python -m venv .venv && .venv\Scripts\activate && pip install -r services\api\requirements.txt"
}

$pyVersion = & $pythonExe --version 2>&1
Write-Ok "$pyVersion  ->  $pythonExe"

# =============================================================================
# STEP 5 -- docker compose up  (project name: orchid)
# =============================================================================

Write-Step "Removing any existing orchid containers (volumes preserved)"

docker compose -p $ComposeProject down 2>$null
Write-Ok "Previous containers removed"

Write-Step "Starting Docker Compose services"

docker compose -p $ComposeProject up -d
if ($LASTEXITCODE -ne 0) {
    Exit-Script "docker compose up failed (exit code $LASTEXITCODE)"
}

Write-Ok "Compose services started"

# =============================================================================
# STEP 6 -- Wait for services to be ready
# =============================================================================

function Wait-ContainerHealthy {
    param(
        [Parameter(Mandatory)][string]$ContainerName,
        [int]$TimeoutSec = 120
    )

    Write-Step "Waiting for $ContainerName to be healthy (up to ${TimeoutSec}s)"

    $deadline = (Get-Date).AddSeconds($TimeoutSec)

    while ((Get-Date) -lt $deadline) {
        $status = docker inspect --format '{{.State.Health.Status}}' $ContainerName 2>$null
        if ($status) { $status = $status.Trim() }

        switch ($status) {
            'healthy'   { Write-Ok "$ContainerName is healthy"; return }
            'unhealthy' { Exit-Script "$ContainerName is unhealthy. Check: docker logs $ContainerName" }
            default     { Write-Host "    $ContainerName  [$status] ..." -ForegroundColor DarkGray }
        }

        Start-Sleep 3
    }

    Exit-Script "$ContainerName did not become healthy in ${TimeoutSec}s. Check: docker logs $ContainerName"
}

function Wait-ContainerRunning {
    param(
        [Parameter(Mandatory)][string]$ContainerName,
        [int]$TimeoutSec    = 60,
        [int]$ExtraDelaySec = 5
    )

    Write-Step "Waiting for $ContainerName to be running (up to ${TimeoutSec}s)"

    $deadline = (Get-Date).AddSeconds($TimeoutSec)

    while ((Get-Date) -lt $deadline) {
        $status = docker inspect --format '{{.State.Status}}' $ContainerName 2>$null
        if ($status) { $status = $status.Trim() }

        if ($status -eq 'running') {
            Write-Ok "$ContainerName is running"
            if ($ExtraDelaySec -gt 0) {
                Write-Host "    Settling for ${ExtraDelaySec}s ..." -ForegroundColor DarkGray
                Start-Sleep $ExtraDelaySec
            }
            return
        }

        Write-Host "    $ContainerName  [$status] ..." -ForegroundColor DarkGray
        Start-Sleep 3
    }

    Exit-Script "$ContainerName did not start in ${TimeoutSec}s. Check: docker logs $ContainerName"
}

# Core data path — order mirrors docker-compose depends_on chain
Wait-ContainerHealthy -ContainerName "${ComposeProject}-postgres-1"         -TimeoutSec 120
Wait-ContainerHealthy -ContainerName "${ComposeProject}-zookeeper-1"        -TimeoutSec  90
Wait-ContainerHealthy -ContainerName "${ComposeProject}-kafka-1"            -TimeoutSec 150
Wait-ContainerHealthy -ContainerName "${ComposeProject}-schema-registry-1"  -TimeoutSec  90
Wait-ContainerHealthy -ContainerName "${ComposeProject}-qdrant-1"           -TimeoutSec  60
Wait-ContainerHealthy -ContainerName "${ComposeProject}-neo4j-1"            -TimeoutSec  90

# Airflow webserver starts only after airflow-init completes — give it extra time
Wait-ContainerHealthy -ContainerName "${ComposeProject}-airflow-webserver-1" -TimeoutSec 180

# Sandbox has no HEALTHCHECK — wait for running state
Wait-ContainerRunning -ContainerName "${ComposeProject}-sandbox-1" -TimeoutSec 60

Write-Ok "All services ready"

# =============================================================================
# Helper: launch a child PowerShell window via -EncodedCommand
#
# -EncodedCommand accepts a Base64-encoded UTF-16LE command string, which
# avoids all argument-parsing issues when the repo path contains spaces,
# ampersands, or other shell-special characters.
# =============================================================================

function Start-EncodedWindow {
    param(
        [Parameter(Mandatory)][string]$Title,
        [Parameter(Mandatory)][string]$Command,
        [string]$WorkDir = $RepoRoot
    )

    $fullCmd = '$Host.UI.RawUI.WindowTitle = ''' + $Title + '''; ' + $Command
    $bytes   = [System.Text.Encoding]::Unicode.GetBytes($fullCmd)
    $encoded = [Convert]::ToBase64String($bytes)

    Start-Process powershell.exe `
        -ArgumentList "-NoExit", "-EncodedCommand", $encoded `
        -WorkingDirectory $WorkDir
}

# =============================================================================
# STEP 7 -- FastAPI server  (port 8000)
#
# PYTHONPATH is set to the repo root so that `services.api.main` resolves
# without needing an editable install.
# =============================================================================

Write-Step "Opening FastAPI server window  (port 8000)"

$apiCommand = '$env:PYTHONPATH = ''' + $RepoRoot + '''; ' +
              'Set-Location ''' + $RepoRoot + '''; ' +
              '& ''' + $pythonExe + ''' -m uvicorn services.api.main:app --reload --host 0.0.0.0 --port 8000'

Start-EncodedWindow -Title "orchid API :8000" -Command $apiCommand -WorkDir $RepoRoot

Write-Ok "API server window opened  ->  http://localhost:8000"

# =============================================================================
# STEP 8 -- Next.js dashboard dev server  (port 3000)
# =============================================================================

Write-Step "Opening Next.js dashboard window  (port 3000)"

$DashDir = Join-Path $RepoRoot 'services\dashboard'
$NextBin = Join-Path $DashDir 'node_modules\next\dist\bin\next'

# Install npm dependencies if node_modules is missing
if (-not (Test-Path $NextBin)) {
    Write-Warn "node_modules not found -- running npm install in services\dashboard\"
    $origDir = (Get-Location).Path
    Set-Location $DashDir
    npm install
    if ($LASTEXITCODE -ne 0) { Exit-Script "npm install failed" }
    Set-Location $origDir
}

# Verify node is available
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Exit-Script "node not found on PATH. Install Node.js 20+ and retry."
}
$nodeExe = $nodeCmd.Source

$feCommand = 'Set-Location ''' + $DashDir + '''; ' +
             '& ''' + $nodeExe + ''' ''' + $NextBin + ''' dev'

Start-EncodedWindow -Title "orchid Dashboard :3000" -Command $feCommand -WorkDir $DashDir

Write-Ok "Next.js dev server window opened  ->  http://localhost:3000"

# =============================================================================
# STEP 9 -- Wait for API then open browser
# =============================================================================

Write-Step "Waiting for API server to be ready ..."

$apiReady = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" `
                               -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $apiReady = $true; break }
    } catch { }
    Write-Host "    API not yet up -- ${i}/30 ..." -ForegroundColor DarkGray
    Start-Sleep 2
}

if ($apiReady) {
    Write-Ok "API is responding"
} else {
    Write-Warn "API did not respond after 60s -- opening browser anyway"
}

Start-Process "http://localhost:3000"
Write-Ok "Browser opened at http://localhost:3000"

# =============================================================================
# STEP 10 -- Summary
# =============================================================================

$div = "  " + ("-" * 56)

Write-Host ""
Write-Host $div                                                                  -ForegroundColor DarkGray
Write-Host "  Service                    URL"                                    -ForegroundColor White
Write-Host $div                                                                  -ForegroundColor DarkGray
Write-Host "  Dashboard (Next.js)        http://localhost:3000"                  -ForegroundColor Green
Write-Host "  API (FastAPI)              http://localhost:8000"                  -ForegroundColor Green
Write-Host "  API docs (Swagger)         http://localhost:8000/docs"             -ForegroundColor Green
Write-Host "  API docs (ReDoc)           http://localhost:8000/redoc"            -ForegroundColor Green
Write-Host $div                                                                  -ForegroundColor DarkGray
Write-Host "  Candidate Sandbox          http://localhost:8080  (code-server)"   -ForegroundColor Cyan
Write-Host "  Airflow                    http://localhost:8082  (admin/admin)"   -ForegroundColor Cyan
Write-Host "  Qdrant                     http://localhost:6333"                  -ForegroundColor DarkGray
Write-Host "  Neo4j Browser              http://localhost:7474"                  -ForegroundColor DarkGray
Write-Host "  Schema Registry            http://localhost:8081"                  -ForegroundColor DarkGray
Write-Host "  Kafka (host access)        localhost:29092"                        -ForegroundColor DarkGray
Write-Host $div                                                                  -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Demo mode (no API keys needed):  POST /demo/token on the login page" -ForegroundColor Gray
Write-Host "  Stop Docker services:            docker compose -p orchid down"    -ForegroundColor Gray
Write-Host "  Remove volumes too:              docker compose -p orchid down -v" -ForegroundColor Gray
Write-Host ""
