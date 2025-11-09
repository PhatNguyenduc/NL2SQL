"""Tests for SQL validation utilities"""

import pytest
from src.utils.validation import (
    validate_sql,
    is_safe_query,
    sanitize_query,
    add_query_limit,
    extract_table_names,
    validate_query_against_schema,
    check_query_complexity
)


class TestValidateSQL:
    """Test SQL validation functions"""
    
    def test_valid_select_query(self):
        query = "SELECT * FROM users WHERE age > 18"
        is_valid, message = validate_sql(query)
        assert is_valid is True
    
    def test_empty_query(self):
        query = ""
        is_valid, message = validate_sql(query)
        assert is_valid is False
        assert "empty" in message.lower()
    
    def test_multiple_statements(self):
        query = "SELECT * FROM users; DROP TABLE users;"
        is_valid, message = validate_sql(query)
        assert is_valid is False
        assert "multiple" in message.lower()
    
    def test_query_with_semicolon(self):
        query = "SELECT * FROM users;"
        is_valid, message = validate_sql(query)
        assert is_valid is True


class TestSafeQuery:
    """Test safety checking functions"""
    
    def test_safe_select_query(self):
        query = "SELECT * FROM users"
        is_safe, issues = is_safe_query(query)
        assert is_safe is True
        assert len(issues) == 0
    
    def test_dangerous_drop_query(self):
        query = "DROP TABLE users"
        is_safe, issues = is_safe_query(query)
        assert is_safe is False
        assert any("DROP" in issue for issue in issues)
    
    def test_dangerous_delete_query(self):
        query = "DELETE FROM users WHERE id = 1"
        is_safe, issues = is_safe_query(query)
        assert is_safe is False
        assert any("DELETE" in issue for issue in issues)
    
    def test_query_with_comments(self):
        query = "SELECT * FROM users -- comment"
        is_safe, issues = is_safe_query(query)
        assert is_safe is False
        assert any("comment" in issue.lower() for issue in issues)
    
    def test_query_starting_with_with(self):
        query = "WITH temp AS (SELECT * FROM users) SELECT * FROM temp"
        is_safe, issues = is_safe_query(query)
        assert is_safe is True


class TestSanitizeQuery:
    """Test query sanitization"""
    
    def test_remove_comments(self):
        query = "SELECT * FROM users -- this is a comment"
        sanitized = sanitize_query(query)
        assert "--" not in sanitized
        assert "SELECT * FROM users" in sanitized
    
    def test_remove_multiline_comments(self):
        query = "SELECT * /* comment */ FROM users"
        sanitized = sanitize_query(query)
        assert "/*" not in sanitized
        assert "*/" not in sanitized
    
    def test_remove_trailing_semicolon(self):
        query = "SELECT * FROM users;"
        sanitized = sanitize_query(query)
        assert not sanitized.endswith(";")


class TestAddQueryLimit:
    """Test adding LIMIT clause"""
    
    def test_add_limit_to_query_without_limit(self):
        query = "SELECT * FROM users"
        with_limit = add_query_limit(query, 100)
        assert "LIMIT 100" in with_limit
    
    def test_dont_add_limit_if_exists(self):
        query = "SELECT * FROM users LIMIT 50"
        with_limit = add_query_limit(query, 100)
        assert "LIMIT 50" in with_limit
        assert with_limit.count("LIMIT") == 1


class TestExtractTableNames:
    """Test table name extraction"""
    
    def test_extract_single_table(self):
        query = "SELECT * FROM users"
        tables = extract_table_names(query)
        assert "users" in tables
    
    def test_extract_multiple_tables_with_join(self):
        query = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        tables = extract_table_names(query)
        assert "users" in tables
        assert "orders" in tables
    
    def test_extract_with_aliases(self):
        query = "SELECT u.name FROM users u"
        tables = extract_table_names(query)
        assert "users" in tables


class TestValidateQueryAgainstSchema:
    """Test schema validation"""
    
    def test_valid_table_reference(self):
        query = "SELECT * FROM users"
        available_tables = ["users", "orders", "products"]
        is_valid, message = validate_query_against_schema(query, available_tables)
        assert is_valid is True
    
    def test_invalid_table_reference(self):
        query = "SELECT * FROM nonexistent_table"
        available_tables = ["users", "orders", "products"]
        is_valid, message = validate_query_against_schema(query, available_tables)
        assert is_valid is False
        assert "not found" in message.lower()


class TestCheckQueryComplexity:
    """Test query complexity analysis"""
    
    def test_simple_query(self):
        query = "SELECT * FROM users"
        complexity, warnings = check_query_complexity(query)
        assert complexity == "simple"
        assert len(warnings) == 0
    
    def test_medium_complexity_with_join(self):
        query = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        complexity, warnings = check_query_complexity(query)
        assert complexity in ["simple", "medium"]
    
    def test_complex_query_with_many_joins(self):
        query = """
        SELECT * FROM users 
        JOIN orders ON users.id = orders.user_id
        JOIN products ON orders.product_id = products.id
        JOIN categories ON products.category_id = categories.id
        JOIN brands ON products.brand_id = brands.id
        JOIN suppliers ON products.supplier_id = suppliers.id
        JOIN warehouses ON products.warehouse_id = warehouses.id
        """
        complexity, warnings = check_query_complexity(query)
        assert complexity == "complex"
        assert len(warnings) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
