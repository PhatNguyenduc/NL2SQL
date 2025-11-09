# Test Configuration

## Running Tests

### Unit Tests (no database required)

```bash
pytest tests/test_validation.py -v
```

### Integration Tests (requires database and API key)

```bash
# Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/test_db"
export OPENAI_API_KEY="your-api-key"

# Run integration tests
pytest tests/test_converter.py -v -m integration
```

### Run all tests

```bash
pytest tests/ -v
```

## Test Database Setup

### PostgreSQL

```bash
# Create test database
createdb nl2sql_test

# Load sample schema
psql nl2sql_test < tests/fixtures/sample_db.sql
```

### MySQL

```bash
# Create test database
mysql -u root -p -e "CREATE DATABASE nl2sql_test;"

# Load sample schema (convert PostgreSQL to MySQL syntax first)
mysql -u root -p nl2sql_test < tests/fixtures/sample_db_mysql.sql
```

## Test Coverage

To generate coverage report:

```bash
pip install pytest-cov
pytest tests/ --cov=src --cov-report=html
```
