"""Database schema extraction module"""

from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import logging
from src.models.sql_query import TableSchema, DatabaseSchema, DatabaseType

logger = logging.getLogger(__name__)


class SchemaExtractor:
    """Extract database schema information for PostgreSQL and MySQL"""
    
    def __init__(self, connection_string: str, database_type: DatabaseType):
        """
        Initialize SchemaExtractor
        
        Args:
            connection_string: SQLAlchemy connection string
            database_type: Type of database (postgresql or mysql)
        """
        self.connection_string = connection_string
        self.database_type = database_type
        self.engine: Optional[Engine] = None
        self._schema_cache: Optional[DatabaseSchema] = None
        
    def connect(self) -> Engine:
        """Create and return database engine"""
        if self.engine is None:
            try:
                self.engine = create_engine(self.connection_string, echo=False)
                logger.info(f"Connected to {self.database_type} database")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
        return self.engine
    
    def disconnect(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            logger.info("Database connection closed")
    
    def extract_schema(self, include_sample_data: bool = False, sample_limit: int = 3) -> DatabaseSchema:
        """
        Extract complete database schema
        
        Args:
            include_sample_data: Whether to include sample data from tables
            sample_limit: Number of sample rows to fetch per table
            
        Returns:
            DatabaseSchema object containing all schema information
        """
        if self._schema_cache is not None and not include_sample_data:
            return self._schema_cache
        
        engine = self.connect()
        inspector = inspect(engine)
        
        # Get database name
        db_name = self._get_database_name(engine)
        
        # Get all table names
        table_names = inspector.get_table_names()
        logger.info(f"Found {len(table_names)} tables in database")
        
        # Extract schema for each table
        tables = []
        for table_name in table_names:
            try:
                table_schema = self._extract_table_schema(
                    inspector, 
                    table_name,
                    include_sample_data,
                    sample_limit
                )
                tables.append(table_schema)
            except Exception as e:
                logger.warning(f"Failed to extract schema for table {table_name}: {e}")
        
        schema = DatabaseSchema(
            database_name=db_name,
            database_type=self.database_type,
            tables=tables,
            total_tables=len(tables)
        )
        
        # Cache schema if not including sample data
        if not include_sample_data:
            self._schema_cache = schema
        
        return schema
    
    def _extract_table_schema(
        self, 
        inspector, 
        table_name: str,
        include_sample_data: bool = False,
        sample_limit: int = 3
    ) -> TableSchema:
        """
        Extract schema for a single table
        
        Args:
            inspector: SQLAlchemy inspector
            table_name: Name of the table
            include_sample_data: Whether to include sample data
            sample_limit: Number of sample rows
            
        Returns:
            TableSchema object
        """
        # Get columns
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": "YES" if col["nullable"] else "NO",
                "default": str(col.get("default", ""))
            })
        
        # Get primary keys
        pk_constraint = inspector.get_pk_constraint(table_name)
        primary_keys = pk_constraint.get("constrained_columns", []) if pk_constraint else []
        
        # Get foreign keys
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name):
            foreign_keys.append({
                "column": fk["constrained_columns"][0] if fk["constrained_columns"] else "",
                "referenced_table": fk["referred_table"],
                "referenced_column": fk["referred_columns"][0] if fk["referred_columns"] else ""
            })
        
        # Get sample data if requested
        sample_data = None
        if include_sample_data:
            sample_data = self._get_sample_data(table_name, sample_limit)
        
        return TableSchema(
            table_name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys if foreign_keys else None,
            sample_data=sample_data
        )
    
    def _get_sample_data(self, table_name: str, limit: int = 3) -> Optional[List[Dict[str, Any]]]:
        """
        Get sample data from a table
        
        Args:
            table_name: Name of the table
            limit: Number of rows to fetch
            
        Returns:
            List of dictionaries representing rows
        """
        try:
            engine = self.connect()
            with engine.connect() as conn:
                query = text(f"SELECT * FROM {table_name} LIMIT {limit}")
                result = conn.execute(query)
                rows = [dict(row._mapping) for row in result]
                return rows if rows else None
        except Exception as e:
            logger.warning(f"Failed to get sample data for {table_name}: {e}")
            return None
    
    def _get_database_name(self, engine: Engine) -> str:
        """
        Get the current database name
        
        Args:
            engine: SQLAlchemy engine
            
        Returns:
            Database name
        """
        try:
            with engine.connect() as conn:
                if self.database_type == DatabaseType.POSTGRESQL:
                    result = conn.execute(text("SELECT current_database()"))
                    return result.scalar()
                elif self.database_type == DatabaseType.MYSQL:
                    result = conn.execute(text("SELECT DATABASE()"))
                    return result.scalar()
        except Exception as e:
            logger.warning(f"Failed to get database name: {e}")
            return "unknown"
    
    def format_schema_for_llm(self, schema: Optional[DatabaseSchema] = None) -> str:
        """
        Format schema in a human-readable format for LLM
        
        Args:
            schema: DatabaseSchema object (if None, will extract it)
            
        Returns:
            Formatted schema string
        """
        if schema is None:
            schema = self.extract_schema()
        
        output = []
        output.append(f"Database: {schema.database_name} ({schema.database_type})")
        output.append(f"Total Tables: {schema.total_tables}\n")
        
        for table in schema.tables:
            output.append(f"Table: {table.table_name}")
            output.append("Columns:")
            
            for col in table.columns:
                nullable = "NULL" if col["nullable"] == "YES" else "NOT NULL"
                pk_marker = " [PRIMARY KEY]" if col["name"] in table.primary_keys else ""
                output.append(f"  - {col['name']}: {col['type']} {nullable}{pk_marker}")
            
            # Add foreign keys
            if table.foreign_keys:
                output.append("Foreign Keys:")
                for fk in table.foreign_keys:
                    output.append(
                        f"  - {fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}"
                    )
            
            # Add sample data if available
            if table.sample_data:
                output.append("Sample Data:")
                for i, row in enumerate(table.sample_data, 1):
                    output.append(f"  Row {i}: {row}")
            
            output.append("")  # Empty line between tables
        
        return "\n".join(output)
    
    def get_table_names(self) -> List[str]:
        """
        Get list of all table names
        
        Returns:
            List of table names
        """
        schema = self.extract_schema()
        return [table.table_name for table in schema.tables]
    
    def get_table_schema(self, table_name: str) -> Optional[TableSchema]:
        """
        Get schema for a specific table
        
        Args:
            table_name: Name of the table
            
        Returns:
            TableSchema object or None if table not found
        """
        schema = self.extract_schema()
        for table in schema.tables:
            if table.table_name == table_name:
                return table
        return None
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
