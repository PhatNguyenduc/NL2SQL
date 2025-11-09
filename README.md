# NL2SQL - Natural Language to SQL Converter# NL2SQL - Natural Language to SQL Converter

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

🚀 Chuyển đổi câu hỏi tiếng tự nhiên thành SQL queries cho PostgreSQL và MySQL một cách chính xác và an toàn.

## 🎯 Modes## ✨ Tính năng

**1. Backend Server** (Recommended) - REST API với chat interface cho frontend integration - ✅ **Chuyển đổi thông minh**: Sử dụng OpenAI GPT để chuyển câu hỏi tự nhiên thành SQL

**2. CLI Tool** - Command-line interface để sử dụng trực tiếp- ✅ **Hỗ trợ đa database**: PostgreSQL và MySQL

- ✅ **Tự động phân tích schema**: Trích xuất và hiểu cấu trúc database

## ✨ Tính năng- ✅ **An toàn tuyệt đối**: Chỉ cho phép SELECT, chặn các thao tác nguy hiểm

- ✅ **Few-shot learning**: Tăng độ chính xác với examples

### Core Features- ✅ **CLI tiện lợi**: Command-line interface dễ sử dụng

- ✅ **Chuyển đổi thông minh**: Sử dụng OpenAI GPT để chuyển câu hỏi tự nhiên thành SQL- ✅ **Python API**: Tích hợp dễ dàng vào ứng dụng

- ✅ **Hỗ trợ đa database**: PostgreSQL và MySQL- ✅ **Format đẹp**: SQL được format chuẩn, dễ đọc

- ✅ **Tự động phân tích schema**: Trích xuất và hiểu cấu trúc database- ✅ **Execute & Results**: Thực thi và hiển thị kết quả trực quan

- ✅ **An toàn tuyệt đối**: Chỉ cho phép SELECT, chặn các thao tác nguy hiểm

- ✅ **Few-shot learning**: Tăng độ chính xác với examples## 📦 Cài đặt nhanh

- ✅ **Format đẹp**: SQL được format chuẩn, dễ đọc

- ✅ **Execute & Results**: Thực thi và hiển thị kết quả trực quan```bash

# Clone project

### Backend API Featuresgit clone https://github.com/yourusername/nl2sql.git

- 🚀 **REST API**: FastAPI server với 9 endpointscd nl2sql

- 💬 **Chat Interface**: Session-based conversation với message history

- 🐳 **Docker Support**: Containerized deployment với docker-compose# Tạo virtual environment

- 📊 **Interactive Docs**: Swagger UI và ReDoc tự độngpython -m venv venv

- 🔄 **Batch Processing**: Xử lý nhiều questions cùng lúc.\venv\Scripts\Activate.ps1 # Windows PowerShell

- ⚡ **High Performance**: Async/await architecture

# Cài đặt dependencies

---pip install -r requirements.txt

## 🚀 Quick Start# Cài đặt package

pip install -e .

### Option 1: Docker (Recommended for Backend Server)

# Cấu hình environment variables

````bashcopy .env.example .env

# 1. Clone repository# Chỉnh sửa .env với API key và database URL

git clone https://github.com/yourusername/nl2sql.git```

cd nl2sql

## 🚀 Sử dụng nhanh

# 2. Tạo .env file

copy .env.example .env### CLI

# Sửa .env với DATABASE_URL và OPENAI_API_KEY của bạn

```bash

# 3. Start all services (API + PostgreSQL + pgAdmin)# Test kết nối database

docker-compose up -dnl2sql test



# 4. Check status# Xem schema

docker-compose psnl2sql schema



# Server chạy tại http://localhost:8000# Tạo SQL từ câu hỏi

# Interactive docs: http://localhost:8000/docsnl2sql query "Show me all users"

````

# Tạo và thực thi SQL

**Test API:**nl2sql query "How many orders were placed last month?" --execute

```bash

# Health check# Xử lý hàng loạt

curl http://localhost:8000/healthnl2sql batch -i questions.txt -o results.json --execute

```

# Send a question

curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"message\": \"How many users?\", \"execute_query\": true}"### Python API

````

```python

### Option 2: Local Developmentfrom src.core.converter import NL2SQLConverter

from src.models.sql_query import DatabaseType

```powershell

# 1. Clone và setup# Khởi tạo converter

git clone https://github.com/yourusername/nl2sql.gitconverter = NL2SQLConverter(

cd nl2sql    connection_string="postgresql://user:pass@localhost/db",

    database_type=DatabaseType.POSTGRESQL,

# 2. Tạo virtual environment    enable_few_shot=True

python -m venv venv)

.\venv\Scripts\Activate.ps1

# Tạo SQL

# 3. Cài đặt dependenciessql_query = converter.generate_sql("Show me all users registered today")

pip install -r requirements.txtprint(sql_query.query)

pip install -e .print(f"Confidence: {sql_query.confidence:.2%}")



# 4. Cấu hình .env# Tạo và thực thi

copy .env.example .envsql_query, result = converter.generate_and_execute("What's the average order value?")

# DATABASE_URL=postgresql://user:password@localhost:5432/dbnameif result.success:

# OPENAI_API_KEY=sk-your-key-here    print(f"Result: {result.rows}")



# 5a. Chạy Backend Serverconverter.close()

python main.py```



