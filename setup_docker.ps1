# Setup NL2SQL with Docker (MySQL + API)

Write-Host "=== NL2SQL Full Docker Setup ===" -ForegroundColor Green

# Check if Docker is running
Write-Host "`nChecking Docker..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "[OK] Docker is running" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check if .env exists and validate LLM provider
Write-Host "`nChecking .env file..." -ForegroundColor Yellow
if (-not (Test-Path .env)) {
    Write-Host "[ERROR] .env file not found! Please copy from .env.example" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] .env exists" -ForegroundColor Green

# Check LLM provider configuration
$envContent = Get-Content .env -Raw
$llmProvider = "openai"  # default

if ($envContent -match 'LLM_PROVIDER=(\w+)') {
    $llmProvider = $matches[1].ToLower()
}

Write-Host "`nDetected LLM Provider: $llmProvider" -ForegroundColor Cyan

# Validate API keys based on provider
$providerConfigured = $false

switch ($llmProvider) {
    "openai" {
        if ($envContent -match 'OPENAI_API_KEY="?sk-[^"\s]+') {
            Write-Host "[OK] OpenAI API key configured" -ForegroundColor Green
            $providerConfigured = $true
        } else {
            Write-Host "[WARNING] OpenAI API key not found or invalid" -ForegroundColor Yellow
        }
    }
    "gemini" {
        if ($envContent -match 'GEMINI_API_KEY="?[^"\s]+') {
            Write-Host "[OK] Gemini API key configured" -ForegroundColor Green
            $providerConfigured = $true
        } else {
            Write-Host "[ERROR] Gemini API key not found!" -ForegroundColor Red
            Write-Host "Get free key at: https://aistudio.google.com/apikey" -ForegroundColor Yellow
            exit 1
        }
    }
    "openrouter" {
        if ($envContent -match 'OPENROUTER_API_KEY="?sk-or-[^"\s]+') {
            Write-Host "[OK] OpenRouter API key configured" -ForegroundColor Green
            $providerConfigured = $true
        } else {
            Write-Host "[ERROR] OpenRouter API key not found!" -ForegroundColor Red
            Write-Host "Get key at: https://openrouter.ai/keys" -ForegroundColor Yellow
            exit 1
        }
    }
    "anthropic" {
        if ($envContent -match 'ANTHROPIC_API_KEY="?sk-ant-[^"\s]+') {
            Write-Host "[OK] Anthropic API key configured" -ForegroundColor Green
            $providerConfigured = $true
        } else {
            Write-Host "[ERROR] Anthropic API key not found!" -ForegroundColor Red
            exit 1
        }
    }
    default {
        Write-Host "[WARNING] Unknown provider: $llmProvider, defaulting to OpenAI" -ForegroundColor Yellow
    }
}

if (-not $providerConfigured) {
    Write-Host "`n[WARNING] No valid LLM provider configured!" -ForegroundColor Yellow
    Write-Host "Checking for fallback providers..." -ForegroundColor Cyan
    
    # Try Gemini as fallback (free)
    if ($envContent -match 'GEMINI_API_KEY="?[^"\s]+' -and $envContent -notmatch 'GEMINI_API_KEY="?your-') {
        Write-Host "[OK] Found Gemini API key, using as fallback" -ForegroundColor Green
        # Update .env to use Gemini
        $envContent = $envContent -replace 'LLM_PROVIDER=\w+', 'LLM_PROVIDER=gemini'
        $envContent | Set-Content .env
        Write-Host "[INFO] Updated .env to use Gemini provider" -ForegroundColor Cyan
    }
    # Try OpenAI as fallback
    elseif ($envContent -match 'OPENAI_API_KEY="?sk-[^"\s]+') {
        Write-Host "[OK] Found OpenAI API key, using as fallback" -ForegroundColor Green
        $envContent = $envContent -replace 'LLM_PROVIDER=\w+', 'LLM_PROVIDER=openai'
        $envContent | Set-Content .env
        Write-Host "[INFO] Updated .env to use OpenAI provider" -ForegroundColor Cyan
    }
    # Try OpenRouter as fallback
    elseif ($envContent -match 'OPENROUTER_API_KEY="?sk-or-[^"\s]+') {
        Write-Host "[OK] Found OpenRouter API key, using as fallback" -ForegroundColor Green
        $envContent = $envContent -replace 'LLM_PROVIDER=\w+', 'LLM_PROVIDER=openrouter'
        $envContent | Set-Content .env
        Write-Host "[INFO] Updated .env to use OpenRouter provider" -ForegroundColor Cyan
    }
    else {
        Write-Host "[ERROR] No valid API key found for any provider!" -ForegroundColor Red
        Write-Host "`nPlease add at least one API key to .env:" -ForegroundColor Yellow
        Write-Host "  - Gemini (FREE): https://aistudio.google.com/apikey" -ForegroundColor White
        Write-Host "  - OpenRouter: https://openrouter.ai/keys" -ForegroundColor White
        Write-Host "  - OpenAI: https://platform.openai.com/api-keys" -ForegroundColor White
        exit 1
    }
}

# Stop existing containers
Write-Host "`nStopping existing containers..." -ForegroundColor Yellow
docker-compose -f docker-compose.full.yml down 2>$null

