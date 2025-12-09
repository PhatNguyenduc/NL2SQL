# 🔄 NL2SQL - Natural Language to SQL Converter

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

🚀 **High-Performance Backend API** chuyển đổi câu hỏi tiếng tự nhiên thành SQL queries với kiến trúc tối ưu, multi-layer caching, và hỗ trợ đa LLM providers.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         NL2SQL System                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  React   │───▶│ FastAPI  │───▶│  Redis   │───▶│  MySQL   │  │
│  │ Frontend │    │ Backend  │    │  Cache   │    │ Database │  │
│  │  :3000   │◀───│  :8000   │◀───│  :6379   │◀───│  :3307   │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                        │                                         │
│         ┌──────────────┼──────────────┐                         │
│         ▼              ▼              ▼                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                  │
│  │  Semantic  │ │Query Plan  │ │  General   │                  │
│  │   Cache    │ │   Cache    │ │   Cache    │                  │
│  │(Embedding) │ │ (Pattern)  │ │  (Redis)   │                  │
│  └────────────┘ └────────────┘ └────────────┘                  │
│                        │                                         │
│                        ▼                                         │
│        ┌─────────────────────────────────┐                      │
│        │      Multi-LLM Providers        │                      │
│        │  Gemini │ OpenAI │ Claude │ ... │                      │
│        └─────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

> 📚 **Chi tiết kiến trúc**: [docs/architecture.md](docs/architecture.md)

---

## ✨ Tính năng nổi bật

### 🚀 Performance Optimizations

- **3-Layer Caching**: Semantic Cache + Query Plan Cache + Redis
- **Async LLM Calls**: Non-blocking I/O, 4x throughput improvement
- **Connection Pooling**: Optimized database connections
- **Schema Optimization**: 60-70% token reduction

### 🤖 Intelligent SQL Generation

- **Multi-LLM Provider**: OpenAI, Gemini (FREE), OpenRouter, Claude, Azure
- **Auto-Fallback**: Tự động chuyển provider khi cần
- **SQL Execution Feedback**: Tự động retry với error context
- **Query Type Classification**: Optimize prompt per query type

### 📊 Monitoring & Analytics

- **Real-time Dashboard**: Query stats, cache performance, error analysis
- **Hourly Trends**: Visualize usage patterns
- **Confidence Tracking**: Monitor SQL generation quality

### 🛡️ Security & Reliability

- **Read-only Enforcement**: Chỉ SELECT queries
- **SQL Injection Prevention**: Multi-layer validation
- **Graceful Degradation**: Auto-recovery mechanisms

---

## ⚡ Performance Highlights

| Feature            | Improvement    | How                          |
| ------------------ | -------------- | ---------------------------- |
| **Cache Hit**      | ~50ms response | Semantic similarity matching |
| **Token Usage**    | -60-70%        | Schema optimization          |
| **Throughput**     | 4x             | Async LLM calls              |
| **Error Recovery** | Auto-fix       | SQL execution feedback       |

### Caching Strategy

```
Question: "How many users?"
         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: SEMANTIC CACHE                                      │
│ "Count all users" ≈ "How many users?" (similarity: 0.95)    │
│ → Return cached SQL instantly (~50ms)                        │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: QUERY PLAN CACHE                                    │
│ "Top 5 users" → TOP_N pattern template                      │
│ "Top 10 products" → Same template, different params         │
│ → Fill template without LLM call                            │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: GENERAL CACHE (Redis)                               │
│ Schema, prompts, execution results                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Technical Stack

| Component           | Technology                     | Purpose                        |
| ------------------- | ------------------------------ | ------------------------------ |
| **API Framework**   | FastAPI + Uvicorn              | High-performance async API     |
| **LLM Integration** | Instructor + httpx             | Structured output, async calls |
| **Database**        | MySQL 8.0 + SQLAlchemy         | Connection pooling, ORM        |
| **Caching**         | Redis 7 + In-memory            | Multi-layer caching            |
| **Embeddings**      | OpenAI / Sentence-Transformers | Semantic similarity            |
| **Frontend**        | React 18 + TypeScript + Vite   | Modern SPA with dark theme      |
| **UI Framework**   | Tailwind CSS + Custom CSS      | Responsive design, animations  |
| **Container**       | Docker Compose                 | Full stack deployment          |

---

## 🚀 Quick Start (5 phút)

### 1️⃣ Clone & Setup

```powershell
# Clone repository
git clone https://github.com/PhatNguyenduc/NL2SQL.git
cd NL2SQL

