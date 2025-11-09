"""Main NL2SQL converter using OpenAI and Instructor"""

import os
import logging
from typing import Optional, List
import instructor
from openai import OpenAI
from src.models.sql_query import (
    SQLQuery, 
    DatabaseConfig, 
    QueryResult, 
    DatabaseType,
    DatabaseSchema
)
from src.core.schema_extractor import SchemaExtractor
from src.core.query_executor import QueryExecutor
from src.prompts.system_prompt import get_full_system_prompt, get_user_prompt_template
from src.prompts.few_shot_examples import get_few_shot_examples, format_examples_for_prompt
from src.utils.validation import validate_query_against_schema
from src.utils.formatting import format_sql

logger = logging.getLogger(__name__)


class NL2SQLConverter:
    """Main class for converting natural language to SQL queries"""
    
    def __init__(
        self,
        connection_string: str,
        database_type: DatabaseType = DatabaseType.POSTGRESQL,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        enable_few_shot: bool = True,
        enable_auto_execute: bool = False,
        default_limit: int = 100
    ):
        """
        Initialize NL2SQL converter
        
        Args:
            connection_string: Database connection string
            database_type: Type of database (postgresql or mysql)
            openai_api_key: OpenAI API key (if None, reads from env)
            model: OpenAI model to use
            enable_few_shot: Enable few-shot learning examples
            enable_auto_execute: Automatically execute generated queries
            default_limit: Default LIMIT for queries
        """
        self.connection_string = connection_string
        self.database_type = database_type
        self.model = model
        self.enable_few_shot = enable_few_shot
        self.enable_auto_execute = enable_auto_execute
        self.default_limit = default_limit
        
        # Initialize OpenAI client with Instructor
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided and OPENAI_API_KEY env var not set")
        
        self.client = instructor.from_openai(OpenAI(api_key=api_key))
        
        # Initialize schema extractor
        self.schema_extractor = SchemaExtractor(connection_string, database_type)
        self.schema: Optional[DatabaseSchema] = None
        self.schema_text: Optional[str] = None
        
        # Initialize query executor
        self.query_executor = QueryExecutor(
            connection_string,
            database_type,
            default_limit=default_limit
        )
        
        logger.info(f"NL2SQL Converter initialized with {database_type} database")
    
    def load_schema(self, include_sample_data: bool = False) -> DatabaseSchema:
        """
        Load and cache database schema
        
        Args:
            include_sample_data: Include sample data in schema
            
        Returns:
            DatabaseSchema object
        """
        logger.info("Loading database schema...")
        self.schema = self.schema_extractor.extract_schema(include_sample_data)
        self.schema_text = self.schema_extractor.format_schema_for_llm(self.schema)
        logger.info(f"Schema loaded: {self.schema.total_tables} tables")
        return self.schema
    
    def generate_sql(
        self,
        question: str,
        temperature: float = 0.1,
        max_retries: int = 2
    ) -> SQLQuery:
        """
        Generate SQL query from natural language question
        
        Args:
            question: Natural language question
            temperature: Model temperature (0.0 = deterministic, 1.0 = creative)
            max_retries: Maximum number of retry attempts
            
        Returns:
            SQLQuery object
        """
        # Load schema if not already loaded
        if self.schema is None:
            self.load_schema()
        
        # Build system prompt
        system_prompt = get_full_system_prompt(self.schema_text, self.database_type.value)
        
        # Add few-shot examples if enabled
        if self.enable_few_shot:
            examples = get_few_shot_examples(self.database_type.value)
            examples_text = format_examples_for_prompt(examples[:5])  # Use top 5 examples
            system_prompt = f"{system_prompt}\n\n{examples_text}"
        
        # Build user prompt
        user_prompt = get_user_prompt_template(question)
        
        logger.info(f"Generating SQL for question: {question}")
        
        try:
            # Call OpenAI with Instructor for structured output
            response = self.client.chat.completions.create(
                model=self.model,
                response_model=SQLQuery,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_retries=max_retries
            )
            
            # Validate query against schema
            is_valid, error_msg = validate_query_against_schema(
                response.query,
                self.schema_extractor.get_table_names()
            )
            
            if not is_valid:
                logger.warning(f"Generated query references invalid tables: {error_msg}")
                if response.potential_issues is None:
                    response.potential_issues = []
                response.potential_issues.append(error_msg)
                response.confidence *= 0.5  # Reduce confidence
            
            # Format SQL
            response.query = format_sql(response.query)
            
            logger.info(f"SQL generated successfully (confidence: {response.confidence})")
            return response
        
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            raise
    
    def generate_and_execute(
        self,
        question: str,
        temperature: float = 0.1
    ) -> tuple[SQLQuery, QueryResult]:
        """
        Generate SQL and execute it
        
        Args:
            question: Natural language question
            temperature: Model temperature
            
        Returns:
            Tuple of (SQLQuery, QueryResult)
        """
        # Generate SQL
        sql_query = self.generate_sql(question, temperature)
        
        # Execute query
        result = self.query_executor.execute(sql_query.query)
        
        return sql_query, result
    
    def ask(
        self,
        question: str,
        execute: Optional[bool] = None,
        temperature: float = 0.1
    ) -> dict:
        """
        High-level interface: ask a question and get results
        
        Args:
            question: Natural language question
            execute: Whether to execute query (if None, uses default)
            temperature: Model temperature
            
        Returns:
            Dictionary with query and optionally results
        """
        should_execute = execute if execute is not None else self.enable_auto_execute
        
        if should_execute:
            sql_query, result = self.generate_and_execute(question, temperature)
            return {
                "question": question,
                "sql_query": sql_query.model_dump(),
                "result": result.model_dump()
            }
        else:
            sql_query = self.generate_sql(question, temperature)
            return {
                "question": question,
                "sql_query": sql_query.model_dump()
            }
    
    def batch_generate(
        self,
        questions: List[str],
        temperature: float = 0.1
    ) -> List[SQLQuery]:
        """
        Generate SQL for multiple questions
        
        Args:
            questions: List of natural language questions
            temperature: Model temperature
            
        Returns:
            List of SQLQuery objects
        """
        results = []
        for question in questions:
            try:
                sql_query = self.generate_sql(question, temperature)
                results.append(sql_query)
            except Exception as e:
                logger.error(f"Failed to generate SQL for '{question}': {e}")
                # Create error response
                error_query = SQLQuery(
                    query="-- Error generating query",
                    explanation=f"Error: {str(e)}",
                    confidence=0.0,
                    potential_issues=[str(e)]
                )
                results.append(error_query)
        
        return results
    
    def get_schema_info(self) -> str:
        """
        Get formatted schema information
        
        Returns:
            Formatted schema string
        """
        if self.schema_text is None:
            self.load_schema()
        return self.schema_text
    
    def test_connection(self) -> bool:
        """
        Test database connection
        
        Returns:
            True if connection successful
        """
        return self.query_executor.test_connection()
    
    def close(self):
        """Close all connections"""
        self.schema_extractor.disconnect()
        self.query_executor.disconnect()
        logger.info("NL2SQL Converter closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
