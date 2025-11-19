# Run NL2SQL Streamlit Frontend

Write-Host "=== NL2SQL Streamlit Frontend ===" -ForegroundColor Green

# Check if in frontend directory
if (-not (Test-Path "streamlit_app.py")) {
    if (Test-Path "../frontend/streamlit_app.py") {
        Write-Host "Navigating to frontend directory..." -ForegroundColor Yellow
        cd ../frontend
    } elseif (Test-Path "frontend/streamlit_app.py") {
        Write-Host "Navigating to frontend directory..." -ForegroundColor Yellow
        cd frontend
    } else {
        Write-Host "[ERROR] Cannot find streamlit_app.py" -ForegroundColor Red
        Write-Host "Please run this script from project root or frontend directory" -ForegroundColor Yellow
        exit 1
    }
}

# Check if API is running
Write-Host "`nChecking API status..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    $health = $response.Content | ConvertFrom-Json
    
    Write-Host "[OK] API is running" -ForegroundColor Green
    Write-Host "  Provider: $($health.llm_provider)" -ForegroundColor Cyan
    Write-Host "  Model: $($health.llm_model)" -ForegroundColor Cyan
    Write-Host "  Database: $(if($health.database_connected){'Connected'}else{'Disconnected'})" -ForegroundColor Cyan
} catch {
    Write-Host "[WARNING] API is not responding" -ForegroundColor Yellow
    Write-Host "Make sure to run: .\setup_docker.ps1 first" -ForegroundColor Yellow
    Write-Host "`nContinuing anyway..." -ForegroundColor Cyan
}

# Check if dependencies are installed
Write-Host "`nChecking dependencies..." -ForegroundColor Yellow
$streamlitInstalled = python -m pip show streamlit 2>$null
if (-not $streamlitInstalled) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    pip install -r requirements.txt --quiet
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "[OK] Dependencies already installed" -ForegroundColor Green
}

# Run Streamlit
Write-Host "`nStarting Streamlit app..." -ForegroundColor Yellow
Write-Host "=" * 70 -ForegroundColor Green
Write-Host "Frontend will open at: http://localhost:8501" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host "=" * 70 -ForegroundColor Green

streamlit run streamlit_app.py