# Copy và config .env
copy .env.example .env
# Chỉnh sửa .env với API keys (xem bước 2)
```

### 2️⃣ Chọn LLM Provider

**Option A: Gemini (FREE - Recommended)** 🎁

```bash
# .env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here  # FREE tại: https://aistudio.google.com/apikey
```

**Option B: OpenAI**

```bash
# .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

**Option C: OpenRouter** (100+ models)

```bash
# .env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-your-key-here  # https://openrouter.ai/keys
```

> 📚 **Chi tiết providers**: Xem [docs/llm_providers.md](docs/llm_providers.md)

### 3️⃣ Chạy Full Stack với Docker

```bash
# Quick start (Linux/macOS)
./start.sh

# Quick start (Windows)
.\start.ps1

# Hoặc manual
docker-compose up -d --build
```

**✅ Script sẽ:**
- Kiểm tra Docker
- Validate API keys (auto fallback nếu cần)
- Start MySQL (port 3307), Redis (port 6379), API (port 8000), Frontend (port 3000)
- Import schema + Generate sample data (500 users, 1000 products, 2000 orders)
- Test health checks

**Services Ready:**

- 🎨 **React Frontend**: http://localhost:3000
- 🔗 **API**: http://localhost:8000
- 📖 **API Docs**: http://localhost:8000/docs
- 🗄️ **phpMyAdmin**: http://localhost:8080 (optional, use `--profile tools`)
- 💾 **MySQL**: localhost:3307 (root/admin)
- 💾 **Redis**: localhost:6379

### 4️⃣ Test API

**Option A: Use React UI** (Recommended)

Frontend React đã chạy tự động với Docker Compose tại **http://localhost:3000**

**Hoặc chạy local development:**

```bash
cd frontend
npm install
npm run dev
# App sẽ chạy tại http://localhost:3000
```

**Option B: Use cURL**

```powershell
# Health check
curl http://localhost:8000/health

# Chat với database (generate + execute)
curl -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{
    "message": "How many users do we have?",
    "execute_query": true
  }'

# Xem schema
curl http://localhost:8000/schema
```

**Response example:**

```json
{
  "session_id": "abc123",
  "sql_generation": {
    "query": "SELECT COUNT(*) AS user_count FROM users;",
    "confidence": 0.95,
    "explanation": "Counts total users in database"
  },
  "execution": {
    "success": true,
    "rows": [{ "user_count": 500 }],
    "row_count": 1
  }
}
```

---

## 📚 API Endpoints

### 🔹 Chat - Generate & Execute SQL

```http
POST /chat
```

**Request:**

```json
{
  "message": "Show me top 10 products by sales",
  "execute_query": true,
  "session_id": "optional-session-id",
  "temperature": 0.1
}
```

**Response:**

```json
{
  "session_id": "abc123",
  "sql_generation": {
    "query": "SELECT p.product_name, SUM(oi.quantity) as total_sales\nFROM products p\nJOIN order_items oi ON p.product_id = oi.product_id\nGROUP BY p.product_id, p.product_name\nORDER BY total_sales DESC\nLIMIT 10;",
    "confidence": 0.92,
    "explanation": "Joins products with order_items, aggregates sales, returns top 10"
  },
  "execution": {
    "success": true,
    "rows": [
      { "product_name": "iPhone 14", "total_sales": 245 },
      { "product_name": "MacBook Pro", "total_sales": 189 }
    ],
    "row_count": 10,
    "execution_time": 0.023
  }
}
```

### 🔹 Batch Processing

```http
POST /chat/batch
```

**Request:**

```json
{
  "messages": [
    "How many users?",
    "Show top 5 categories",
    "Average order value"
  ],
  "execute_queries": true,
  "session_id": "batch-session"
}
```

### 🔹 Schema Info

```http
GET /schema
```

Returns database structure (24 tables: users, products, orders, etc.)

### 🔹 Conversation History

```http
POST /conversation/history
```

```json
{
  "session_id": "abc123",
  "limit": 50
}
```