# 5b. Hoặc sử dụng CLI## 📚 Documentation

nl2sql test

nl2sql ask "How many users?"- [Installation Guide](docs/installation.md) - Hướng dẫn cài đặt chi tiết

```- [Usage Guide](docs/usage.md) - Hướng dẫn sử dụng

- [Configuration](docs/configuration.md) - Cấu hình nâng cao

---- [Examples](examples/) - Các ví dụ mẫu



## 🎮 Usage## 🔧 Tech Stack



### Backend Server Mode### Core

- **instructor** - Structured outputs từ LLMs

**Start Server:**- **openai** - OpenAI API client

```bash- **pydantic** - Data validation

# With Docker- **sqlalchemy** - Database abstraction

docker-compose up -d- **sqlparse** - SQL formatting



# Local development### Database

python main.py- **psycopg2-binary** - PostgreSQL driver

```- **pymysql** - MySQL driver



**API Endpoints:**### CLI & UI

```bash- **click** - CLI framework

# Health check- **rich** - Terminal formatting

GET http://localhost:8000/health

### Development

# Chat (generate SQL + execute)- **pytest** - Testing framework

POST http://localhost:8000/chat- **python-dotenv** - Environment variables

{

  "message": "Show me all users registered last month",## 📁 Cấu trúc Project

  "execute_query": true,

  "session_id": "optional-session-id"```

}nl2sql/

├── src/

# Batch processing│   ├── core/               # Core modules

POST http://localhost:8000/chat/batch│   │   ├── converter.py    # Main NL2SQL converter

{│   │   ├── schema_extractor.py

  "messages": ["How many users?", "Show top 10 products"],│   │   └── query_executor.py

  "execute_queries": false│   ├── models/             # Pydantic models

}│   ├── prompts/            # LLM prompts

│   ├── utils/              # Utilities

# Get database schema│   └── cli.py              # CLI interface

GET http://localhost:8000/schema├── tests/                  # Tests

├── examples/               # Usage examples

# Conversation history├── docs/                   # Documentation

POST http://localhost:8000/conversation/history└── requirements.txt

{```

  "session_id": "session-123",

  "limit": 50## 🎯 Ví dụ

}

### Các loại câu hỏi được hỗ trợ

# List active sessions

GET http://localhost:8000/sessions**Aggregations:**

````

"How many users do we have?"

**Interactive Documentation:**"What's the average order value?"

- **Swagger UI**: http://localhost:8000/docs"Sum of all sales this month"

- **ReDoc**: http://localhost:8000/redoc```

**Frontend Integration Example (JavaScript):\*\***Filtering:\*\*

`javascript`

async function askQuestion(question) {"Show users older than 25"

const response = await fetch('http://localhost:8000/chat', {"Find orders placed last week"

    method: 'POST',"Products with price above $100"

    headers: { 'Content-Type': 'application/json' },```

    body: JSON.stringify({

      message: question,**Joins:**

      execute_query: true,```

      temperature: 0.1"Show orders with customer information"

    })"List products with their categories"

});"Users with their order history"

````

const data = await response.json();

console.log('SQL:', data.sql_generation.query);**Sorting:**

console.log('Results:', data.execution?.rows);```

return data;"Top 10 customers by spending"

}"Latest 5 orders"

"Products sorted by price descending"

// Usage```

askQuestion("Show me all users registered today");

```**Grouping:**

````

### CLI Mode"Revenue by month"

"Order count by status"

````bash"Average rating by product category"

# Test kết nối database```

nl2sql test

## 🛡️ Bảo mật

# Xem schema

nl2sql schema- ✅ Chỉ cho phép SELECT queries

- ✅ Chặn tất cả các thao tác thay đổi dữ liệu (INSERT, UPDATE, DELETE, DROP, etc.)

# Generate SQL (không execute)- ✅ Validation SQL syntax

nl2sql ask "Có bao nhiêu người dùng?"- ✅ Chống SQL injection

- ✅ Tự động thêm LIMIT để tránh queries quá lớn

# Generate và execute

nl2sql ask "Hiển thị 10 đơn hàng gần nhất" --execute## 🧪 Testing



# Batch processing```bash

nl2sql batch questions.txt --output results.json# Chạy unit tests

pytest tests/test_validation.py -v

# Interactive mode

nl2sql interactive# Chạy integration tests (cần database và API key)

```export DATABASE_URL="postgresql://user:pass@localhost/db"

export OPENAI_API_KEY="your-key"

### Python APIpytest tests/test_converter.py -v -m integration



```python# Chạy tất cả tests với coverage

from src.core.converter import NL2SQLConverterpytest tests/ --cov=src --cov-report=html

