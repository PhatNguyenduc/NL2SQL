#!/bin/bash

# NL2SQL Quick Start Script
# This script starts all services using Docker Compose

set -e

echo "🚀 Starting NL2SQL Services..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Creating .env from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file"
        echo ""
        echo "📝 Please edit .env and add your API keys:"
        echo "   nano .env"
        echo ""
        read -p "Press Enter after you've configured .env..."
    else
        echo "❌ Error: .env.example not found"
        exit 1
    fi
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

echo "🐳 Docker is running"
echo ""

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down 2>/dev/null || true
echo ""

# Build and start services
echo "🏗️  Building and starting services..."
echo "This may take a few minutes on first run..."
echo ""

docker-compose up -d --build

echo ""
echo "⏳ Waiting for services to be healthy..."
echo ""

# Wait for services
sleep 10

# Check status
echo "📊 Service Status:"
docker-compose ps
echo ""

# Display access information
echo "✅ NL2SQL is ready!"
echo ""
echo "🌐 Access Points:"
echo "   • React Frontend:  http://localhost:3000"
echo "   • API Backend:     http://localhost:8000"
echo "   • API Docs:        http://localhost:8000/docs"
echo "   • MySQL:           localhost:3307 (user: root, password: admin)"
echo "   • Redis:           localhost:6379"
echo ""
echo "📝 Useful commands:"
echo "   • View logs:       docker-compose logs -f"
echo "   • Stop services:   docker-compose down"
echo "   • Restart:         docker-compose restart"
echo ""
echo "💬 Open http://localhost:3000 to start chatting with your database!"

