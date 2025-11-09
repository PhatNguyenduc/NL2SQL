"""Safe SQL query execution module"""

import time
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from src.models.sql_query import QueryResult, DatabaseType
from src.utils.validation import (
    validate_sql, 
    is_safe_query, 
    sanitize_query, 
    add_query_limit
)

logger = logging.getLogger(__name__)


class QueryExecutor:
    """Execute SQL queries safely with validation and limits"""
    
    def __init__(
        self, 
        connection_string: str,
        database_type: DatabaseType,
        default_limit: int = 100,
        max_limit: int = 1000,
        enable_auto_limit: bool = True
    ):
        """
        Initialize QueryExecutor
        
        Args:
            connection_string: SQLAlchemy connection string
            database_type: Type of database
            default_limit: Default LIMIT to add if not specified
            max_limit: Maximum allowed LIMIT
            enable_auto_limit: Automatically add LIMIT if not present
        """
        self.connection_string = connection_string
        self.database_type = database_type
        self.default_limit = default_limit
        self.max_limit = max_limit
        self.enable_auto_limit = enable_auto_limit
        self.engine: Optional[Engine] = None
    
    def connect(self) -> Engine:
        """Create and return database engine"""
        if self.engine is None:
            try:
                self.engine = create_engine(self.connection_string, echo=False)
                logger.info(f"Query executor connected to {self.database_type} database")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
        return self.engine
    
    def disconnect(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            logger.info("Query executor disconnected")
    
    def execute(self, query: str, dry_run: bool = False) -> QueryResult:
        """
        Execute SQL query with safety checks
        
        Args:
            query: SQL query to execute
            dry_run: If True, validate but don't execute
            
        Returns:
            QueryResult object
        """
        start_time = time.time()
        
        # Step 1: Sanitize query
        query = sanitize_query(query)
        
        # Step 2: Validate syntax
        is_valid, error_msg = validate_sql(query)
        if not is_valid:
            return QueryResult(
                success=False,
                error_message=f"Validation error: {error_msg}",
                execution_time=time.time() - start_time
            )
        
        # Step 3: Check safety
        is_safe, issues = is_safe_query(query)
        if not is_safe:
            return QueryResult(
                success=False,
                error_message=f"Security check failed: {', '.join(issues)}",
                execution_time=time.time() - start_time
            )
        
        # Step 4: Add LIMIT if needed
        if self.enable_auto_limit:
            query = add_query_limit(query, self.default_limit)
        
        # Step 5: Dry run (validation only)
        if dry_run:
            return QueryResult(
                success=True,
                row_count=0,
                execution_time=time.time() - start_time,
                error_message="Dry run - query not executed"
            )
        
        # Step 6: Execute query
        try:
            engine = self.connect()
            with engine.connect() as conn:
                result = conn.execute(text(query))
                
                # Fetch results
                rows = []
                columns = []
                
                if result.returns_rows:
                    columns = list(result.keys())
                    rows = [dict(row._mapping) for row in result]
                
                execution_time = time.time() - start_time
                
                logger.info(f"Query executed successfully: {len(rows)} rows in {execution_time:.3f}s")
                
                return QueryResult(
                    success=True,
                    rows=rows,
                    row_count=len(rows),
                    execution_time=execution_time,
                    columns=columns
                )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = str(e)
            logger.error(f"Query execution failed: {error_message}")
            
            return QueryResult(
                success=False,
                error_message=error_message,
                execution_time=execution_time
            )
    
    def execute_batch(self, queries: List[str]) -> List[QueryResult]:
        """
        Execute multiple queries
        
        Args:
            queries: List of SQL queries
            
        Returns:
            List of QueryResult objects
        """
        results = []
        for query in queries:
            result = self.execute(query)
            results.append(result)
        return results
    
    def test_connection(self) -> bool:
        """
        Test database connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            engine = self.connect()
            with engine.connect() as conn:
                if self.database_type == DatabaseType.POSTGRESQL:
                    conn.execute(text("SELECT 1"))
                elif self.database_type == DatabaseType.MYSQL:
                    conn.execute(text("SELECT 1"))
            logger.info("Connection test successful")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_row_count(self, table_name: str) -> Optional[int]:
        """
        Get total row count for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            Row count or None if failed
        """
        try:
            query = f"SELECT COUNT(*) as count FROM {table_name}"
            result = self.execute(query)
            if result.success and result.rows:
                return result.rows[0]['count']
        except Exception as e:
            logger.warning(f"Failed to get row count for {table_name}: {e}")
        return None
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
