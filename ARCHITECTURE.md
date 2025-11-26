# NL2SQL System Architecture

## 🎯 Overview

NL2SQL là một hệ thống chuyển đổi câu hỏi ngôn ngữ tự nhiên (Natural Language) thành câu truy vấn SQL. Hệ thống hỗ trợ đa LLM provider và tối ưu hóa cho cả tiếng Việt và tiếng Anh.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NL2SQL System                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Frontend   │───▶│   FastAPI    │───▶│   Database   │                   │
│  │  (Streamlit) │    │   Backend    │    │   (MySQL)    │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│         │                   │                                                │
│         │                   ▼                                                │
│         │           ┌──────────────┐                                         │
│         │           │  LLM Provider│                                         │
│         │           │  (Multi-LLM) │                                         │
│         │           └──────────────┘                                         │
│         │                   │                                                │
│         ▼                   ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Core Processing Pipeline                         │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │    │
│  │  │Preproc- │─▶│ Schema  │─▶│   LLM   │─▶│  SQL    │─▶│  Post-  │   │    │
│  │  │essor    │  │Optimizer│  │Generate │  │Validator│  │Process  │   │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
NL2SQL/
├── src/
│   ├── api/                    # FastAPI endpoints
│   │   ├── models.py          # Pydantic models (request/response)
│   │   └── __init__.py
│   │
│   ├── core/                   # Core business logic
│   │   ├── converter.py       # Main NL2SQL converter (orchestrator)
│   │   ├── llm_provider.py    # Multi-LLM provider adapter
│   │   ├── query_executor.py  # SQL execution engine
│   │   ├── query_preprocessor.py  # Question preprocessing & classification
│   │   ├── schema_extractor.py    # Database schema extraction
│   │   ├── schema_optimizer.py    # Schema optimization for LLM
│   │   ├── sql_validator.py       # SQL validation & post-processing
│   │   ├── cache_manager.py       # Redis-based multi-level caching
│   │   ├── prompt_builder.py      # Prompt building with caching
│   │   ├── semantic_cache.py      # Semantic SQL caching
│   │   └── schema_version_manager.py  # Schema versioning for cache invalidation
│   │
│   ├── models/                 # Data models
│   │   └── sql_query.py       # SQLQuery, DatabaseSchema, etc.
│   │
│   ├── prompts/                # LLM prompts
│   │   ├── system_prompt.py   # System prompts with planning
│   │   └── few_shot_examples.py   # Few-shot learning examples
│   │
│   ├── services/               # Application services
│   │   └── chat_service.py    # Chat session management
│   │
│   ├── utils/                  # Utility functions
│   │   ├── validation.py      # Query validation
│   │   └── formatting.py      # SQL formatting
│   │
│   └── cli.py                  # Command-line interface
│
├── frontend/                   # Streamlit UI
│   ├── streamlit_app.py       # Main Streamlit app
│   ├── Dockerfile             # Frontend Docker image
│   └── requirements.txt
│
├── main.py                     # FastAPI application entry
├── docker-compose.full.yml     # Full stack Docker setup (MySQL + Redis + API + Frontend)
├── Dockerfile                  # Backend Docker image
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables
```

---

## 🧩 Core Components

### 1. **NL2SQLConverter** (`src/core/converter.py`)

Orchestrator chính điều phối toàn bộ quá trình chuyển đổi NL → SQL.

```python
class NL2SQLConverter:
    def __init__(self, connection_string, database_type, llm_config, ...)
    def generate_sql(self, question, temperature, conversation_history, ...) -> SQLQuery
    def _is_schema_query(self, question) -> bool  # Detect metadata queries
    def _self_correct_query(self, ...) -> SQLQuery  # Auto-fix failed queries
```

**Flow:**

```
Question → Preprocess → Schema Optimize → LLM Generate → Validate → Post-process → SQLQuery
```

### 2. **QueryPreprocessor** (`src/core/query_preprocessor.py`)

Tiền xử lý câu hỏi với hỗ trợ tiếng Việt.

```python
class QueryPreprocessor:
    def process(self, question) -> ProcessedQuery
    def _normalize_text(self, text) -> str        # Vietnamese → English
    def _classify_query(self, text) -> QueryType  # LOOKUP, AGGREGATION, JOIN, etc.
    def _extract_entities(self, text) -> List[str]
    def _extract_time_references(self, text) -> List[str]
