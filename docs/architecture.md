# 🏗️ NL2SQL Architecture & Technical Deep Dive

## 📋 Mục lục

- [Tổng quan kiến trúc](#tổng-quan-kiến-trúc)
- [Core Components](#core-components)
- [Kỹ thuật tối ưu hiệu năng](#kỹ-thuật-tối-ưu-hiệu-năng)
- [Caching Strategy](#caching-strategy)
- [LLM Integration](#llm-integration)
- [Data Flow](#data-flow)

---

## 🎯 Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NL2SQL System                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │  Streamlit   │────▶│   FastAPI    │────▶│    MySQL     │                │
│  │   Frontend   │     │   Backend    │     │   Database   │                │
│  │  (Port 8501) │◀────│  (Port 8000) │◀────│  (Port 3307) │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│                              │                                               │
│                              ▼                                               │
│                    ┌──────────────────┐                                     │
│                    │   Redis Cache    │                                     │
│                    │   (Port 6379)    │                                     │
│                    └──────────────────┘                                     │
│                              │                                               │
│         ┌────────────────────┼────────────────────┐                         │
│         ▼                    ▼                    ▼                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   Semantic   │    │  Query Plan  │    │   General    │                  │
│  │    Cache     │    │    Cache     │    │    Cache     │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

                              │
                              ▼
              ┌───────────────────────────────┐
              │        LLM Providers          │
              │  ┌─────────┐ ┌─────────────┐  │
              │  │ Gemini  │ │   OpenAI    │  │
              │  │ (FREE)  │ │   (GPT-4)   │  │
              │  └─────────┘ └─────────────┘  │
              │  ┌─────────┐ ┌─────────────┐  │
              │  │ Claude  │ │ OpenRouter  │  │
              │  │         │ │(100+ models)│  │
              │  └─────────┘ └─────────────┘  │
              └───────────────────────────────┘
```

### Design Principles

1. **Modularity**: Mỗi component hoạt động độc lập, dễ thay thế và mở rộng
2. **Performance First**: Multi-layer caching giảm thiểu LLM calls
3. **Reliability**: Auto-fallback, retry mechanisms, error recovery
4. **Security**: Read-only queries, SQL injection prevention, input validation

---

## 🔧 Core Components

### 1. NL2SQLConverter (`src/core/converter.py`)

**Mục đích**: Bộ não chính - chuyển đổi câu hỏi tự nhiên thành SQL

```python
class NL2SQLConverter:
    """
    Pipeline xử lý:
    1. Question Preprocessing → Chuẩn hóa, phân loại query type
    2. Cache Lookup → Kiểm tra Semantic Cache + Query Plan Cache
    3. Schema Optimization → Lọc tables liên quan
    4. Prompt Building → Xây dựng prompt với few-shot examples
    5. LLM Generation → Gọi LLM với Instructor structured output
    6. SQL Validation → Validate + Post-process SQL
    7. Cache Storage → Lưu kết quả vào cache
    """
```

**Tại sao thiết kế này?**

- **Pipeline architecture**: Dễ debug từng bước, dễ thêm/bỏ stages
- **Instructor integration**: Đảm bảo LLM output luôn có format đúng (không cần parse manual)
- **Multi-level validation**: Catch lỗi sớm, giảm execution failures

### 2. AsyncNL2SQLConverter (`src/core/async_converter.py`)

**Mục đích**: Version async cho high-performance endpoints

```python
class AsyncNL2SQLConverter:
    """
    Sử dụng httpx.AsyncClient thay vì sync requests
    → Non-blocking I/O cho LLM calls
    → Tăng throughput khi có nhiều concurrent requests
    """
```

**Benchmark**:

- Sync: ~50 req/s
- Async: ~200 req/s (4x improvement)

### 3. SchemaOptimizer (`src/core/schema_optimizer.py`)

**Mục đích**: Tối ưu context schema gửi cho LLM

```python
class SchemaOptimizer:
    """
    Vấn đề: 24 tables × ~10 columns = 240 columns → Token quá lớn

    Giải pháp:
    1. Compact representation: Chỉ giữ table.column format
    2. Relevant table filtering: Chỉ include tables liên quan
    3. FK relationship mapping: Giúp LLM hiểu JOINs
    """
```

**Kết quả**: Giảm 60-70% tokens, tăng độ chính xác vì less noise

### 4. QueryPreprocessor (`src/core/query_preprocessor.py`)

**Mục đích**: Tiền xử lý câu hỏi trước khi gửi LLM

```python
class QueryPreprocessor:
    """
    Features:
    1. Vietnamese text normalization (Unicode NFC)
    2. Query type classification (lookup, aggregation, ranking, etc.)
    3. Entity extraction (table names, columns mentioned)
    4. Confidence scoring
    """
```

**Query Types**:

- `lookup`: Truy vấn đơn giản (SELECT ... WHERE)
- `aggregation`: Tổng hợp (COUNT, SUM, AVG, GROUP BY)
- `ranking`: Xếp hạng (ORDER BY ... LIMIT)
- `join`: Liên kết tables
- `time_range`: Filter theo thời gian

### 5. SQLValidator (`src/core/sql_validator.py`)

**Mục đích**: Validate và post-process SQL

```python
class SQLValidator:
    """
    Validation checks:
    1. Syntax validation (basic SQL parsing)
    2. Table/column existence check
    3. Dangerous keywords detection (DROP, DELETE, etc.)
    4. SQL injection patterns

    Post-processing:
    1. Auto-add LIMIT clause
    2. Format/beautify SQL
    3. Add table aliases
    """
```

---

## ⚡ Kỹ thuật tối ưu hiệu năng

### 1. Multi-Layer Caching (3 levels)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CACHING LAYERS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: SEMANTIC CACHE (Embedding-based)                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ "How many users?" ──embedding──▶ [0.12, 0.45, ...]      │    │
│  │ "Count all users" ──embedding──▶ [0.11, 0.46, ...]      │    │
│  │                      similarity = 0.95 → CACHE HIT!      │    │
│  │                                                           │    │
│  │ Benefit: Câu hỏi khác nhau về chữ nhưng ý nghĩa giống   │    │
│  │          → Reuse kết quả SQL                              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 2: QUERY PLAN CACHE (Pattern-based)                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ "Top 5 users by orders"  ──pattern──▶ TOP_N template     │    │
│  │ "Top 10 products by sales" ──pattern──▶ Same template!   │    │
│  │                                                           │    │
│  │ Template: SELECT {columns} FROM {table}                  │    │
│  │           ORDER BY {metric} DESC LIMIT {n}               │    │
│  │                                                           │    │
│  │ Benefit: Chỉ thay đổi parameters, không cần gọi LLM     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 3: GENERAL CACHE (Redis key-value)                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Schema cache: Avoid re-extracting database schema        │    │
│  │ Prompt cache: Reuse built prompts                        │    │
│  │ Result cache: Store execution results                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Schema Version Management

```python
class SchemaVersionManager:
    """
    Vấn đề: Cache SQL nhưng schema thay đổi → SQL sai

    Giải pháp:
    1. Hash schema structure → version ID
    2. Mỗi cached SQL gắn với schema version
    3. Schema thay đổi → Invalidate relevant cache entries
    """
```

### 3. SQL Execution Feedback Loop

```python
def _retry_with_execution_error(self, ...):
    """
    Vấn đề: LLM generate SQL hợp lệ về syntax nhưng lỗi khi execute

    Giải pháp:
    1. Execute SQL
    2. Nếu error → Extract error message
    3. Gửi lại cho LLM kèm error context
    4. LLM tự sửa dựa trên MySQL error
    5. Retry up to MAX_RETRIES lần
    """
```

**Ví dụ**:

```
Input: "Top 5 users this month and last month"
LLM Output (sai): SELECT ... ORDER BY x LIMIT 5 UNION ALL SELECT ...
MySQL Error: Syntax error near 'UNION'

→ Retry với error feedback:
"The SQL failed with: Syntax error. For UNION queries, wrap each SELECT in parentheses..."

LLM Corrected: (SELECT ... ORDER BY x LIMIT 5) UNION ALL (SELECT ...)
```

### 4. Async LLM Calls

```python
# Sync (blocking)
response = client.chat.completions.create(...)  # Blocks thread

# Async (non-blocking)
response = await async_client.chat.completions.create(...)  # Yields to event loop
```

**Tại sao quan trọng?**

- LLM call: ~2-10 seconds
- Sync: 1 thread blocked = 1 request at a time
- Async: Event loop handles 100s of concurrent requests

### 5. Connection Pooling

```python
# SQLAlchemy connection pool
engine = create_engine(
    connection_string,
    pool_size=10,          # Giữ 10 connections sẵn
    max_overflow=20,       # Có thể mở thêm 20 khi cần
    pool_timeout=30,       # Chờ connection tối đa 30s
    pool_recycle=3600      # Recycle connections sau 1h
)
```

---

## 💾 Caching Strategy

### Semantic Cache Flow

```
                                    ┌─────────────────┐
                                    │  User Question  │
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ Generate        │
                                    │ Embedding       │
                                    │ (1536-dim vec)  │
                                    └────────┬────────┘
                                             │
                         ┌───────────────────┼───────────────────┐
                         │                   │                   │
                         ▼                   ▼                   ▼
               ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
               │  Exact Match    │ │ Similarity      │ │    Miss         │
               │  (hash lookup)  │ │ Search ≥0.85    │ │  (call LLM)     │
               └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                        │                   │                   │
                        ▼                   ▼                   ▼
               ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
               │  Return cached  │ │  Return similar │ │  Generate SQL   │
               │  SQL instantly  │ │  SQL (adjusted) │ │  + cache it     │
               └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Cache Key Design

```python
# Semantic Cache Key
cache_key = f"nl2sql:semantic:{schema_version}:{question_hash}"

# Query Plan Cache Key
cache_key = f"nl2sql:plan:{pattern_type}:{table_names_hash}"

# General Cache Key
cache_key = f"nl2sql:{cache_type}:{unique_id}"
```

### TTL Strategy

| Cache Type     | TTL          | Lý do                             |
| -------------- | ------------ | --------------------------------- |
| Semantic Cache | 24h          | Câu hỏi có thể lặp lại trong ngày |
| Query Plan     | 7 days       | Patterns ít thay đổi              |
| Schema Cache   | Until change | Schema thường ổn định             |
| Prompt Cache   | 1h           | Prompt có thể update              |

---

## 🤖 LLM Integration

### Multi-Provider Architecture

```python
class LLMProvider(Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    AZURE_OPENAI = "azure_openai"

def get_llm_client(config: LLMConfig):
    """
    Factory pattern:
    - Config chứa provider type
    - Return appropriate client instance
    - All clients implement same interface
    """
```

### Instructor Integration

```python
# Thay vì parse JSON thủ công:
response = client.chat.completions.create(...)
sql = json.loads(response.choices[0].message.content)["query"]  # Error-prone!

# Instructor đảm bảo structured output:
response = client.chat.completions.create(
    model=self.model,
    response_model=SQLQuery,  # Pydantic model
    messages=messages
)
# response.query, response.explanation, response.confidence đã có sẵn
```

### Auto-Fallback Logic

```
1. User sets LLM_PROVIDER=openai
2. OpenAI key invalid/missing
3. System tries: Gemini → OpenRouter → Anthropic
4. First valid key wins
5. Log warning about fallback
```

---

## 🔄 Data Flow

### Request Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Frontend │───▶│ FastAPI  │───▶│  Chat    │───▶│ NL2SQL   │───▶│   LLM    │
│ (Chat)   │    │ Endpoint │    │ Service  │    │ Converter│    │ Provider │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                     │               │               │               │
                     │               │               │               │
                     ▼               ▼               ▼               ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
              │ Request  │    │ Session  │    │  Cache   │    │ Prompt   │
              │ Logging  │    │ History  │    │ Lookup   │    │ Building │
              │ + ID     │    │          │    │          │    │          │
              └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                    │
                     ┌──────────────────────────────────────────────┘
                     │
                     ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
              │   SQL    │───▶│   SQL    │───▶│  Query   │───▶│ Response │
              │ Response │    │Validation│    │Execution │    │ Format   │
              └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Analytics Collection Points

```python
# Mỗi request được track:
record_analytics(
    success=True/False,
    execution_time_ms=...,
    from_cache=True/False,
    query_type="aggregation",
    tables_used=["users", "orders"],
    confidence=0.95,
    error_type=None/"SyntaxError"/...
)
```

---

## 📊 Performance Metrics

### Target Benchmarks

| Metric                | Target | Current   |
| --------------------- | ------ | --------- |
| Cache Hit Rate        | >60%   | Varies    |
| Avg Response (cached) | <100ms | ~50ms     |
| Avg Response (LLM)    | <5s    | ~3-8s     |
| SQL Accuracy          | >90%   | ~85-95%   |
| Concurrent Users      | 100+   | Tested 50 |

### Monitoring Endpoints

```http
GET /analytics/dashboard     # Full analytics
GET /monitoring/cache/all    # All cache stats
GET /monitoring/embedding/stats  # Semantic cache
GET /monitoring/query-plan/stats # Query plan cache
GET /health                  # System health
```

---

## 🔒 Security Architecture

### Defense in Depth

```
Layer 1: Input Validation (Pydantic)
    ↓
Layer 2: Query Preprocessing (Sanitize)
    ↓
Layer 3: SQL Generation (Read-only prompts)
    ↓
Layer 4: SQL Validation (Keyword blocking)
    ↓
Layer 5: Query Execution (Read-only connection)
```

### Blocked Patterns

```python
DANGEROUS_KEYWORDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP',
    'TRUNCATE', 'ALTER', 'CREATE', 'GRANT',
    'REVOKE', 'EXEC', 'EXECUTE', '--', '/*'
]
```

---

## 🚀 Scaling Considerations

### Horizontal Scaling

```yaml
# Docker Compose với replicas
services:
  nl2sql-api:
    deploy:
      replicas: 3
    # Load balancer ở front
```

### Caching Scalability

- Redis Cluster cho high availability
- Sharding by cache key prefix
- Read replicas cho heavy read load

### Database Optimization

- Read replicas cho SELECT queries
- Connection pooling tuned for workload
- Query result caching

---

## 📚 Further Reading

- [LLM Providers Guide](./llm_providers.md)
- [API Reference](http://localhost:8000/docs)
- [Deployment Guide](./deployment.md) (coming soon)
