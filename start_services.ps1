# start_services.ps1
Write-Host "Starting DeligenX Platform Services..." -ForegroundColor Cyan

# 1. Start Redis using Docker Compose
Write-Host "[1/3] Starting Redis (Message Broker)..." -ForegroundColor Yellow
docker-compose up -d

# Check if docker-compose succeeded
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running. Please open Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

# Wait a couple of seconds for Redis to initialize
Start-Sleep -Seconds 2

# 2. Start Uvicorn (FastAPI Backend) in a new window
Write-Host "[2/3] Starting FastAPI Backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command `"& .\.venv\Scripts\Activate.ps1; uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`""

# 3. Start Celery Worker in a new window
Write-Host "[3/3] Starting Celery Worker..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command `"& .\.venv\Scripts\Activate.ps1; celery -A api.celery_app worker --loglevel=info --pool=solo`""

Write-Host "All services started successfully!" -ForegroundColor Green
Write-Host "FastAPI is running on http://localhost:8000"
Write-Host "Celery is listening for background tasks."
