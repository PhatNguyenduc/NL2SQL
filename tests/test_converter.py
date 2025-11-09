"""Tests for NL2SQL converter (requires database and OpenAI API key)"""

import pytest
import os
from unittest.mock import Mock, patch
from src.core.converter import NL2SQLConverter
from src.models.sql_query import DatabaseType, SQLQuery


class TestNL2SQLConverter:
    """Test NL2SQL converter"""
    
    @pytest.fixture
    def mock_converter(self):
        """Create a mock converter for testing"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            # This is a mock - real tests would need actual DB
            return None
    
    def test_converter_initialization_without_api_key(self):
        """Test that converter raises error without API key"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key"):
                NL2SQLConverter(
                    connection_string="postgresql://user:pass@localhost/db",
                    database_type=DatabaseType.POSTGRESQL
                )
    
    def test_converter_initialization_with_api_key(self):
        """Test converter initialization with API key"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.core.converter.OpenAI"):
                with patch("src.core.converter.instructor.from_openai"):
                    converter = NL2SQLConverter(
                        connection_string="postgresql://user:pass@localhost/db",
                        database_type=DatabaseType.POSTGRESQL,
                        openai_api_key="test-key"
                    )
                    assert converter is not None
                    assert converter.database_type == DatabaseType.POSTGRESQL


class TestSQLQueryModel:
    """Test SQLQuery model validation"""
    
    def test_valid_sql_query(self):
        """Test creating a valid SQLQuery"""
        query = SQLQuery(
            query="SELECT * FROM users",
            explanation="Get all users",
            confidence=0.95,
            tables_used=["users"]
        )
        assert query.query == "SELECT * FROM users"
        assert query.confidence == 0.95
    
    def test_invalid_confidence(self):
        """Test that invalid confidence raises error"""
        with pytest.raises(ValueError):
            SQLQuery(
                query="SELECT * FROM users",
                explanation="Get all users",
                confidence=1.5,  # Invalid
                tables_used=["users"]
            )
    
    def test_empty_query(self):
        """Test that empty query raises error"""
        with pytest.raises(ValueError):
            SQLQuery(
                query="",
                explanation="Get all users",
                confidence=0.95,
                tables_used=["users"]
            )


# Integration tests (require actual database)
@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("DATABASE_URL") or not os.getenv("OPENAI_API_KEY"),
    reason="Requires DATABASE_URL and OPENAI_API_KEY environment variables"
)
class TestNL2SQLIntegration:
    """Integration tests with real database and OpenAI"""
    
    def test_schema_loading(self):
        """Test loading database schema"""
        db_url = os.getenv("DATABASE_URL")
        db_type = DatabaseType.POSTGRESQL if "postgresql" in db_url else DatabaseType.MYSQL
        
        converter = NL2SQLConverter(
            connection_string=db_url,
            database_type=db_type
        )
        
        schema = converter.load_schema()
        assert schema is not None
        assert schema.total_tables > 0
        
        converter.close()
    
    def test_simple_query_generation(self):
        """Test generating a simple query"""
        db_url = os.getenv("DATABASE_URL")
        db_type = DatabaseType.POSTGRESQL if "postgresql" in db_url else DatabaseType.MYSQL
        
        converter = NL2SQLConverter(
            connection_string=db_url,
            database_type=db_type
        )
        
        # Load schema first
        converter.load_schema()
        
        # Generate query
        sql_query = converter.generate_sql("Show me all records from the first table")
        
        assert sql_query is not None
        assert sql_query.query.upper().startswith("SELECT")
        assert sql_query.confidence > 0
        
        converter.close()
    
    def test_connection_test(self):
        """Test database connection"""
        db_url = os.getenv("DATABASE_URL")
        db_type = DatabaseType.POSTGRESQL if "postgresql" in db_url else DatabaseType.MYSQL
        
        converter = NL2SQLConverter(
            connection_string=db_url,
            database_type=db_type
        )
        
        result = converter.test_connection()
        assert result is True
        
        converter.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
