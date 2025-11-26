"""Main NL2SQL converter with multi-LLM provider support"""

import os
import logging
from typing import Optional, List, Dict, Any
from src.models.sql_query import (
    SQLQuery, 
    DatabaseConfig, 
    QueryResult, 
    DatabaseType,
    DatabaseSchema
)
from src.core.schema_extractor import SchemaExtractor
from src.core.query_executor import QueryExecutor
from src.core.llm_provider import (
    get_llm_client,
    create_llm_config_from_env,
    LLMConfig,
    LLMProvider
)
from src.prompts.system_prompt import get_full_system_prompt, get_user_prompt_template
from src.prompts.few_shot_examples import get_few_shot_examples, format_examples_for_prompt, get_relevant_examples
from src.utils.validation import validate_query_against_schema
from src.utils.formatting import format_sql

import re

logger = logging.getLogger(__name__)


# Keywords indicating schema/metadata questions (not data queries)
SCHEMA_QUERY_PATTERNS = [
    r'\b(schema|cấu trúc|structure)\b',
    r'\b(tables?|bảng)\b.*\b(list|liệt kê|có gì|nào|what)\b',
    r'\b(what|những|có)\b.*\b(tables?|bảng)\b',
    r'\b(describe|mô tả|giải thích)\b.*\b(database|db|cơ sở dữ liệu)\b',
    r'\b(columns?|cột|fields?|trường)\b.*\b(in|của|trong)\b.*\b(table|bảng)\b',
    r'\b(database|db)\b.*\b(info|information|thông tin)\b',
    r'\bshow\s+(tables?|databases?)\b',
    r'\bdesc(ribe)?\s+\w+\b',
]


