# NL2SQL Quick Start Script (PowerShell)
# This script starts all services using Docker Compose

Write-Host "🚀 Starting NL2SQL Services..." -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  Warning: .env file not found" -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ Created .env file" -ForegroundColor Green
        Write-Host ""
        Write-Host "📝 Please edit .env and add your API keys:" -ForegroundColor Cyan
        Write-Host "   notepad .env"
        Write-Host ""
        Read-Host "Press Enter after you've configured .env"
    } else {
        Write-Host "❌ Error: .env.example not found" -ForegroundColor Red
        exit 1
    }
}

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "🐳 Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Docker is not running" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again"
    exit 1
}
Write-Host ""

# Stop existing containers
Write-Host "🛑 Stopping existing containers..." -ForegroundColor Yellow
docker-compose down 2>$null
Write-Host ""

# Build and start services
Write-Host "🏗️  Building and starting services..." -ForegroundColor Cyan
Write-Host "This may take a few minutes on first run..." -ForegroundColor Gray
Write-Host ""

docker-compose up -d --build

Write-Host ""
Write-Host "⏳ Waiting for services to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
Write-Host ""

# Check status
Write-Host "📊 Service Status:" -ForegroundColor Cyan
docker-compose ps
Write-Host ""

# Display access information
Write-Host "✅ NL2SQL is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Access Points:" -ForegroundColor Cyan
Write-Host "   • React Frontend:  http://localhost:3000" -ForegroundColor White
Write-Host "   • API Backend:     http://localhost:8000" -ForegroundColor White
Write-Host "   • API Docs:        http://localhost:8000/docs" -ForegroundColor White
Write-Host "   • MySQL:           localhost:3307 (user: root, password: admin)" -ForegroundColor White
Write-Host "   • Redis:           localhost:6379" -ForegroundColor White
Write-Host ""
Write-Host "📝 Useful commands:" -ForegroundColor Cyan
Write-Host "   • View logs:       docker-compose logs -f" -ForegroundColor Gray
Write-Host "   • Stop services:   docker-compose down" -ForegroundColor Gray
Write-Host "   • Restart:         docker-compose restart" -ForegroundColor Gray
Write-Host ""
Write-Host "💬 Open http://localhost:3000 to start chatting with your database!" -ForegroundColor Green