### 🔹 Health Check

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "database_connected": true,
  "llm_provider": "gemini",
  "llm_model": "gemini-1.5-flash",
  "tables": 24
}
```

> 📖 **Full API Docs**: http://localhost:8000/docs (Swagger UI)

---

## 🎯 Ví dụ Queries

### Aggregations

```
"How many users do we have?"
"What's the average order value?"
"Total revenue this month"
```

### Filtering

```
"Show users registered after 2024-01-01"
"Products with price above $100"
"Orders with status 'delivered'"
```

### Joins

```
"Show orders with customer names"
"Products with their categories"
"Users with their order history"
```

### Sorting & Limiting

```
"Top 10 customers by spending"
"Latest 20 orders"
"5 most expensive products"
```

### Grouping

```
"Revenue by month"
"Order count by status"
"Average rating per product category"
```

---

## 🔧 Cấu hình

### Environment Variables (.env)

```bash
# ============================================
# LLM Provider Configuration
# ============================================
LLM_PROVIDER=gemini              # openai | gemini | openrouter | anthropic | azure_openai

# Gemini (FREE)
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-1.5-flash

# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

# OpenRouter
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_MODEL=openai/gpt-4o-mini

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Advanced LLM Settings
LLM_TEMPERATURE=0.1
LLM_MAX_RETRIES=3
LLM_TIMEOUT=30

# ============================================
# Database Configuration
# ============================================
DATABASE_URL=mysql+pymysql://root:admin@mysql:3306/ecommerce

# ============================================
# Server Configuration
# ============================================
HOST=0.0.0.0
PORT=8000
DEFAULT_LIMIT=100
LOG_LEVEL=INFO
CORS_ORIGINS=*
```

---

## 🐳 Docker Commands

```bash
# Quick start (recommended)
./start.sh          # Linux/macOS
.\start.ps1         # Windows

# Hoặc manual commands:
docker-compose -f docker-compose.full.yml up -d --build
docker-compose -f docker-compose.full.yml logs -f
docker-compose -f docker-compose.full.yml down

# Restart services
docker-compose -f docker-compose.full.yml restart

# Restart chỉ API (sau khi đổi LLM provider)
docker-compose -f docker-compose.full.yml restart nl2sql-api

# MySQL CLI
docker exec -it nl2sql-mysql mysql -u root -padmin ecommerce
```

---

## 💻 Local Development (không dùng Docker)

```powershell
# 1. Cài đặt dependencies
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Setup MySQL (riêng biệt)
# - Cài MySQL 8.0
# - Import resources/data/ecommerce_schema.sql
# - Run resources/data/generate_data.py

# 3. Config .env
DATABASE_URL=mysql+pymysql://root:admin@localhost:3307/ecommerce
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here

# 4. Run API server
python main.py

# Server chạy tại: http://localhost:8000
```

---

## 📊 Database Schema

**24 Tables** trong `ecommerce` database:

### Core Tables

- `users` - User accounts (500 records)
- `products` - Products catalog (1000 records)
- `categories` - Product categories (30 records)
- `brands` - Product brands (50 records)

### Orders

- `orders` - Order headers (2000 records)
- `order_items` - Order line items
- `order_addresses` - Shipping/billing addresses
- `order_status_history` - Status changes
- `transactions` - Payment transactions
- `shipments` - Shipping info

### Product Management

- `product_variants` - Product variations (size, color)
- `product_images` - Product images
- `product_attributes` - Custom attributes
- `variant_attributes` - Variant-specific attributes
- `product_categories` - Many-to-many relation
- `inventory` - Stock levels

### Customer Features

- `user_addresses` - Saved addresses
- `shopping_carts` - Active carts
- `cart_items` - Cart contents
- `product_reviews` - Reviews & ratings
- `wishlists` - Wishlist items

### Marketing

- `coupons` - Discount coupons
- `coupon_usage` - Coupon redemptions

### Configuration

- `payment_methods` - Payment options
- `shipping_methods` - Shipping options

> 📄 **Full schema**: `resources/data/ecommerce_schema.sql`

---

## 🤖 Multi-LLM Provider Support

### Supported Providers

| Provider         | Free Tier       | Cost     | Best For                 |
| ---------------- | --------------- | -------- | ------------------------ |
| **Gemini**       | ✅ 1500 req/day | FREE     | Development, learning    |
| **OpenRouter**   | ✅ Some models  | $ - $$$  | Access to 100+ models    |
| **OpenAI**       | $5 credit       | $$$      | Production, best quality |
| **Claude**       | $5 credit       | $$ - $$$ | Complex reasoning        |
| **Azure OpenAI** | ❌ None         | $$$      | Enterprise, compliance   |

### Auto Fallback Logic

```
1. Đọc LLM_PROVIDER từ .env
2. Nếu không set hoặc key invalid:
   → Try Gemini (FREE)
   → Try OpenAI
   → Try OpenRouter
   → Error nếu không có key nào