class NL2SQLConverter:
    """Main class for converting natural language to SQL queries"""
    
    def __init__(
        self,
        connection_string: str,
        database_type: DatabaseType = DatabaseType.POSTGRESQL,
        llm_config: Optional[LLMConfig] = None,
        openai_api_key: Optional[str] = None,  # Backward compatibility
        model: Optional[str] = None,  # Backward compatibility
        enable_few_shot: bool = True,
        enable_auto_execute: bool = False,
        default_limit: int = 100
    ):
        """
        Initialize NL2SQL converter with multi-LLM provider support
        
        Args:
            connection_string: Database connection string
            database_type: Type of database (postgresql or mysql)
            llm_config: LLM configuration (if None, creates from env vars)
            openai_api_key: OpenAI API key (deprecated, use llm_config or env vars)
            model: Model name (deprecated, use llm_config or env vars)
            enable_few_shot: Enable few-shot learning examples
            enable_auto_execute: Automatically execute generated queries
            default_limit: Default LIMIT for queries
        """
        self.connection_string = connection_string
        self.database_type = database_type
        self.enable_few_shot = enable_few_shot
        self.enable_auto_execute = enable_auto_execute
        self.default_limit = default_limit
        
        # Initialize LLM client with multi-provider support
        if llm_config is None:
            # Try to create from env vars
            try:
                llm_config = create_llm_config_from_env()
                
                # Override with explicit parameters for backward compatibility
                if openai_api_key:
                    llm_config.api_key = openai_api_key
                    llm_config.provider = LLMProvider.OPENAI
                if model:
                    llm_config.model = model
                    
            except Exception as e:
                # Fallback to OpenAI with explicit params
                if openai_api_key or os.getenv("OPENAI_API_KEY"):
                    logger.warning(f"Failed to create LLM config from env: {e}. Falling back to OpenAI.")
                    from src.core.llm_provider import LLMConfig, LLMProvider
                    llm_config = LLMConfig(
                        provider=LLMProvider.OPENAI,
                        api_key=openai_api_key or os.getenv("OPENAI_API_KEY"),
                        model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                    )
                else:
                    raise ValueError(
                        "No LLM configuration provided. Set LLM_PROVIDER and appropriate API key env vars, "
                        "or provide llm_config parameter"
                    )
        
        self.llm_config = llm_config
        self.model = llm_config.model
        self.client = get_llm_client(llm_config)
        
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
    
    def _is_schema_query(self, question: str) -> bool:
        """
        Detect if the question is asking about database schema/metadata
        rather than actual data
        
        Args:
            question: Natural language question
            
        Returns:
            True if question is about schema/metadata
        """
        question_lower = question.lower()
        
        for pattern in SCHEMA_QUERY_PATTERNS:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return True
        return False
    
    def _generate_schema_response(self, question: str) -> SQLQuery:
        """
        Generate a response for schema/metadata questions
        
        Args:
            question: The schema-related question
            
        Returns:
            SQLQuery with schema information
        """
        if self.schema is None:
            self.load_schema()
        
        # Get table names
        table_names = self.schema_extractor.get_table_names()
        
        # Build schema summary
        schema_info = []
        schema_info.append(f"Database có {len(table_names)} bảng:")
        for table in self.schema.tables:
            col_count = len(table.columns)
            pk_cols = [c.name for c in table.columns if c.is_primary_key]
            pk_info = f" (PK: {', '.join(pk_cols)})" if pk_cols else ""
            schema_info.append(f"  - {table.name}: {col_count} cột{pk_info}")
        
        explanation = "\n".join(schema_info)
        
        # For MySQL, we can actually query INFORMATION_SCHEMA
        if self.database_type == DatabaseType.MYSQL:
            sql = """SELECT TABLE_NAME, TABLE_ROWS, TABLE_COMMENT 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME"""
        else:
            # PostgreSQL
            sql = """SELECT tablename, schemaname 
FROM pg_catalog.pg_tables 
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY tablename"""
        
        return SQLQuery(
            query=sql,
            explanation=explanation,
            confidence=1.0,
            tables_used=["INFORMATION_SCHEMA"],
            potential_issues=["Đây là metadata query, không phải data query"]
        )
    
    def generate_sql(
        self,
        question: str,
        temperature: float = 0.1,
        max_retries: int = 2,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        enable_self_correction: bool = True
    ) -> SQLQuery:
        """
        Generate SQL query from natural language question
        
        Args:
            question: Natural language question
            temperature: Model temperature (0.0 = deterministic, 1.0 = creative)
            max_retries: Maximum number of retry attempts
            conversation_history: Previous conversation messages for context
            enable_self_correction: Enable automatic retry with error feedback
            
        Returns:
            SQLQuery object
        """
        # Load schema if not already loaded
        if self.schema is None:
            self.load_schema()
        
        # Check if this is a schema/metadata question
        if self._is_schema_query(question):
            logger.info(f"Detected schema query: {question}")
            return self._generate_schema_response(question)
        
        # Build system prompt
        system_prompt = get_full_system_prompt(self.schema_text, self.database_type.value)
        
        # Add few-shot examples if enabled (use relevant examples)
        if self.enable_few_shot:
            examples = get_relevant_examples(question, max_examples=3)
            if not examples:
                examples = get_few_shot_examples(self.database_type.value)[:3]
            examples_text = format_examples_for_prompt(examples)
            system_prompt = f"{system_prompt}\n\n{examples_text}"
        
        # Build messages with conversation context
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history for multi-turn context
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages (3 turns)
                messages.append(msg)
        
        # Build user prompt
        user_prompt = get_user_prompt_template(question)
        messages.append({"role": "user", "content": user_prompt})
        
        logger.info(f"Generating SQL for question: {question}")
        
        try:
            # Call LLM with Instructor for structured output
            response = self.client.chat.completions.create(
                model=self.model,
                response_model=SQLQuery,
                messages=messages,
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
                response.confidence *= 0.5
                
                # Try self-correction if enabled
                if enable_self_correction:
                    corrected = self._self_correct_query(
                        question, response, error_msg, messages, temperature
                    )
                    if corrected:
                        return corrected
            
            # Format SQL
            response.query = format_sql(response.query)
            
            logger.info(f"SQL generated successfully (confidence: {response.confidence})")
            return response
        
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            raise
    
    def _self_correct_query(
        self,
        original_question: str,
        failed_response: SQLQuery,
        error_message: str,
        original_messages: List[Dict[str, str]],
        temperature: float
    ) -> Optional[SQLQuery]:
        """
        Attempt to self-correct a failed query by providing error feedback
        
        Args:
            original_question: The original question
            failed_response: The failed SQLQuery response
            error_message: Error message describing what went wrong
            original_messages: Original conversation messages
            temperature: Model temperature
            
        Returns:
            Corrected SQLQuery or None if correction fails
        """
        logger.info(f"Attempting self-correction for query error: {error_message}")
        
        correction_prompt = f"""The previous SQL query had an issue:

ORIGINAL QUERY: {failed_response.query}
ERROR: {error_message}

Please generate a corrected SQL query that:
1. Fixes the error mentioned above
2. Uses only tables and columns that exist in the schema
3. Still answers the original question: {original_question}

Available tables: {', '.join(self.schema_extractor.get_table_names())}"""
        
        try:
            messages = original_messages.copy()
            messages.append({"role": "assistant", "content": f"```sql\n{failed_response.query}\n```"})
            messages.append({"role": "user", "content": correction_prompt})
            
            corrected_response = self.client.chat.completions.create(
                model=self.model,
                response_model=SQLQuery,
                messages=messages,
                temperature=temperature,
                max_retries=1
            )
            
            # Validate corrected query
            is_valid, _ = validate_query_against_schema(
                corrected_response.query,
                self.schema_extractor.get_table_names()
            )
            
            if is_valid:
                corrected_response.query = format_sql(corrected_response.query)
                if corrected_response.potential_issues is None:
                    corrected_response.potential_issues = []
                corrected_response.potential_issues.append("Query was auto-corrected")
                logger.info("Self-correction successful")
                return corrected_response
            else:
                logger.warning("Self-correction still produced invalid query")
                return None
                
        except Exception as e:
            logger.warning(f"Self-correction failed: {e}")
            return None
    
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
