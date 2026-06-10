# setup_ingestion.ps1
# Run from ANYWHERE — auto-finds project, installs ingestion service, starts it.
# Usage: Right-click → Run with PowerShell   OR   .\setup_ingestion.ps1 in VS Code terminal

$ErrorActionPreference = "Stop"

# ── 1. Find project root ──────────────────────────────────────────────────────
$PROJECT = "C:\Users\$env:USERNAME\Downloads\log-intelligence-platform\log-intelligence-platform"
if (-not (Test-Path "$PROJECT\docker-compose.yml")) {
    Write-Error "Project not found at $PROJECT — edit `$PROJECT in this script."
    exit 1
}
Set-Location $PROJECT
Write-Host "`n[1/6] Project found: $PROJECT" -ForegroundColor Cyan

# ── 2. Download & extract ingestion service zip ───────────────────────────────
$ZIP_URL = ""   # leave blank — zip already in Downloads or paste URL here
$ZIP_PATH = "$env:USERPROFILE\Downloads\ingestion-service.zip"

if (Test-Path $ZIP_PATH) {
    Write-Host "[2/6] Extracting ingestion-service.zip..." -ForegroundColor Cyan
    Expand-Archive -Path $ZIP_PATH -DestinationPath $PROJECT -Force
    Write-Host "      Extracted to $PROJECT\services\ingestion" -ForegroundColor Green
} else {
    Write-Host "[2/6] ZIP not found — assuming files already in place, skipping extract." -ForegroundColor Yellow
}

# ── 3. Verify required files exist ───────────────────────────────────────────
$required = @(
    "services\ingestion\app\main.py",
    "services\ingestion\app\models.py",
    "services\ingestion\app\db.py",
    "services\ingestion\app\collectors\fault_api.py",
    "services\ingestion\app\collectors\redis_alerts.py",
    "services\ingestion\app\collectors\cpp_metrics.py",
    "services\ingestion\pyproject.toml"
)
$missing = $false
foreach ($f in $required) {
    if (-not (Test-Path "$PROJECT\$f")) {
        Write-Host "  MISSING: $f" -ForegroundColor Red
        $missing = $true
    }
}
if ($missing) {
    Write-Error "Some files missing. Download ingestion-service.zip from Claude and put it in Downloads."
    exit 1
}
Write-Host "[3/6] All ingestion files present" -ForegroundColor Green

# ── 4. Install Python deps ─────────────────────────────────────────────────────
Write-Host "[4/6] Installing Python dependencies..." -ForegroundColor Cyan
Set-Location "$PROJECT\services\ingestion"
pip install -e . --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed"; exit 1 }
Write-Host "      Dependencies installed" -ForegroundColor Green

# ── 5. Ensure postgres + redis containers are running ─────────────────────────
Set-Location $PROJECT
Write-Host "[5/6] Checking Docker containers..." -ForegroundColor Cyan

$pgRunning = docker ps --filter "name=logdb" --filter "status=running" -q
$redisRunning = docker ps --filter "name=logredis" --filter "status=running" -q

if (-not $pgRunning -or -not $redisRunning) {
    Write-Host "      Starting postgres + redis..." -ForegroundColor Yellow
    docker compose up postgres redis -d 2>&1 | Out-Null
    Write-Host "      Waiting 8s for containers to be ready..."
    Start-Sleep -Seconds 8
} else {
    Write-Host "      postgres + redis already running" -ForegroundColor Green
}

# Verify DB is accepting connections
$pgReady = docker exec logdb pg_isready -U loguser -d logdb 2>&1
Write-Host "      DB status: $pgReady" -ForegroundColor Green

# ── 6. Start ingestion service ────────────────────────────────────────────────
Write-Host "[6/6] Starting ingestion service on port 8001..." -ForegroundColor Cyan
Write-Host "      Dashboard: http://localhost:8001/health" -ForegroundColor Green
Write-Host "      Latest logs: http://localhost:8001/latest" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop.`n" -ForegroundColor Yellow

Set-Location "$PROJECT\services\ingestion"

$env:DATABASE_URL    = "postgresql://loguser:logpass@localhost:5432/logdb"
$env:REDIS_URL       = "redis://localhost:6379"
$env:FAULT_API_URL   = "http://localhost:5001"
$env:NODE_WEBHOOK_URL= "http://localhost:3001"

# Run uvicorn — output goes to terminal AND to test_output.txt in project root
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload 2>&1 | Tee-Object -FilePath "$PROJECT\test_output.txt"