# Build and start services
Write-Host "`nBuilding and starting services..." -ForegroundColor Yellow
Write-Host "This may take a few minutes on first run..." -ForegroundColor Cyan
docker-compose -f docker-compose.full.yml up -d --build

# Wait for MySQL to be ready
Write-Host "`nWaiting for MySQL to be ready..." -ForegroundColor Yellow
$maxRetries = 30
$retries = 0
while ($retries -lt $maxRetries) {
    $health = docker inspect --format='{{.State.Health.Status}}' nl2sql-mysql 2>$null
    if ($health -eq "healthy") {
        Write-Host "[OK] MySQL is ready" -ForegroundColor Green
        break
    }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
    $retries++
}

if ($retries -eq $maxRetries) {
    Write-Host "`n[ERROR] MySQL failed to start" -ForegroundColor Red
    Write-Host "Check logs: docker-compose -f docker-compose.full.yml logs mysql" -ForegroundColor Yellow
    exit 1
}

# Wait for API to be ready
Write-Host "`nWaiting for API to be ready..." -ForegroundColor Yellow
$maxRetries = 30
$retries = 0
while ($retries -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] API is ready" -ForegroundColor Green
            break
        }
    } catch {
        # Continue waiting
    }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
    $retries++
}

if ($retries -lt $maxRetries) {
    # Verify setup
    Write-Host "`nVerifying setup..." -ForegroundColor Yellow
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
        if ($health.status -eq "healthy") {
            Write-Host "[OK] Health check passed" -ForegroundColor Green
            Write-Host "  Database connected: $($health.database_connected)" -ForegroundColor White
            Write-Host "  OpenAI configured: $($health.openai_configured)" -ForegroundColor White
        }
    } catch {
        Write-Host "⚠ API started but health check failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n⚠ API is taking longer than expected to start" -ForegroundColor Yellow
    Write-Host "Check logs: docker-compose -f docker-compose.full.yml logs nl2sql-api" -ForegroundColor Yellow
}

# Check if we need to generate data
Write-Host "`nChecking database data..." -ForegroundColor Yellow
$userCount = docker exec nl2sql-mysql mysql -u root -padmin -D ecommerce -e "SELECT COUNT(*) FROM users" -s -N 2>$null

if ($userCount -eq "0" -or $null -eq $userCount) {
    Write-Host "No data found. Generating sample data..." -ForegroundColor Cyan
    
    # Install Python dependencies for data generation
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install mysql-connector-python faker --quiet
    
    # Update generate_data.py to use docker mysql
    Write-Host "Generating data..." -ForegroundColor Yellow
    $generateScript = Get-Content resources\data\generate_data.py -Raw
    $generateScript = $generateScript -replace "host='localhost'", "host='127.0.0.1'"
    $generateScript | Set-Content resources\data\generate_data_temp.py
    
    python resources\data\generate_data_temp.py
    Remove-Item resources\data\generate_data_temp.py
    
    Write-Host "[OK] Data generated" -ForegroundColor Green
} else {
    Write-Host "[OK] Database already has data ($userCount users)" -ForegroundColor Green
}

# Show summary
$separator = "=" * 70
Write-Host "`n$separator" -ForegroundColor Green
Write-Host "[OK] Setup Complete!" -ForegroundColor Green
Write-Host "$separator" -ForegroundColor Green

Write-Host "`nServices Running:" -ForegroundColor Cyan
Write-Host "  NL2SQL API:    http://localhost:8000" -ForegroundColor White
Write-Host "  Swagger Docs:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "  MySQL:         localhost:3306" -ForegroundColor White
Write-Host "  phpMyAdmin:    http://localhost:8080 (optional)" -ForegroundColor White

Write-Host "`nDatabase Info:" -ForegroundColor Cyan
Write-Host "  Host: localhost (or mysql from other containers)" -ForegroundColor White
Write-Host "  Port: 3306" -ForegroundColor White
Write-Host "  Database: ecommerce" -ForegroundColor White
Write-Host "  User: root" -ForegroundColor White
Write-Host "  Password: admin" -ForegroundColor White

Write-Host "`nTest Commands:" -ForegroundColor Cyan
Write-Host "  curl http://localhost:8000/health" -ForegroundColor White
Write-Host '  curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"message\": \"How many users?\", \"execute_query\": true}"' -ForegroundColor White

Write-Host "`nDocker Commands:" -ForegroundColor Cyan
Write-Host "  View logs (all):    docker-compose -f docker-compose.full.yml logs -f" -ForegroundColor White
Write-Host "  View logs (API):    docker-compose -f docker-compose.full.yml logs -f nl2sql-api" -ForegroundColor White
Write-Host "  View logs (MySQL):  docker-compose -f docker-compose.full.yml logs -f mysql" -ForegroundColor White
Write-Host "  Stop all:           docker-compose -f docker-compose.full.yml down" -ForegroundColor White
Write-Host "  Restart all:        docker-compose -f docker-compose.full.yml restart" -ForegroundColor White
Write-Host "  Start phpMyAdmin:   docker-compose -f docker-compose.full.yml --profile tools up -d" -ForegroundColor White

Write-Host "`nMySQL CLI:" -ForegroundColor Cyan
Write-Host "  docker exec -it nl2sql-mysql mysql -u root -padmin ecommerce" -ForegroundColor White

$separator = "=" * 70
Write-Host "`n$separator" -ForegroundColor Green
