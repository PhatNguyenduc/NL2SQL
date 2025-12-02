"""Async NL2SQL Converter - High-performance async version"""

import os
import re
import logging
import asyncio
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
    create_llm_config_from_env,
    LLMConfig,
    LLMProvider
)
from src.core.async_llm_provider import (
    AsyncLLMClient,
    get_async_llm_client,
    run_with_timeout,
    retry_async
)
from src.core.schema_optimizer import SchemaOptimizer
from src.core.query_preprocessor import QueryPreprocessor, QueryType, preprocess_question
from src.core.sql_validator import SQLValidator, SQLPostProcessor, ValidationResult
from src.core.schema_version_manager import SchemaVersionManager
from src.core.cache_manager import CacheManager, get_cache_manager, CacheLevel
from src.core.prompt_builder import PromptBuilder, build_nl2sql_prompt
from src.core.semantic_cache import SemanticCache, get_semantic_cache
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


# Keywords indicating schema/metadata questions
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


class AsyncNL2SQLConverter:
    """
    Async version of NL2SQL converter for high-performance scenarios
    
    Benefits:
    - Non-blocking LLM calls
    - Parallel processing of multiple queries
    - Better resource utilization
    - Concurrent cache operations
    """
    
    def __init__(
        self,
        connection_string: str,
        database_type: DatabaseType = DatabaseType.POSTGRESQL,
        llm_config: Optional[LLMConfig] = None,
        enable_few_shot: bool = True,
        enable_auto_execute: bool = False,
        default_limit: int = 100,
        enable_caching: bool = True,
        llm_timeout: float = 30.0
    ):
        """
        Initialize Async NL2SQL converter
        
        Args:
            connection_string: Database connection string
            database_type: Type of database
            llm_config: LLM configuration
            enable_few_shot: Enable few-shot examples
            enable_auto_execute: Auto execute generated queries
            default_limit: Default LIMIT for queries
            enable_caching: Enable caching
            llm_timeout: Timeout for LLM calls in seconds
        """
        self.connection_string = connection_string
        self.database_type = database_type
        self.enable_few_shot = enable_few_shot
        self.enable_auto_execute = enable_auto_execute
        self.default_limit = default_limit
        self.enable_caching = enable_caching
        self.llm_timeout = llm_timeout
        
        # Initialize LLM config
        if llm_config is None:
            llm_config = create_llm_config_from_env()
        
        self.llm_config = llm_config
        self.model = llm_config.model
        
        # Async LLM client (lazy initialized)
        self._async_client: Optional[AsyncLLMClient] = None
        
        # Schema components
        self.schema_extractor = SchemaExtractor(connection_string, database_type)
        self.schema: Optional[DatabaseSchema] = None
        self.schema_text: Optional[str] = None
        
        # Query executor
        self.query_executor = QueryExecutor(
            connection_string,
            database_type,
            default_limit=default_limit
        )
        
        # Optimizers (initialized after schema load)
        self.schema_optimizer: Optional[SchemaOptimizer] = None
        self.query_preprocessor: Optional[QueryPreprocessor] = None
        self.sql_validator: Optional[SQLValidator] = None
        self.sql_postprocessor = SQLPostProcessor(default_limit=default_limit)
        
        # Caching components
        self.schema_version_manager = SchemaVersionManager()
        self.cache_manager: Optional[CacheManager] = None
        self.prompt_builder: Optional[PromptBuilder] = None
        self.semantic_cache: Optional[SemanticCache] = None
        
        self._initialized = False
        
        logger.info(f"AsyncNL2SQLConverter created for {database_type}")
    
    async def initialize(self):
        """
        Async initialization - call this before using the converter
        """
        if self._initialized:
            return
        
        # Initialize async LLM client
        self._async_client = AsyncLLMClient(self.llm_config)
        
        # Load schema
        await asyncio.get_event_loop().run_in_executor(
            None, self.load_schema
        )
        
        # Initialize caching
        if self.enable_caching:
            try:
                self.cache_manager = get_cache_manager()
                self.prompt_builder = PromptBuilder(
                    cache_manager=self.cache_manager,
                    schema_version_manager=self.schema_version_manager,
                    enable_caching=True
                )
                self.semantic_cache = get_semantic_cache()
                logger.info("Async converter: Caching enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize caching: {e}")
                self.enable_caching = False
        
        self._initialized = True
        logger.info("AsyncNL2SQLConverter initialized successfully")
    
    def load_schema(self, include_sample_data: bool = False) -> DatabaseSchema:
        """Load database schema (sync operation)"""
        logger.info("Loading database schema...")
        self.schema = self.schema_extractor.extract_schema(include_sample_data)
        self.schema_text = self.schema_extractor.format_schema_for_llm(self.schema)
        
        self._init_optimizers()
        
        if self.enable_caching:
            schema_changed = self.schema_version_manager.update_schema(self.schema)
            if schema_changed and self.cache_manager:
                version = self.schema_version_manager.get_current_version()
                self.cache_manager.update_schema_version(version)
        
        logger.info(f"Schema loaded: {self.schema.total_tables} tables")
        return self.schema
    
    def _init_optimizers(self):
        """Initialize optimizers with schema info"""
        if self.schema is None:
            return
        
        self.schema_optimizer = SchemaOptimizer(self.schema)
        
        table_names = [t.table_name for t in self.schema.tables]
        column_names = []
        column_map = {}
        
        for table in self.schema.tables:
            cols = [c["name"] for c in table.columns]
            column_names.extend(cols)
            column_map[table.table_name] = cols
        
        self.query_preprocessor = QueryPreprocessor(table_names, column_names)
        self.sql_validator = SQLValidator(
            table_names=table_names,
            column_map=column_map,
            relationships=self.schema_optimizer.relationships
        )
    
    def _is_schema_query(self, question: str) -> bool:
        """Check if question is about schema/metadata"""
        question_lower = question.lower()
        for pattern in SCHEMA_QUERY_PATTERNS:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return True
        return False
    
    def _generate_schema_response(self, question: str) -> SQLQuery:
        """Generate response for schema questions"""
        if self.schema is None:
            self.load_schema()
        
        table_names = self.schema_extractor.get_table_names()
        
        schema_info = [f"Database có {len(table_names)} bảng:"]
        for table in self.schema.tables:
            col_count = len(table.columns)
            pk_cols = [c["name"] for c in table.columns if c.get("primary_key", False)]
            pk_info = f" (PK: {', '.join(pk_cols)})" if pk_cols else ""
            schema_info.append(f"  - {table.table_name}: {col_count} cột{pk_info}")
        
        explanation = "\n".join(schema_info)
        
        if self.database_type == DatabaseType.MYSQL:
            sql = """SELECT TABLE_NAME, TABLE_ROWS, TABLE_COMMENT 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME"""
        else:
            sql = """SELECT tablename, schemaname 
FROM pg_catalog.pg_tables 
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY tablename"""
        
        return SQLQuery(
            query=sql,
            explanation=explanation,
            confidence=1.0,
            tables_used=["INFORMATION_SCHEMA"],
            potential_issues=["Metadata query"]
        )
    
    async def generate_sql(
        self,
        question: str,
        temperature: float = 0.1,
        max_retries: int = 2,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        enable_self_correction: bool = True,
        use_cache: bool = True
    ) -> SQLQuery:
        """
        Async SQL generation from natural language
        
        Args:
            question: Natural language question
            temperature: Model temperature
            max_retries: Max retry attempts
            conversation_history: Previous conversation
            enable_self_correction: Enable auto-correction
            use_cache: Try cached results first
            
        Returns:
            SQLQuery object
        """
        # Ensure initialized
        if not self._initialized:
            await self.initialize()
        
        # Check for schema query
        if self._is_schema_query(question):
            logger.info(f"Detected schema query: {question}")
            return self._generate_schema_response(question)
        
        schema_version = self.schema_version_manager.get_current_version()
        
        # Try semantic cache first
        if use_cache and self.enable_caching and self.semantic_cache:
            if not conversation_history:
                cached = self.semantic_cache.get_sql(question, schema_version)
                if cached:
                    entry, similarity = cached
                    logger.info(f"Cache hit (similarity: {similarity:.2f})")
                    return SQLQuery(
                        query=entry.sql,
                        explanation=f"{entry.explanation}\n(Cached, similarity: {similarity:.2f})",
                        confidence=min(0.95, entry.hit_count * 0.1 + 0.8),
                        tables_used=entry.tables_used,
                        potential_issues=["From cache"]
                    )
        
        # Preprocess question
        processed = None
        query_type = None
        if self.query_preprocessor:
            processed = self.query_preprocessor.process(question)
            query_type = processed.query_type
            effective_question = processed.normalized
        else:
            effective_question = question
        
        # Build prompt
        messages = self._build_messages(
            question, effective_question, processed, query_type, 
            conversation_history, schema_version
        )
        
        logger.info(f"Async generating SQL for: {question}")
        
        try:
            # Async LLM call with timeout
            response = await run_with_timeout(
                self._async_client.create_completion(
                    response_model=SQLQuery,
                    messages=messages,
                    temperature=temperature,
                    max_retries=max_retries
                ),
                timeout=self.llm_timeout,
                error_msg=f"LLM call timed out after {self.llm_timeout}s"
            )
            
            # Validate and post-process
            response = await self._validate_and_process(
                response, question, messages, temperature, enable_self_correction
            )
            
            # Cache successful result
            if self.enable_caching and self.semantic_cache and response.confidence >= 0.7:
                # Run cache update in background
                asyncio.create_task(self._cache_result(
                    question, response, query_type, schema_version
                ))
            
            logger.info(f"SQL generated (confidence: {response.confidence})")
            return response
            
        except Exception as e:
            logger.error(f"Async SQL generation failed: {e}")
            raise
    
    def _build_messages(
        self,
        original_question: str,
        effective_question: str,
        processed: Optional[Any],
        query_type: Optional[QueryType],
        conversation_history: Optional[List[Dict[str, str]]],
        schema_version: str
    ) -> List[Dict[str, str]]:
        """Build messages for LLM"""
        # Get compact schema
        if self.schema_optimizer:
            compact_schema = self.schema_optimizer.format_compact_schema(include_types=False)
            relevant_table_objs = self.schema_optimizer.get_relevant_tables(original_question) if hasattr(self.schema_optimizer, 'get_relevant_tables') else None
            relevant_tables = [t.table_name for t in relevant_table_objs] if relevant_table_objs else None
        else:
            compact_schema = self.schema_text
            relevant_tables = None
        
        # Use prompt builder if available
        if self.prompt_builder and self.enable_caching:
            built_prompt = self.prompt_builder.build_prompt(
                question=effective_question,
                schema_text=compact_schema,
                database_type=self.database_type.value,
                schema_version=schema_version,
                query_type=query_type,
                conversation_history=conversation_history,
                enable_few_shot=self.enable_few_shot,
                relevant_tables=relevant_tables
            )
            return built_prompt.messages
        
        # Fallback to manual prompt building
        system_prompt = get_full_system_prompt(compact_schema, self.database_type.value)
        
        if processed:
            query_type_hint = get_query_type_prompt(processed.query_type.value)
            if query_type_hint:
                system_prompt = f"{system_prompt}\n{query_type_hint}"
        
        if self.enable_few_shot:
            examples = get_relevant_examples(original_question, max_examples=3)
            if not examples:
                examples = get_few_shot_examples(self.database_type.value)[:3]
            examples_text = format_examples_for_prompt(examples)
            system_prompt = f"{system_prompt}\n\n{examples_text}"
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(msg)
        
        if processed and processed.normalized != original_question.lower():
            user_prompt = get_user_prompt_template(f"{original_question}\n(Interpreted: {processed.normalized})")
        else:
            user_prompt = get_user_prompt_template(original_question)
        
        messages.append({"role": "user", "content": user_prompt})
        
        return messages
    
    async def _validate_and_process(
        self,
        response: SQLQuery,
        question: str,
        messages: List[Dict[str, str]],
        temperature: float,
        enable_self_correction: bool
    ) -> SQLQuery:
        """Validate and post-process response"""
        if self.sql_validator:
            validation_result = self.sql_validator.validate(response.query)
            
            if not validation_result.is_valid:
                error_feedback = self.sql_validator.generate_error_feedback(validation_result)
                logger.warning(f"Validation failed: {len(validation_result.errors)} errors")
                
                if response.potential_issues is None:
                    response.potential_issues = []
                
                for err in validation_result.errors:
                    response.potential_issues.append(f"{err.error_type.value}: {err.message}")
                
                response.confidence *= 0.3
                
                if enable_self_correction:
                    corrected = await self._async_self_correct(
                        question, response, error_feedback, messages, temperature
                    )
                    if corrected:
                        return corrected
            
            for warning in validation_result.warnings[:3]:
                if response.potential_issues is None:
                    response.potential_issues = []
                response.potential_issues.append(f"Warning: {warning.message}")
        
        # Post-process SQL
        response.query = self.sql_postprocessor.process(response.query)
        response.query = format_sql(response.query)
        
        return response
    
    async def _async_self_correct(
        self,
        original_question: str,
        failed_response: SQLQuery,
        error_message: str,
        original_messages: List[Dict[str, str]],
        temperature: float
    ) -> Optional[SQLQuery]:
        """Async self-correction attempt"""
        logger.info("Attempting async self-correction")
        
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
            
            corrected = await run_with_timeout(
                self._async_client.create_completion(
                    response_model=SQLQuery,
                    messages=messages,
                    temperature=temperature,
                    max_retries=1
                ),
                timeout=self.llm_timeout / 2  # Shorter timeout for correction
            )
            
            # Validate corrected query
            if self.sql_validator:
                val_result = self.sql_validator.validate(corrected.query)
                if val_result.is_valid:
                    corrected.query = self.sql_postprocessor.process(corrected.query)
                    corrected.query = format_sql(corrected.query)
                    if corrected.potential_issues is None:
                        corrected.potential_issues = []
                    corrected.potential_issues.insert(0, "Auto-corrected from previous error")
                    logger.info("Self-correction successful")
                    return corrected
            
            return None
            
        except Exception as e:
            logger.warning(f"Self-correction failed: {e}")
            return None
    
    async def _cache_result(
        self,
        question: str,
        response: SQLQuery,
        query_type: Optional[QueryType],
        schema_version: str
    ):
        """Cache result in background"""
        try:
            self.semantic_cache.cache_sql(
                question=question,
                sql=response.query,
                explanation=response.explanation or "",
                query_type=query_type.value if query_type else "unknown",
                tables_used=response.tables_used or [],
                schema_version=schema_version
            )
        except Exception as e:
            logger.debug(f"Background caching failed: {e}")
    
    async def generate_sql_batch(
        self,
        questions: List[str],
        max_concurrent: int = 5,
        **kwargs
    ) -> List[SQLQuery]:
        """
        Generate SQL for multiple questions in parallel
        
        Args:
            questions: List of natural language questions
            max_concurrent: Maximum concurrent LLM calls
            **kwargs: Additional args passed to generate_sql
            
        Returns:
            List of SQLQuery objects
        """
        if not self._initialized:
            await self.initialize()
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def limited_generate(question: str) -> SQLQuery:
            async with semaphore:
                try:
                    return await self.generate_sql(question, **kwargs)
                except Exception as e:
                    logger.error(f"Batch generation failed for '{question[:50]}...': {e}")
                    return SQLQuery(
                        query="-- Error generating SQL",
                        explanation=f"Error: {str(e)}",
                        confidence=0.0,
                        potential_issues=[str(e)]
                    )
        
        tasks = [limited_generate(q) for q in questions]
        results = await asyncio.gather(*tasks)
        
        return list(results)
    
    async def execute_and_generate(
        self,
        question: str,
        **kwargs
    ) -> Tuple[SQLQuery, Optional[QueryResult]]:
        """
        Generate SQL and execute it
        
        Args:
            question: Natural language question
            **kwargs: Args for generate_sql
            
        Returns:
            Tuple of (SQLQuery, QueryResult or None)
        """
        sql_query = await self.generate_sql(question, **kwargs)
        
        if sql_query.confidence < 0.5:
            return sql_query, None
        
        # Execute in thread pool (sync database operation)
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.query_executor.execute(sql_query.query, safe_mode=True)
        )
        
        return sql_query, result
    
    async def close(self):
        """Close async resources"""
        if self._async_client:
            await self._async_client.close()
        self._initialized = False
        logger.info("AsyncNL2SQLConverter closed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# Convenience function for one-off async queries
async def async_nl2sql(
    question: str,
    connection_string: str,
    database_type: DatabaseType = DatabaseType.MYSQL,
    llm_config: Optional[LLMConfig] = None,
    **kwargs
) -> SQLQuery:
    """
    One-off async NL2SQL conversion
    
    Args:
        question: Natural language question
        connection_string: Database connection string
        database_type: Type of database
        llm_config: LLM configuration
        **kwargs: Additional args
        
    Returns:
        SQLQuery object
    """
    async with AsyncNL2SQLConverter(
        connection_string=connection_string,
        database_type=database_type,
        llm_config=llm_config
    ) as converter:
        return await converter.generate_sql(question, **kwargs)
