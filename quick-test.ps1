# Quick verification script for the UAS Pub-Sub Log Aggregator
# PowerShell version

Write-Host "================================" -ForegroundColor Cyan
Write-Host "UAS Log Aggregator - Quick Test" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Checking Docker..." -ForegroundColor Yellow
docker --version
if ($LASTEXITCODE -ne 0) { Write-Host "Docker not found!" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "2. Checking Docker Compose..." -ForegroundColor Yellow
docker compose version
if ($LASTEXITCODE -ne 0) { Write-Host "Docker Compose not found!" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "3. Validating docker-compose.yml..." -ForegroundColor Yellow
docker compose config | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Invalid docker-compose.yml!" -ForegroundColor Red; exit 1 }
Write-Host "✓ docker-compose.yml is valid" -ForegroundColor Green

Write-Host ""
Write-Host "4. Building images (this may take a few minutes)..." -ForegroundColor Yellow
docker compose build

Write-Host ""
Write-Host "5. Starting services..." -ForegroundColor Yellow
docker compose up -d storage broker

Write-Host ""
Write-Host "6. Waiting for database to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "7. Starting aggregator..." -ForegroundColor Yellow
docker compose up -d aggregator

Write-Host ""
Write-Host "8. Waiting for aggregator to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "9. Testing API endpoints..." -ForegroundColor Yellow
Write-Host "   - GET /"
Invoke-RestMethod -Uri http://localhost:8080/ | ConvertTo-Json

Write-Host ""
Write-Host "   - GET /health"
Invoke-RestMethod -Uri http://localhost:8080/health | ConvertTo-Json

Write-Host ""
Write-Host "   - GET /stats"
Invoke-RestMethod -Uri http://localhost:8080/stats | ConvertTo-Json

Write-Host ""
Write-Host ""
Write-Host "10. Running publisher (this will send 25,000 events)..." -ForegroundColor Yellow
docker compose up publisher

Write-Host ""
Write-Host "11. Checking final stats..." -ForegroundColor Yellow
Invoke-RestMethod -Uri http://localhost:8080/stats | ConvertTo-Json

Write-Host ""
Write-Host "12. Viewing some processed events..." -ForegroundColor Yellow
Invoke-RestMethod -Uri "http://localhost:8080/events?limit=5" | ConvertTo-Json

Write-Host ""
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Test Complete!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view logs: docker compose logs -f"
Write-Host "To stop: docker compose down"
Write-Host "To clean up: docker compose down -v"
