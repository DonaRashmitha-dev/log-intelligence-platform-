Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

$PROJECT = "C:\Users\$env:USERNAME\Downloads\log-intelligence-platform\log-intelligence-platform"
Set-Location $PROJECT
Write-Host "[1/6] Project: $PROJECT" -ForegroundColor Cyan

$ZIP = "$env:USERPROFILE\Downloads\ingestion-service.zip"
if (Test-Path $ZIP) {
    Write-Host "[2/6] Extracting zip..." -ForegroundColor Cyan
    Expand-Archive -Path $ZIP -DestinationPath $PROJECT -Force
    Write-Host "      Done" -ForegroundColor Green
} else {
    Write-Host "[2/6] No zip found, files assumed in place" -ForegroundColor Yellow
}

Write-Host "[3/6] Checking files..." -ForegroundColor Cyan
$ok = $true
$files = @(
    "services\ingestion\app\main.py",
    "services\ingestion\app\models.py",
    "services\ingestion\app\db.py",
    "services\ingestion\app\collectors\fault_api.py",
    "services\ingestion\app\collectors\redis_alerts.py",
    "services\ingestion\app\collectors\cpp_metrics.py",
    "services\ingestion\pyproject.toml"
)
foreach ($f in $files) {
    if (-not (Test-Path "$PROJECT\$f")) {
        Write-Host "  MISSING: $f" -ForegroundColor Red
        $ok = $false
    }
}
if (-not $ok) {
    Write-Host "Download ingestion-service.zip from Claude chat and put in Downloads" -ForegroundColor Red
    exit 1
}
Write-Host "      All files present" -ForegroundColor Green

Write-Host "[4/6] Installing Python deps..." -ForegroundColor Cyan
Set-Location "$PROJECT\services\ingestion"
pip install -e . --quiet
Write-Host "      Done" -ForegroundColor Green

Set-Location $PROJECT
Write-Host "[5/6] Checking Docker..." -ForegroundColor Cyan
$pg = docker ps --filter "name=logdb" --filter "status=running" -q
$rd = docker ps --filter "name=logredis" --filter "status=running" -q
if ((-not $pg) -or (-not $rd)) {
    Write-Host "      Starting containers..." -ForegroundColor Yellow
    docker compose up postgres redis -d 2>&1 | Out-Null
    Start-Sleep -Seconds 8
}
$ready = docker exec logdb pg_isready -U loguser -d logdb 2>&1
Write-Host "      $ready" -ForegroundColor Green

Write-Host "[6/6] Starting ingestion on :8001 ..." -ForegroundColor Cyan
Write-Host "      Health : http://localhost:8001/health"
Write-Host "      Logs   : http://localhost:8001/latest"
Write-Host "      Output : test_output.txt"
Write-Host "      Ctrl+C to stop`n" -ForegroundColor Yellow

Set-Location "$PROJECT\services\ingestion"
$env:DATABASE_URL     = "postgresql://loguser:logpass@localhost:5432/logdb"
$env:REDIS_URL        = "redis://localhost:6379"
$env:FAULT_API_URL    = "http://localhost:5001"
$env:NODE_WEBHOOK_URL = "http://localhost:3001"

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload 2>&1 | Tee-Object -FilePath "$PROJECT\test_output.txt"