from src.models.sql_query import DatabaseConfig```



# Setup## 🤝 Contributing

config = DatabaseConfig(

    host="localhost",Contributions are welcome! Please feel free to submit a Pull Request.

    port=5432,

    database="mydb",1. Fork the project

    username="user",2. Create your feature branch (`git checkout -b feature/AmazingFeature`)

    password="pass",3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)

    db_type="postgresql"4. Push to the branch (`git push origin feature/AmazingFeature`)

)5. Open a Pull Request



converter = NL2SQLConverter(config)## 📝 License



# Generate SQLThis project is licensed under the MIT License - see the LICENSE file for details.

result = converter.generate_sql(

    "How many active users are there?",## 🙏 Acknowledgments

    temperature=0.1

)- OpenAI for GPT models

- Instructor library for structured outputs

print(f"SQL: {result.query}")- SQLAlchemy for database abstraction

print(f"Confidence: {result.confidence}")- Rich for beautiful terminal output



# Generate and execute## 📮 Contact

result = converter.generate_and_execute(

    "Show me top 10 products by sales"Your Name - [@yourusername](https://twitter.com/yourusername)

)

Project Link: [https://github.com/yourusername/nl2sql](https://github.com/yourusername/nl2sql)

if result.execution_result.success:

    print(f"Found {result.execution_result.row_count} rows")---

    for row in result.execution_result.rows:

        print(row)⭐ If you find this project useful, please give it a star!
````

---

## 🏗️ Architecture

### Backend Server Architecture

```
┌─────────────┐
│  Frontend   │  (React, Vue, Angular, etc.)
│  Chat UI    │
└──────┬──────┘
       │ HTTP REST API
       │
┌──────▼──────────────────────┐
│      FastAPI Server         │
│        (main.py)            │
├─────────────────────────────┤
│   Chat Service              │ ← Session management
│   NL2SQL Converter          │ ← OpenAI GPT integration
│   Schema Extractor          │ ← DB schema analysis
│   Query Executor            │ ← Safe query execution
└──────┬──────────────────────┘
       │
┌──────▼──────────┐
│   Database      │
│  (PostgreSQL)   │
└─────────────────┘
```

### Request Flow

1. Frontend sends natural language question via POST /chat
2. ChatService manages session and conversation history
3. NL2SQLConverter calls OpenAI API with database schema
4. OpenAI returns structured SQL with explanation
5. QueryExecutor validates and executes query (if requested)
6. Results returned to frontend as JSON

---

## 📁 Project Structure

```
NL2SQL/
├── main.py                    # FastAPI server entry point
├── src/
│   ├── api/
│   │   └── models.py         # API request/response models
│   ├── services/
│   │   └── chat_service.py   # Chat business logic
│   ├── core/
│   │   ├── converter.py      # Main NL2SQL logic
│   │   ├── schema_extractor.py
│   │   └── query_executor.py
│   ├── models/
│   │   └── sql_query.py      # Core data models
│   ├── prompts/
│   │   ├── system_prompt.py
│   │   └── few_shot_examples.py
│   ├── utils/
│   │   ├── validation.py
│   │   └── formatting.py
│   └── cli.py                # CLI interface
├── tests/                     # Unit & integration tests
├── docs/                      # Documentation
├── examples/                  # Code examples
├── Dockerfile                 # Container definition
├── docker-compose.yml         # Multi-service setup
└── requirements.txt           # Python dependencies
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file:

```env
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# Server Configuration (for backend mode)
HOST=0.0.0.0
PORT=8000
DEFAULT_LIMIT=100
LOG_LEVEL=INFO

# Security
# Add authentication/rate limiting in production
```

### Docker Configuration

See `docker-compose.yml` for:

- **nl2sql-api**: FastAPI server
- **postgres**: PostgreSQL database with sample data
- **pgadmin**: Database management UI (optional)

---

## 📚 Documentation

### Getting Started

- **[Quick Start](docs/quickstart.md)** - Bắt đầu trong 5 phút
- **[Backend Server Guide](docs/backend_server.md)** - Chạy server cho frontend
- **[API Reference](docs/api.md)** - Đầy đủ API endpoints với examples

### Advanced

- [Installation Guide](docs/installation.md) - Chi tiết cài đặt
- [Configuration Guide](docs/configuration.md) - Cấu hình nâng cao
- [Usage Guide](docs/usage.md) - CLI usage đầy đủ

### Examples

- [Python Examples](examples/) - Basic, PostgreSQL, MySQL, Batch
- [Frontend Integration](docs/backend_server.md#-frontend-integration) - React, Vue examples
- [API Examples](docs/api.md#-usage-examples) - JavaScript, cURL, Python

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_converter.py

# Integration tests
pytest tests/integration/
```

---

## 🐳 Docker Deployment

### Development

```bash
docker-compose up -d
```

### Production

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Behind reverse proxy (Nginx/Traefik)
# See docs/deployment.md for details
```

---

## 🔒 Security

- ✅ **Read-only operations**: Chỉ cho phép SELECT queries
- ✅ **SQL injection prevention**: Validation và parameterization
- ✅ **Query limits**: Tự động thêm LIMIT để tránh large result sets
- ✅ **Input validation**: Pydantic models cho tất cả inputs
- ⚠️ **Add authentication** trong production (API keys, JWT, OAuth)
- ⚠️ **Rate limiting** recommended cho production

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
