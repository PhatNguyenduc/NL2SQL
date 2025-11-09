"""Pydantic models for SQL queries and database configuration"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum


class DatabaseType(str, Enum):
    """Supported database types"""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class DatabaseConfig(BaseModel):
    """Database configuration model"""
    db_type: DatabaseType = Field(..., description="Type of database (postgresql or mysql)")
    host: str = Field(..., description="Database host")
    port: int = Field(..., description="Database port")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    database: str = Field(..., description="Database name")
    
    @property
    def connection_string(self) -> str:
        """Generate SQLAlchemy connection string"""
        if self.db_type == DatabaseType.POSTGRESQL:
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == DatabaseType.MYSQL:
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    class Config:
        use_enum_values = True


class SQLQuery(BaseModel):
    """Model for generated SQL query with metadata"""
    query: str = Field(..., description="Generated SQL query")
    explanation: str = Field(..., description="Explanation of what the query does")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score of the generated query (0-1)"
    )
    tables_used: List[str] = Field(
        default_factory=list,
        description="List of tables used in the query"
    )
    potential_issues: Optional[List[str]] = Field(
        default=None,
        description="List of potential issues or warnings"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """Validate that query is not empty and is a string"""
        if not v or not isinstance(v, str):
            raise ValueError("Query must be a non-empty string")
        return v.strip()
    
    @validator('confidence')
    def validate_confidence(cls, v):
        """Ensure confidence is between 0 and 1"""
        if not 0 <= v <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "SELECT * FROM users WHERE age > 18 LIMIT 10",
                "explanation": "This query retrieves all columns from the users table where age is greater than 18, limited to 10 results",
                "confidence": 0.95,
                "tables_used": ["users"],
                "potential_issues": None
            }
        }


class QueryResult(BaseModel):
    """Model for query execution results"""
    success: bool = Field(..., description="Whether the query executed successfully")
    rows: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Query result rows as list of dictionaries"
    )
    row_count: int = Field(default=0, description="Number of rows returned")
    execution_time: float = Field(default=0.0, description="Query execution time in seconds")
    columns: Optional[List[str]] = Field(
        default=None,
        description="List of column names in the result"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if query failed"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "rows": [
                    {"id": 1, "name": "John", "age": 25},
                    {"id": 2, "name": "Jane", "age": 30}
                ],
                "row_count": 2,
                "execution_time": 0.05,
                "columns": ["id", "name", "age"],
                "error_message": None
            }
        }


class ErrorResponse(BaseModel):
    """Model for error responses"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Detailed error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Query contains forbidden keywords",
                "details": {"forbidden_keywords": ["DROP", "DELETE"]}
            }
        }


class TableSchema(BaseModel):
    """Model for database table schema"""
    table_name: str = Field(..., description="Name of the table")
    columns: List[Dict[str, str]] = Field(
        ...,
        description="List of columns with their properties"
    )
    primary_keys: List[str] = Field(
        default_factory=list,
        description="List of primary key columns"
    )
    foreign_keys: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="List of foreign key relationships"
    )
    sample_data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Sample data from the table"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "table_name": "users",
                "columns": [
                    {"name": "id", "type": "INTEGER", "nullable": "NO"},
                    {"name": "username", "type": "VARCHAR", "nullable": "NO"},
                    {"name": "email", "type": "VARCHAR", "nullable": "YES"}
                ],
                "primary_keys": ["id"],
                "foreign_keys": None,
                "sample_data": None
            }
        }


class DatabaseSchema(BaseModel):
    """Model for complete database schema"""
    database_name: str = Field(..., description="Name of the database")
    database_type: DatabaseType = Field(..., description="Type of database")
    tables: List[TableSchema] = Field(..., description="List of tables in the database")
    total_tables: int = Field(..., description="Total number of tables")
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "database_name": "myapp",
                "database_type": "postgresql",
                "tables": [],
                "total_tables": 5
            }
        }