3. Validate API key format
4. Initialize client
```

### Switching Providers

```powershell
# Chỉnh .env
LLM_PROVIDER=gemini

# Restart API
docker-compose -f docker-compose.full.yml restart nl2sql-api

# Hoặc local:
python main.py
```

> 📚 **Provider details**: [docs/llm_providers.md](docs/llm_providers.md)

---

## 🛡️ Security & Safety

### ✅ Implemented

- **Read-only**: Chỉ cho phép `SELECT` queries
- **Query validation**: Block INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.
- **SQL injection prevention**: Parameterized queries
- **Auto LIMIT**: Thêm LIMIT tự động nếu thiếu
- **Input validation**: Pydantic models cho mọi input
- **Error handling**: Graceful error messages, không expose internals

### ⚠️ Production Recommendations

- **Authentication**: Thêm API keys hoặc JWT
- **Rate limiting**: Giới hạn requests/IP
- **HTTPS**: Sử dụng reverse proxy (Nginx/Traefik)
- **Monitoring**: Setup logging và alerts
- **Backup**: Regular database backups

---

## 📁 Project Structure

```
NL2SQL/
├── main.py                          # FastAPI entry point + Analytics
├── docker-compose.yml               # Full stack Docker config
├── Dockerfile                       # API container image
├── requirements.txt                 # Python dependencies
│
├── src/
│   ├── api/
│   │   └── models.py               # API request/response models (Pydantic)
│   │
│   ├── services/
│   │   ├── chat_service.py         # Chat logic + SQL Execution Feedback
│   │   └── async_chat_service.py   # Async version for high throughput
│   │
│   ├── core/                        # 🔧 CORE COMPONENTS
│   │   ├── converter.py            # Main NL2SQL converter pipeline
│   │   ├── async_converter.py      # Async version (4x throughput)
│   │   ├── llm_provider.py         # Multi-LLM adapter (5 providers)
│   │   ├── schema_extractor.py     # DB schema analysis
│   │   ├── schema_optimizer.py     # Token reduction (60-70%)
│   │   ├── query_executor.py       # Safe SQL execution
│   │   ├── query_preprocessor.py   # Query classification
│   │   ├── sql_validator.py        # SQL validation + post-processing
│   │   ├── prompt_builder.py       # Optimized prompt construction
│   │   │
│   │   ├── cache_manager.py        # General Redis cache
│   │   ├── semantic_cache.py       # Embedding-based cache (Layer 1)
│   │   ├── query_plan_cache.py     # Pattern-based cache (Layer 2)
│   │   ├── embedding_provider.py   # Embedding generation
│   │   └── schema_version_manager.py # Cache invalidation
│   │
│   ├── prompts/
│   │   ├── system_prompt.py        # LLM system prompts
│   │   └── few_shot_examples.py    # Example queries
│   │
│   └── models/
│       └── sql_query.py            # Core data models
│
├── frontend/
│   ├── src/
│   │   ├── home.tsx                # Main chat UI component
│   │   ├── components/
│   │   │   └── Analytics.tsx       # Analytics dashboard
│   │   ├── api/
│   │   │   └── client.ts           # API client & types
│   │   ├── main.tsx                # App entry point
│   │   └── index.css               # Styles & animations
│   ├── Dockerfile                  # Frontend container (Nginx)
│   ├── package.json                # Node dependencies
│   └── vite.config.ts              # Build configuration
│
├── docs/
│   ├── architecture.md             # 🏗️ Technical deep-dive
│   └── llm_providers.md            # LLM provider guide
│
└── resources/
    └── data/
        ├── ecommerce_schema.sql    # MySQL schema (24 tables)
        └── seed.py                 # Sample data generator
```

---

## 🔬 Key Technical Decisions

### 1. Why Multi-Layer Caching?

```
Problem: LLM calls are expensive ($) and slow (2-10s)
Solution: 3-layer cache hierarchy

