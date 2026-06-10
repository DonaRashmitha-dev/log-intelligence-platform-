# Log Intelligence Platform - Single Startup Script
$ROOT = "C:\Users\donar\OneDrive\Desktop\Git Hub Projects\log-intelligence-platform\log-intelligence-platform"
$DASH = "C:\Users\donar\OneDrive\Desktop\Git Hub Projects\log-intelligence-platform"

Write-Host "=== LOG INTELLIGENCE PLATFORM ===" -ForegroundColor Cyan
Write-Host "Starting all services..." -ForegroundColor Yellow

# 1. Docker
Write-Host "[1/7] Starting Postgres + Redis..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ROOT'; docker compose up postgres redis -d; Write-Host 'Docker ready' -ForegroundColor Green; Start-Sleep 5"
Start-Sleep 6

# 2. Fault Injection
Write-Host "[2/7] Starting Fault Injection (port 5000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ROOT\services\fault_injection'; python main.py"

# 3. Monitoring
Write-Host "[3/7] Starting Monitoring System..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:REDIS_URL='redis://localhost:6379'; cd '$ROOT\services\monitoring'; python -m core.monitor --config config/config.json"

Start-Sleep 3

# 4. Ingestion
Write-Host "[4/7] Starting Ingestion Service (port 8001)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:DATABASE_URL='postgresql://loguser:changeme_strong_password@localhost:5432/logdb'; `$env:REDIS_URL='redis://localhost:6379'; `$env:FAULT_API_URL='http://localhost:5000'; cd '$ROOT\services\ingestion'; uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

Start-Sleep 3

# 5. Embedding Worker
Write-Host "[5/7] Starting Embedding Worker..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:DATABASE_URL='postgresql://loguser:changeme_strong_password@localhost:5432/logdb'; cd '$ROOT\services\embedding_worker'; python worker.py"

# 6. Anomaly Detector
Write-Host "[6/7] Starting EWMA Anomaly Detector..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:DATABASE_URL='postgresql://loguser:changeme_strong_password@localhost:5432/logdb'; cd '$ROOT\services'; python anomaly_detector.py"

# 7. Agent
Write-Host "[7/7] Starting Agent API (port 8002)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ROOT\services\agent'; uvicorn agent_api:app --host 0.0.0.0 --port 8002 --reload"

Start-Sleep 5

# HTTP server for dashboard + open browser
Write-Host "" 
Write-Host "=== ALL SERVICES STARTED ===" -ForegroundColor Cyan
Write-Host "Opening dashboard at http://localhost:8080/dashboard.html" -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$DASH'; python -m http.server 8080"
Start-Sleep 2
Start-Process "http://localhost:8080/dashboard.html"

Write-Host ""
Write-Host "Services running:" -ForegroundColor Cyan
Write-Host "  Fault Injection : http://localhost:5000" -ForegroundColor White
Write-Host "  Ingestion       : http://localhost:8001" -ForegroundColor White
Write-Host "  Agent API       : http://localhost:8002" -ForegroundColor White
Write-Host "  Dashboard       : http://localhost:8080/dashboard.html" -ForegroundColor White
