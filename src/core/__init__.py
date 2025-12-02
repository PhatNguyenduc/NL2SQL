"""Core modules for NL2SQL conversion"""

from src.core.converter import NL2SQLConverter
from src.core.schema_extractor import SchemaExtractor
from src.core.query_executor import QueryExecutor
from src.core.embedding_provider import (
    get_embedder,
    get_default_embedder,
    EmbeddingProvider,
    EmbeddingConfig
)
from src.core.semantic_cache import (
    SemanticCache,
    get_semantic_cache,
    reset_semantic_cache
)
from src.core.async_llm_provider import (
    AsyncLLMClient,
    AsyncLLMPool,
    get_async_llm_client,
    reset_async_client,
    run_with_timeout,
    retry_async
)
from src.core.async_converter import (
    AsyncNL2SQLConverter,
    async_nl2sql
)
from src.core.query_decomposer import (
    QueryDecomposer,
    DecomposedQuery,
    SubQuery,
    DecompositionStrategy,
    decompose_question
)
from src.core.execution_feedback import (
    SQLExecutionFeedbackHandler,
    ExecutionFeedback,
    ErrorAnalysis,
    SQLErrorType,
    ExecutionFeedbackLoop,
    analyze_sql_error
)
from src.core.query_plan_cache import (
    QueryPlanCache,
    QueryPlan,
    QueryPattern,
    QueryPatternDetector,
    PatternMatch,
    get_query_plan_cache,
    reset_query_plan_cache
)

__all__ = [
    # Sync
    "NL2SQLConverter", 
    "SchemaExtractor", 
    "QueryExecutor",
    # Async
    "AsyncNL2SQLConverter",
    "async_nl2sql",
    "AsyncLLMClient",
    "AsyncLLMPool",
    "get_async_llm_client",
    "reset_async_client",
    "run_with_timeout",
    "retry_async",
    # Embedding & Cache
    "get_embedder",
    "get_default_embedder",
    "EmbeddingProvider",
    "EmbeddingConfig",
    "SemanticCache",
    "get_semantic_cache",
    "reset_semantic_cache",
    # Query Decomposition
    "QueryDecomposer",
    "DecomposedQuery",
    "SubQuery",
    "DecompositionStrategy",
    "decompose_question",
    # Execution Feedback
    "SQLExecutionFeedbackHandler",
    "ExecutionFeedback",
    "ErrorAnalysis",
    "SQLErrorType",
    "ExecutionFeedbackLoop",
    "analyze_sql_error",
    # Query Plan Cache
    "QueryPlanCache",
    "QueryPlan",
    "QueryPattern",
    "QueryPatternDetector",
    "PatternMatch",
    "get_query_plan_cache",
    "reset_query_plan_cache"
]