```

**Query Types:**

- `LOOKUP` - Simple SELECT
- `AGGREGATION` - COUNT, SUM, AVG
- `JOIN` - Multi-table queries
- `GROUPBY` - GROUP BY queries
- `RANKING` - TOP N, ORDER BY
- `FILTER` - Complex WHERE
- `NESTED` - Subqueries
- `SCHEMA` - Metadata questions

**Vietnamese Support:**

```python
VIETNAMESE_SYNONYMS = {
    "tổng": "sum total",
    "đếm": "count",
    "khách hàng": "customer",
    "doanh thu": "revenue",
    "tháng trước": "last month",
    ...
}
```

### 3. **SchemaOptimizer** (`src/core/schema_optimizer.py`)

Tối ưu hóa schema để giảm token consumption.

```python
class SchemaOptimizer:
    def format_compact_schema(self) -> str        # One-line per table format
    def get_relevant_tables(self, question) -> List[TableSchema]
    def get_join_path(self, table1, table2) -> List[Dict]
```

**Compact Format:**

```
## Sales & Orders
orders(*order_id, customer_id, total_amount, order_date)
order_items(*id, order_id, product_id, quantity, price)

## Relationships (JOIN keys)
orders.customer_id → customers.customer_id
order_items.product_id → products.product_id
```

### 4. **SQLValidator** (`src/core/sql_validator.py`)

Validate SQL và enforce best practices.

```python
class SQLValidator:
    def validate(self, sql) -> ValidationResult
    def _check_dangerous_operations(self, sql)     # Block DROP, DELETE, etc.
    def _validate_tables(self, tables)             # Check table existence
    def _validate_columns(self, columns, tables)   # Check column existence
    def _check_join_conditions(self, sql, tables)  # Detect cartesian products
    def generate_error_feedback(self, result) -> str  # For self-correction
```

**Validation Checks:**

- ❌ Invalid table/column names
- ❌ Dangerous operations (DROP, DELETE, UPDATE)
- ⚠️ Missing LIMIT on SELECT \*
- ⚠️ Implicit JOINs (comma-separated)
- ⚠️ Potential cartesian products

### 5. **SQLPostProcessor** (`src/core/sql_validator.py`)

Post-processing SQL để enforce best practices.

```python
class SQLPostProcessor:
    def process(self, sql) -> str
    def _ensure_limit(self, sql) -> str           # Add LIMIT if missing
    def _clean_whitespace(self, sql) -> str       # Format SQL
