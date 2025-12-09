# 🚀 NL2SQL Quick Start Guide

## Prerequisites

- Docker & Docker Compose
- API key for one of: OpenAI, Gemini, Anthropic, or OpenRouter

---

## 1️⃣ Setup Environment

```bash
# Clone repository
git clone <your-repo-url>
cd NL2SQL

# Create .env file
cp .env.example .env

# Edit .env and add your API key
nano .env  # or use any text editor
```

### Example .env Configuration

**For Gemini (FREE):**
```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key-here
```

**For OpenAI:**
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key-here
```

---

## 2️⃣ Start All Services

```bash
# Build and start: MySQL, Redis, API, Frontend
docker-compose up -d --build

# Wait for all services to be healthy (~60 seconds)
docker-compose ps
```

Expected output:
```
NAME                 STATUS              PORTS
nl2sql-api           Up (healthy)        0.0.0.0:8000->8000/tcp
nl2sql-frontend      Up (healthy)        0.0.0.0:3000->80/tcp
nl2sql-mysql         Up (healthy)        0.0.0.0:3307->3306/tcp
nl2sql-redis         Up (healthy)        0.0.0.0:6379->6379/tcp
nl2sql-seed          Exited (0)
```

---

## 3️⃣ Access the Application

### React Frontend (Main UI)
🎨 **http://localhost:3000**

Features:
- 💬 Chat interface with natural language
- 🔍 Search & highlight in tables
- 📊 Analytics dashboard
- 📥 Download results as CSV
- 🎨 Modern dark theme UI

### API Documentation
📖 **http://localhost:8000/docs**

Interactive Swagger UI to test API endpoints directly.

### Database Management (Optional)
🗄️ **http://localhost:8080**

phpMyAdmin for direct database access (if enabled with `--profile tools`)

---

## 4️⃣ Try Sample Queries

Open http://localhost:3000 and try:

- "How many users do we have?"
- "Show me top 10 products by sales"
- "What's the average order value?"
- "List orders placed in the last 7 days"
- "Users who never placed an order"

---

## 🛠️ Useful Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f nl2sql-api
docker-compose logs -f frontend
```

### Restart Services
```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart nl2sql-api
```

### Stop Services
```bash
# Stop all
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### Check Service Status
```bash
docker-compose ps
```

### Access Database Directly
```bash
# MySQL CLI
docker exec -it nl2sql-mysql mysql -uroot -padmin ecommerce

# Or use phpMyAdmin
docker-compose --profile tools up -d phpmyadmin
# Then visit http://localhost:8080
```

---

## 🐛 Troubleshooting

### API not starting
```bash
# Check if .env has correct API key
cat .env | grep API_KEY

# View API logs
docker-compose logs nl2sql-api
```

### Frontend shows "API Disconnected"
```bash
# Check API health
curl http://localhost:8000/health

# Ensure API is healthy
docker-compose ps nl2sql-api
```

### Port already in use
```bash
# Change ports in docker-compose.yml
ports:
  - "3001:80"  # Frontend (change 3000 to 3001)
  - "8001:8000"  # API (change 8000 to 8001)
```

### MySQL connection refused
```bash
# Wait for MySQL to be ready
docker-compose logs mysql

# Check if seed completed
docker-compose ps seed
```

---

## 🔄 Development Workflow

### Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Start dev server (with hot reload)
npm run dev

# App will run at http://localhost:3000
# with proxy to API at http://localhost:8000
```

### Backend Development
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run API locally
python main.py

# API will run at http://localhost:8000
```

---

## 📦 What Gets Created

When you run `docker-compose up -d --build`:

1. **MySQL Database** with sample ecommerce data:
   - ~500 users
   - ~1000 products
   - ~2000 orders
   - Categories, reviews, etc.

2. **Redis Cache** for performance optimization

3. **FastAPI Backend** with:
   - LLM integration
   - Multi-layer caching
   - Analytics tracking

4. **React Frontend** with:
   - Modern UI
   - Real-time chat
   - Analytics dashboard
   - Search & export features

---

## 🎯 Next Steps

1. ✅ Explore the Chat interface
2. ✅ Try different query types
3. ✅ Check Analytics dashboard
4. ✅ Download query results
5. 📚 Read [Architecture docs](docs/architecture.md)
6. 🔧 Customize for your database schema

---

Happy coding! 🎉

