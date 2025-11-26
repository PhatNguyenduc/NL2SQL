"""Main NL2SQL converter with multi-LLM provider support and advanced optimizations"""

import os
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
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
from src.core.schema_optimizer import SchemaOptimizer
from src.core.query_preprocessor import QueryPreprocessor, QueryType, preprocess_question
from src.core.sql_validator import SQLValidator, SQLPostProcessor, ValidationResult
from src.core.schema_version_manager import SchemaVersionManager
from src.core.cache_manager import CacheManager, get_cache_manager, CacheLevel
from src.core.prompt_builder import PromptBuilder, build_nl2sql_prompt
from src.core.semantic_cache import SemanticSQLCache, get_semantic_cache
from src.prompts.system_prompt import (
    get_full_system_prompt, 
    get_user_prompt_template,
    get_query_type_prompt,
    get_self_correction_prompt
)
from src.prompts.few_shot_examples import get_few_shot_examples, format_examples_for_prompt, get_relevant_examples
from src.utils.validation import validate_query_against_schema
from src.utils.formatting import format_sql

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
        default_limit: int = 100,
        enable_caching: bool = True  # New: Enable prompt/SQL caching
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
            enable_caching: Enable prompt and SQL caching (default: True)
        """
        self.connection_string = connection_string
        self.database_type = database_type
        self.enable_few_shot = enable_few_shot
        self.enable_auto_execute = enable_auto_execute
        self.default_limit = default_limit
        self.enable_caching = enable_caching
        
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
        
        # Optimizers (initialized after schema load)
        self.schema_optimizer: Optional[SchemaOptimizer] = None
        self.query_preprocessor: Optional[QueryPreprocessor] = None
        self.sql_validator: Optional[SQLValidator] = None
        self.sql_postprocessor = SQLPostProcessor(default_limit=default_limit)
        
        # Caching components
        self.schema_version_manager = SchemaVersionManager()
        self.cache_manager: Optional[CacheManager] = None
        self.prompt_builder: Optional[PromptBuilder] = None
        self.semantic_cache: Optional[SemanticSQLCache] = None
        
        if self.enable_caching:
            try:
                self.cache_manager = get_cache_manager()
                self.prompt_builder = PromptBuilder(
                    cache_manager=self.cache_manager,
                    schema_version_manager=self.schema_version_manager,
                    enable_caching=True
                )
                self.semantic_cache = get_semantic_cache()
                logger.info("Prompt and SQL caching enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize caching: {e}. Continuing without cache.")
                self.enable_caching = False
    
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
        
        # Initialize optimizers with schema info
        self._init_optimizers()
        
        # Update schema version for cache invalidation
        if self.enable_caching:
            schema_changed = self.schema_version_manager.update_schema(self.schema)
            if schema_changed and self.cache_manager:
                version = self.schema_version_manager.get_current_version()
                self.cache_manager.update_schema_version(version)
                logger.info(f"Schema version updated: {version}")
        
        logger.info(f"Schema loaded: {self.schema.total_tables} tables")
        return self.schema
    
    def _init_optimizers(self):
        """Initialize schema optimizer, preprocessor, and validator"""
        if self.schema is None:
            return
        
        # Schema optimizer for compact representation
        self.schema_optimizer = SchemaOptimizer(self.schema)
        
        # Get table and column names for preprocessor/validator
        table_names = [t.table_name for t in self.schema.tables]
        column_names = []
        column_map = {}
        
        for table in self.schema.tables:
            cols = [c["name"] for c in table.columns]
            column_names.extend(cols)
            column_map[table.table_name] = cols
        
        # Query preprocessor for Vietnamese + classification
        self.query_preprocessor = QueryPreprocessor(table_names, column_names)
        
        # SQL validator
        self.sql_validator = SQLValidator(
            table_names=table_names,
            column_map=column_map,
            relationships=self.schema_optimizer.relationships
        )
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
            # Columns are dicts with "name", "type", "primary_key" keys
            pk_cols = [c["name"] for c in table.columns if c.get("primary_key", False)]
            pk_info = f" (PK: {', '.join(pk_cols)})" if pk_cols else ""
            schema_info.append(f"  - {table.table_name}: {col_count} cột{pk_info}")
        
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
        enable_self_correction: bool = True,
        use_cache: bool = True  # New: Use cached SQL if available
    ) -> SQLQuery:
        """
        Generate SQL query from natural language question
        
        Args:
            question: Natural language question
            temperature: Model temperature (0.0 = deterministic, 1.0 = creative)
            max_retries: Maximum number of retry attempts
            conversation_history: Previous conversation messages for context
            enable_self_correction: Enable automatic retry with error feedback
            use_cache: Try to use cached SQL before calling LLM
            
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
        
        # Get current schema version
        schema_version = self.schema_version_manager.get_current_version()
        
        # Try semantic cache first (if enabled and not in conversation context)
        if use_cache and self.enable_caching and self.semantic_cache:
            if not conversation_history:  # Only use cache for standalone queries
                cached = self.semantic_cache.get_sql(question, schema_version)
                if cached:
                    entry, similarity = cached
                    logger.info(f"Using cached SQL (similarity: {similarity:.2f})")
                    return SQLQuery(
                        query=entry.sql,
                        explanation=f"{entry.explanation}\n(Cached result, similarity: {similarity:.2f})",
                        confidence=min(0.95, entry.hit_count * 0.1 + 0.8),  # Boost confidence with hits
                        tables_used=entry.tables_used,
                        potential_issues=["Result from cache"]
                    )
        
        # Preprocess question (Vietnamese handling, classification)
        processed = None
        query_type = None
        if self.query_preprocessor:
            processed = self.query_preprocessor.process(question)
            query_type = processed.query_type
            logger.info(f"Query type: {processed.query_type.value}, confidence: {processed.confidence:.2f}")
            
            # Use normalized question for better understanding
            effective_question = processed.normalized
        else:
            effective_question = question
        
        # Use compact schema representation
        if self.schema_optimizer:
            compact_schema = self.schema_optimizer.format_compact_schema(include_types=False)
            # Get relevant tables for targeted examples (convert TableSchema to table names)
            relevant_table_objs = self.schema_optimizer.get_relevant_tables(question) if hasattr(self.schema_optimizer, 'get_relevant_tables') else None
            relevant_tables = [t.table_name for t in relevant_table_objs] if relevant_table_objs else None
        else:
            compact_schema = self.schema_text
            relevant_tables = None
        
        # Build prompt with caching support
        if self.prompt_builder and self.enable_caching:
            built_prompt = self.prompt_builder.build_prompt(
                question=effective_question if processed else question,
                schema_text=compact_schema,
                database_type=self.database_type.value,
                schema_version=schema_version,
                query_type=query_type,
                conversation_history=conversation_history,
                enable_few_shot=self.enable_few_shot,
                relevant_tables=relevant_tables
            )
            messages = built_prompt.messages
            
            if built_prompt.cache_info.get("components_cached"):
                logger.debug(f"Using cached prompt components (tokens saved: {built_prompt.cache_info.get('tokens_saved', 0)})")
        else:
            # Fallback to original prompt building
            system_prompt = get_full_system_prompt(compact_schema, self.database_type.value)
            
            # Add query type specific hints
            if processed:
                query_type_hint = get_query_type_prompt(processed.query_type.value)
                if query_type_hint:
                    system_prompt = f"{system_prompt}\n{query_type_hint}"
            
            # Add few-shot examples if enabled
            if self.enable_few_shot:
                examples = get_relevant_examples(question, max_examples=3)
                if not examples:
                    examples = get_few_shot_examples(self.database_type.value)[:3]
                examples_text = format_examples_for_prompt(examples)
                system_prompt = f"{system_prompt}\n\n{examples_text}"
            
            messages = [{"role": "system", "content": system_prompt}]
            
            if conversation_history:
                for msg in conversation_history[-6:]:
                    messages.append(msg)
            
            if processed and processed.normalized != question.lower():
                user_prompt = get_user_prompt_template(f"{question}\n(Interpreted: {processed.normalized})")
            else:
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
            
            # Advanced validation with SQLValidator
            validation_result = None
            if self.sql_validator:
                validation_result = self.sql_validator.validate(response.query)
                
                if not validation_result.is_valid:
                    error_feedback = self.sql_validator.generate_error_feedback(validation_result)
                    logger.warning(f"Query validation failed: {len(validation_result.errors)} errors")
                    
                    if response.potential_issues is None:
                        response.potential_issues = []
                    
                    for err in validation_result.errors:
                        response.potential_issues.append(f"{err.error_type.value}: {err.message}")
                    
                    response.confidence *= 0.3
                    
                    # Try self-correction if enabled
                    if enable_self_correction:
                        corrected = self._self_correct_query(
                            question, response, error_feedback, messages, temperature
                        )
                        if corrected:
                            return corrected
                
                # Add warnings to potential_issues
                for warning in validation_result.warnings[:3]:
                    if response.potential_issues is None:
                        response.potential_issues = []
                    response.potential_issues.append(f"Warning: {warning.message}")
            
            else:
                # Fallback to basic validation
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
                    
                    if enable_self_correction:
                        corrected = self._self_correct_query(
                            question, response, error_msg, messages, temperature
                        )
                        if corrected:
                            return corrected
            
            # Post-process SQL (add LIMIT, format, etc.)
            response.query = self.sql_postprocessor.process(response.query)
            
            # Format SQL
            response.query = format_sql(response.query)
            
            # Cache successful SQL result
            if self.enable_caching and self.semantic_cache and response.confidence >= 0.7:
                self.semantic_cache.cache_sql(
                    question=question,
                    sql=response.query,
                    explanation=response.explanation or "",
                    query_type=query_type.value if query_type else "unknown",
                    tables_used=response.tables_used or [],
                    schema_version=schema_version
                )
            
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
        logger.info(f"Attempting self-correction for query error")
        
        # Use improved self-correction prompt
        table_names = self.schema_extractor.get_table_names()
        correction_prompt = get_self_correction_prompt(
            failed_response.query,
            error_message,
            table_names
        )
        
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
            
            # Validate corrected query with SQLValidator if available
            is_valid = True
            if self.sql_validator:
                val_result = self.sql_validator.validate(corrected_response.query)
                is_valid = val_result.is_valid
            else:
                is_valid, _ = validate_query_against_schema(
                    corrected_response.query,
                    self.schema_extractor.get_table_names()
                )
            
            if is_valid:
                # Post-process the corrected query
                corrected_response.query = self.sql_postprocessor.process(corrected_response.query)
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
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring
        
        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "caching_enabled": self.enable_caching,
            "schema_version": self.schema_version_manager.get_current_version(),
            "schema_info": self.schema_version_manager.get_version_info()
        }
        
        if self.cache_manager:
            stats["cache_metrics"] = self.cache_manager.get_metrics()
            stats["cache_health"] = self.cache_manager.health_check()
        
        if self.prompt_builder:
            stats["prompt_cache"] = self.prompt_builder.get_cache_stats()
        
        if self.semantic_cache:
            stats["semantic_cache"] = self.semantic_cache.get_stats()
        
        return stats
    
    def invalidate_cache(self, invalidate_sql: bool = True, invalidate_prompts: bool = True):
        """
        Invalidate caches
        
        Args:
            invalidate_sql: Invalidate SQL result cache
            invalidate_prompts: Invalidate prompt cache
        """
        if not self.enable_caching:
            return
        
        if invalidate_sql and self.semantic_cache:
            self.semantic_cache.invalidate_all()
            logger.info("SQL cache invalidated")
        
        if invalidate_prompts and self.prompt_builder:
            self.prompt_builder.invalidate_cache()
            logger.info("Prompt cache invalidated")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