```

### 6. **LLMProvider** (`src/core/llm_provider.py`)

Multi-LLM adapter hỗ trợ nhiều providers.

```python
class LLMProvider(Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"

def get_llm_client(config: LLMConfig) -> instructor.Instructor
```

**Supported Models:**
| Provider | Models |
|----------|--------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-3.5-turbo |
| Gemini | gemini-2.5-flash, gemini-2.5-pro |
| OpenRouter | Any model via OpenRouter |
| Anthropic | claude-3.5-sonnet, claude-3-opus |
| Azure OpenAI | Any Azure deployment |

---

## 🔄 Processing Pipeline

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         SQL Generation Pipeline                           │
└───────────────────────────────────────────────────────────────────────────┘

1. INPUT
   └── User Question: "Tổng doanh thu tháng này theo khách hàng"

2. PREPROCESSING (QueryPreprocessor)
   ├── Normalize Vietnamese: "total revenue this month by customer"
   ├── Classify: GROUPBY + AGGREGATION
   ├── Extract entities: [customers, orders, revenue]
   └── Extract time: ["this month"]

3. SCHEMA OPTIMIZATION (SchemaOptimizer)
   ├── Get relevant tables: [customers, orders]
   ├── Format compact schema
   └── Include JOIN relationships

4. PROMPT BUILDING
   ├── System prompt with:
   │   ├── Compact schema
   │   ├── Step-by-step planning instructions
   │   ├── Query type hints (GROUPBY)
   │   ├── Anti-hallucination guardrails
   │   └── Few-shot examples
   └── User prompt with question

5. LLM GENERATION
   ├── Send to LLM (Gemini/OpenAI/etc.)
   └── Receive structured SQLQuery response

6. VALIDATION (SQLValidator)
   ├── Check table/column existence
   ├── Check for dangerous operations
   ├── Detect potential issues
   └── If invalid → SELF-CORRECTION LOOP

7. SELF-CORRECTION (if needed)
   ├── Generate error feedback
   ├── Send to LLM for correction
   ├── Validate corrected query
   └── Max 2 retries

8. POST-PROCESSING (SQLPostProcessor)
   ├── Ensure LIMIT clause
   ├── Format SQL
   └── Clean whitespace

9. OUTPUT
   └── SQLQuery {
         query: "SELECT c.name, SUM(o.total) ...",
         explanation: "Tính tổng doanh thu...",
         confidence: 0.95,
         tables_used: ["customers", "orders"],
         potential_issues: []
       }
```

---

## 🌐 API Endpoints

### FastAPI Backend (`main.py`)

```
POST /chat              # Main chat endpoint
POST /query             # Direct SQL generation
POST /execute           # Execute SQL query
GET  /schema            # Get database schema
GET  /health            # Health check
GET  /providers         # List LLM providers
```

### Request/Response Models

```python
# Chat Request
{
    "message": "Show me top 10 customers",
    "session_id": "session-abc123",
    "execute_query": true,
    "temperature": 0.1
}

# Chat Response
{
    "session_id": "session-abc123",
    "message_id": "msg-xyz789",
    "sql": {
        "query": "SELECT * FROM customers LIMIT 10",
        "explanation": "...",
        "confidence": 0.95,
        "tables_used": ["customers"]
    },
    "execution": {
        "success": true,
        "rows": [...],
        "row_count": 10
    }
}
```

---

## 🐳 Docker Architecture

```yaml
services:
  redis: # Cache (port 6379)
  mysql: # Database (port 3307)
  nl2sql-api: # FastAPI backend (port 8000)
  frontend: # Streamlit UI (port 8501)
  phpmyadmin: # DB admin (port 8080, optional)
```

### Service Dependencies

```
redis ──────────────┐
                    │
mysql ──────────────┼───▶ nl2sql-api ◄───── LLM APIs (external)
                    │         │
                    └─────────│
                              ▼
                          frontend
```

---

## 🗄️ Prompt Caching System

NL2SQL sử dụng multi-level caching để giảm token consumption và tăng tốc độ response.

### Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           Caching Architecture                              │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                  │
│   │   Schema    │────▶│   Prompt    │────▶│   Semantic  │                  │
│   │   Version   │     │   Builder   │     │    Cache    │                  │
│   │   Manager   │     │  (Cached)   │     │   (SQL)     │                  │
│   └─────────────┘     └─────────────┘     └─────────────┘                  │
│          │                   │                   │                          │
│          └───────────────────┼───────────────────┘                          │
│                              ▼                                              │
│                      ┌─────────────┐                                        │
│                      │    Redis    │                                        │
│                      │    Cache    │                                        │
│                      └─────────────┘                                        │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Cache Levels

| Level    | TTL     | Purpose                |
| -------- | ------- | ---------------------- |
| SYSTEM   | 2 hours | System prompts         |
| SCHEMA   | 1 hour  | Database schema        |
| EXAMPLES | 1 hour  | Few-shot examples      |
| PROMPT   | 30 min  | Built prompts          |
| SQL      | 10 min  | Generated SQL results  |
| SEMANTIC | 30 min  | Semantic query matches |

### Components

#### **1. SchemaVersionManager** (`src/core/schema_version_manager.py`)

Quản lý versioning schema để invalidate cache khi schema thay đổi.

```python
class SchemaVersionManager:
    def compute_schema_hash(self, schema) -> str    # SHA256 hash của schema
    def update_schema(self, schema) -> bool         # Update và check changes
    def get_current_version(self) -> str            # Current version hash
```

#### **2. CacheManager** (`src/core/cache_manager.py`)

Multi-level cache với Redis backend.

```python
class CacheManager:
    def set(self, key, value, level, ttl) -> bool
    def get(self, key, level) -> Optional[Any]
    def invalidate_level(self, level) -> int
    def get_metrics() -> Dict                       # Hit rate, memory, etc.
    def health_check() -> Dict                      # Redis connection status
```

#### **3. PromptBuilder** (`src/core/prompt_builder.py`)

Build prompts với caching cho static parts.

```python
class PromptBuilder:
    def build_cached_components(self, ...) -> CachedPromptComponents
    def build_prompt(self, question, ...) -> BuiltPrompt
```

**Cached Components:**

- System prompt (static)
- Schema text (per version)
- Few-shot examples (per query type)

#### **4. SemanticSQLCache** (`src/core/semantic_cache.py`)

Cache SQL results với semantic matching.

```python
class SemanticSQLCache:
    def cache_sql(self, question, sql, ...) -> bool
    def get_sql(self, question, ...) -> Optional[Tuple[CachedSQLEntry, float]]
```

**Features:**

- Exact match với hash lookup
- Semantic similarity (Jaccard + keyword matching)
- Similarity threshold: 0.85 (configurable)
- Query normalization cho Vietnamese

### Cache Flow

```
Question arrives
       │
       ▼
┌──────────────────┐    Yes    ┌─────────────────┐
│ Check Semantic   │─────────▶ │ Return Cached   │
│ SQL Cache        │           │ SQL (similarity)│
└──────────────────┘           └─────────────────┘
       │ No
       ▼
┌──────────────────┐    Yes    ┌─────────────────┐
│ Check Prompt     │─────────▶ │ Use Cached      │
│ Components Cache │           │ Prompt Parts    │
└──────────────────┘           └─────────────────┘
       │ No
       ▼
┌──────────────────┐
│ Build Fresh      │
│ Prompt & Cache   │
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ Call LLM         │
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ Cache SQL Result │
└──────────────────┘
```

### Monitoring Endpoints

```
GET  /monitoring/cache/metrics      # Cache hit rates, memory
GET  /monitoring/cache/health       # Redis connection status
POST /monitoring/cache/invalidate   # Clear caches
GET  /monitoring/schema/version     # Current schema version
POST /monitoring/schema/reload      # Reload schema, invalidate cache
```

### Configuration

```bash
# Redis
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true

# TTLs (seconds)
CACHE_TTL_SCHEMA=3600      # 1 hour
CACHE_TTL_PROMPT=1800      # 30 minutes
CACHE_TTL_SQL=600          # 10 minutes

# Semantic cache
CACHE_SEMANTIC_THRESHOLD=0.85
```

---

## 🔧 Configuration

### Environment Variables

```bash
# LLM Provider
LLM_PROVIDER=gemini              # openai, gemini, openrouter, anthropic
LLM_TEMPERATURE=0.1
LLM_MAX_RETRIES=3
LLM_TIMEOUT=30

# Provider API Keys
GEMINI_API_KEY=xxx
OPENAI_API_KEY=xxx
OPENROUTER_API_KEY=xxx
ANTHROPIC_API_KEY=xxx

# Database
DATABASE_URL=mysql+pymysql://root:admin@mysql:3306/ecommerce
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Server
HOST=0.0.0.0
PORT=8000
DEFAULT_LIMIT=100
MAX_RESULT_ROWS=1000
LOG_LEVEL=INFO
```

---

## 📊 Key Features Summary

| Feature                  | Description                                  |
| ------------------------ | -------------------------------------------- |
| **Multi-LLM Support**    | OpenAI, Gemini, OpenRouter, Anthropic, Azure |
| **Vietnamese NLP**       | 60+ synonyms, time expressions, entities     |
| **Query Classification** | 8 query types with specialized prompts       |
| **Schema Optimization**  | Compact format, semantic grouping            |
| **Prompt Caching**       | Redis-based multi-level caching              |
| **Semantic SQL Cache**   | Similar query matching (0.85 threshold)      |
| **Self-Correction**      | Auto-fix invalid queries with error feedback |
| **Validation**           | Table/column check, dangerous op detection   |
| **Post-Processing**      | Auto LIMIT, SQL formatting                   |
| **Multi-Turn Context**   | Conversation history awareness               |
| **Session Management**   | With expiry and cleanup                      |
| **Connection Pooling**   | Efficient database connections               |
| **Cache Monitoring**     | /monitoring/cache/\* endpoints               |

---

## 🚀 Running the System

### Full Docker Stack

```bash
docker-compose -f docker-compose.full.yml up --build
```

### With phpMyAdmin

```bash
docker-compose -f docker-compose.full.yml --profile tools up --build
```

### Access Points

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:8501
- **phpMyAdmin**: http://localhost:8080
- **Redis**: localhost:6379

---

## 📈 Performance Optimizations

1. **Prompt Caching**: Redis-based multi-level caching for prompts
2. **Semantic SQL Cache**: Return cached SQL for similar queries (~85% threshold)
3. **Token Reduction**: Compact schema format reduces ~60% tokens
4. **Connection Pooling**: Reuse DB connections (pool_size=10)
5. **Schema Versioning**: Hash-based invalidation on schema changes
6. **Session Cleanup**: Auto-cleanup expired sessions (24h)
7. **Request Logging**: X-Request-ID for tracing
8. **Relevant Examples**: Dynamic few-shot based on question

---

## 🔒 Security

- **Read-Only**: Only SELECT queries allowed
- **SQL Validation**: Block DROP, DELETE, UPDATE, etc.
- **Input Sanitization**: Prevent SQL injection
- **Rate Limiting**: (TODO)
- **API Keys**: Secure LLM API key handling

---

_Last Updated: November 2025_