Layer 1 - Semantic Cache:
  "How many users?" ≈ "Count all users"
  → Same meaning, different words
  → Use embeddings to find similar questions
  → Return cached SQL (saves LLM call)

Layer 2 - Query Plan Cache:
  "Top 5 users by orders" → TOP_N pattern
  "Top 10 products by sales" → Same pattern!
  → Extract pattern, fill template
  → No LLM needed for common patterns

Layer 3 - General Cache:
  → Schema, prompts, results in Redis
  → Fast key-value lookup
```

### 2. Why Instructor for LLM?

```python
# Without Instructor (error-prone):
response = client.chat.completions.create(...)
try:
    data = json.loads(response.content)
    sql = data.get("query", "")  # Might fail!
except: ...

# With Instructor (guaranteed structure):
response = client.chat.completions.create(
    response_model=SQLQuery,  # Pydantic model
    ...
)
# response.query, response.confidence always exist!
```

### 3. Why SQL Execution Feedback?

```
Problem: LLM generates valid-looking SQL but fails on execution

Example:
  Input: "Top 5 users this month AND last month"
  LLM Output: SELECT ... ORDER BY x LIMIT 5 UNION ALL SELECT ...
  MySQL Error: Syntax error near 'UNION'

Solution - Feedback Loop:
  1. Execute SQL
  2. If error → Send error message back to LLM
  3. LLM corrects: (SELECT ... LIMIT 5) UNION ALL (SELECT ... LIMIT 5)
  4. Retry (max 2 times)
```

### 4. Why Schema Optimization?

```
Problem: 24 tables × 10 columns = 240 items → Too many tokens

Solution:
  1. Compact format: table.column (no data types when not needed)
  2. Relevant filtering: Only include tables mentioned in question
  3. FK mapping: Help LLM understand JOINs

Result: 60-70% token reduction → Faster + Cheaper
```

---

## 🧪 Testing

```powershell
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_converter.py -v

# Integration tests (requires DB + API key)
$env:DATABASE_URL="mysql+pymysql://root:admin@localhost:3307/ecommerce"
$env:LLM_PROVIDER="gemini"
$env:GEMINI_API_KEY="your-key"
pytest tests/ -m integration
```

---

## 🤝 Contributing

Contributions are welcome! 🎉

1. Fork repository
2. Create feature branch: `git checkout -b feature/AmazingFeature`
3. Commit changes: `git commit -m 'Add AmazingFeature'`
4. Push to branch: `git push origin feature/AmazingFeature`
5. Open Pull Request

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **OpenAI** - GPT models
- **Google** - Gemini models (FREE tier!)
- **Anthropic** - Claude models
- **OpenRouter** - Multi-model access
- **FastAPI** - Modern web framework
- **instructor** - Structured LLM outputs
- **SQLAlchemy** - Database ORM

---

## 📞 Support

- 📧 Email: phatnguyen@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/PhatNguyenduc/NL2SQL/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/PhatNguyenduc/NL2SQL/discussions)

---

## 🗺️ Roadmap

- [x] ~~Multi-LLM Provider Support~~
- [x] ~~Multi-Layer Caching (Semantic + Query Plan)~~
- [x] ~~Analytics Dashboard~~
- [x] ~~SQL Execution Feedback Loop~~
- [x] ~~Async High-Performance Endpoints~~
- [ ] Support for PostgreSQL
- [ ] CLI interface
- [ ] Query optimization suggestions
- [ ] Multi-language support (Vietnamese NLP)
- [ ] Export to CSV/Excel
- [ ] Query templates library
- [ ] User authentication & permissions

---

## 📊 Monitoring & Analytics

Access the **Analytics Dashboard** at http://localhost:3000 (click 📊 Analytics in sidebar)

**Available Metrics:**

- Query statistics (total, success rate, errors)
- Response time distribution
- Cache hit rates (semantic vs LLM calls)
- Table usage frequency
- Confidence score distribution
- Hourly query trends
- Error type analysis

**API Endpoints:**

```http
GET /analytics/dashboard     # Full analytics data
GET /monitoring/cache/all    # All cache statistics
GET /health                  # System health check
```

---

⭐ **If you find this project useful, please give it a star!**

Made with ❤️ by [PhatNguyenduc](https://github.com/PhatNguyenduc)
