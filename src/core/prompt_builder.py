"""
Prompt Builder with Caching Support

Builds prompts with cached static components to minimize token usage.
Supports prefix caching for system prompts and schema.
"""

import os
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum

from src.core.cache_manager import CacheManager, CacheLevel, get_cache_manager
from src.core.schema_version_manager import SchemaVersionManager
from src.core.query_preprocessor import QueryType
from src.prompts.system_prompt import (
    get_full_system_prompt,
    get_query_type_prompt,
    get_self_correction_prompt
)
from src.prompts.few_shot_examples import (
    get_few_shot_examples,
    format_examples_for_prompt,
    get_relevant_examples
)

logger = logging.getLogger(__name__)


class PromptPart(Enum):
    """Prompt component parts"""
    SYSTEM_BASE = "system_base"           # Core system instructions
    SCHEMA = "schema"                      # Database schema
    EXAMPLES = "examples"                  # Few-shot examples
    QUERY_HINTS = "query_hints"           # Query type specific hints
    USER_CONTEXT = "user_context"         # Conversation context
    CURRENT_QUERY = "current_query"       # Current user question


@dataclass
class CachedPromptComponents:
    """
    Cached prompt components for efficient prompt building
    
    Static parts (system, schema, examples) are cached.
    Dynamic parts (context, query) are built fresh each time.
    """
    # Cached static parts
    system_prompt: str = ""
    schema_text: str = ""
    few_shot_examples: str = ""
    
    # Metadata
    schema_version: Optional[str] = None
    cached_at: Optional[str] = None
    
    # Token estimates
    system_tokens: int = 0
    schema_tokens: int = 0
    examples_tokens: int = 0
    
    @property
    def static_content(self) -> str:
        """Get all static cached content"""
        return f"{self.system_prompt}\n\n{self.schema_text}\n\n{self.few_shot_examples}"
    
    @property
    def total_static_tokens(self) -> int:
        """Estimate total static tokens"""
        return self.system_tokens + self.schema_tokens + self.examples_tokens
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "system_prompt": self.system_prompt,
            "schema_text": self.schema_text,
            "few_shot_examples": self.few_shot_examples,
            "schema_version": self.schema_version,
            "cached_at": self.cached_at,
            "system_tokens": self.system_tokens,
            "schema_tokens": self.schema_tokens,
            "examples_tokens": self.examples_tokens
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedPromptComponents':
        """Deserialize from dictionary"""
        return cls(
            system_prompt=data.get("system_prompt", ""),
            schema_text=data.get("schema_text", ""),
            few_shot_examples=data.get("few_shot_examples", ""),
            schema_version=data.get("schema_version"),
            cached_at=data.get("cached_at"),
            system_tokens=data.get("system_tokens", 0),
            schema_tokens=data.get("schema_tokens", 0),
            examples_tokens=data.get("examples_tokens", 0)
        )


@dataclass
class BuiltPrompt:
    """Complete built prompt ready for LLM"""
    messages: List[Dict[str, str]]
    cache_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def system_message(self) -> str:
        """Get system message content"""
        for msg in self.messages:
            if msg.get("role") == "system":
                return msg.get("content", "")
        return ""
    
    @property
    def user_message(self) -> str:
        """Get last user message content"""
        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""


class PromptBuilder:
    """
    Prompt builder with caching support
    
    Features:
    - Caches static prompt components (system, schema, examples)
    - Prefix caching for common prompts
    - Query-type specific example selection
    - Token estimation for context management
    """
    
    # Approximate tokens per character (varies by tokenizer)
    CHARS_PER_TOKEN = 4
    
    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        schema_version_manager: Optional[SchemaVersionManager] = None,
        enable_caching: bool = True
    ):
        """
        Initialize prompt builder
        
        Args:
            cache_manager: Cache manager instance
            schema_version_manager: Schema version manager for invalidation
            enable_caching: Enable prompt caching
        """
        self.enable_caching = enable_caching
        self.cache_manager = cache_manager or (get_cache_manager() if enable_caching else None)
        self.schema_version_manager = schema_version_manager or SchemaVersionManager()
        
        # Cached components
        self._cached_components: Optional[CachedPromptComponents] = None
        self._components_key: Optional[str] = None
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text"""
        return len(text) // self.CHARS_PER_TOKEN
    
    def _compute_components_key(
        self,
        schema_version: str,
        database_type: str,
        enable_few_shot: bool
    ) -> str:
        """Compute cache key for components"""
        key_data = f"{schema_version}:{database_type}:{enable_few_shot}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def build_cached_components(
        self,
        schema_text: str,
        database_type: str,
        schema_version: str,
        enable_few_shot: bool = True,
        few_shot_examples: Optional[List[Dict]] = None
    ) -> CachedPromptComponents:
        """
        Build or retrieve cached prompt components
        
        Args:
            schema_text: Database schema as text
            database_type: Type of database (postgresql, mysql)
            schema_version: Schema version hash
            enable_few_shot: Include few-shot examples
            few_shot_examples: Custom examples (uses defaults if None)
            
        Returns:
            CachedPromptComponents object
        """
        components_key = self._compute_components_key(
            schema_version, database_type, enable_few_shot
        )
        
        # Check cache
        if self.enable_caching and self.cache_manager:
            cached = self.cache_manager.get(
                f"components:{components_key}",
                CacheLevel.PROMPT
            )
            if cached:
                logger.debug(f"Using cached prompt components: {components_key}")
                return CachedPromptComponents.from_dict(cached)
        
        # Build components
        from datetime import datetime
        
        # System prompt - get_full_system_prompt expects (schema_info, database_type)
        # We'll build the base system prompt without schema (schema added separately)
        system_prompt = get_full_system_prompt(
            schema_info="",  # Schema will be added separately in build_prompt
            database_type=database_type
        )
        
        # Few-shot examples
        examples_text = ""
        if enable_few_shot:
            examples = few_shot_examples or get_few_shot_examples()
            examples_text = format_examples_for_prompt(examples)
        
        components = CachedPromptComponents(
            system_prompt=system_prompt,
            schema_text=schema_text,
            few_shot_examples=examples_text,
            schema_version=schema_version,
            cached_at=datetime.now().isoformat(),
            system_tokens=self._estimate_tokens(system_prompt),
            schema_tokens=self._estimate_tokens(schema_text),
            examples_tokens=self._estimate_tokens(examples_text)
        )
        
        # Cache components
        if self.enable_caching and self.cache_manager:
            self.cache_manager.set(
                f"components:{components_key}",
                components.to_dict(),
                CacheLevel.PROMPT,
                schema_version=schema_version
            )
            logger.debug(f"Cached prompt components: {components_key}")
        
        self._cached_components = components
        self._components_key = components_key
        
        return components
    
    def build_prompt(
        self,
        question: str,
        schema_text: str,
        database_type: str,
        schema_version: str,
        query_type: Optional[QueryType] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        enable_few_shot: bool = True,
        relevant_tables: Optional[List[str]] = None
    ) -> BuiltPrompt:
        """
        Build complete prompt for LLM
        
        Args:
            question: User's natural language question
            schema_text: Database schema (may be filtered/compact)
            database_type: Type of database
            schema_version: Schema version for caching
            query_type: Detected query type
            conversation_history: Previous conversation messages
            enable_few_shot: Include few-shot examples
            relevant_tables: Tables relevant to the query (for focused examples)
            
        Returns:
            BuiltPrompt with messages and cache info
        """
        cache_info = {
            "components_cached": False,
            "examples_cached": False,
            "tokens_saved": 0
        }
        
        # Build or get cached components
        components = self.build_cached_components(
            schema_text=schema_text,
            database_type=database_type,
            schema_version=schema_version,
            enable_few_shot=enable_few_shot
        )
        
        if self._components_key:
            cache_info["components_cached"] = True
            cache_info["tokens_saved"] = components.total_static_tokens
        
        # Build system message with cached parts
        system_parts = [components.system_prompt]
        
        # Add schema
        system_parts.append(f"\n## Database Schema\n{schema_text}")
        
        # Add query-type specific hints
        if query_type:
            hints = get_query_type_prompt(query_type.value if isinstance(query_type, QueryType) else str(query_type))
            if hints:
                system_parts.append(f"\n## Query Hints\n{hints}")
        
        # Add few-shot examples (may use query-type specific)
        if enable_few_shot:
            if query_type and relevant_tables:
                # Get query-type and table-specific examples
                specific_examples = self._get_relevant_examples_cached(
                    query_type, relevant_tables
                )
                if specific_examples:
                    system_parts.append(f"\n## Examples\n{specific_examples}")
                    cache_info["examples_cached"] = True
                else:
                    system_parts.append(f"\n## Examples\n{components.few_shot_examples}")
            else:
                system_parts.append(f"\n## Examples\n{components.few_shot_examples}")
        
        system_content = "\n".join(system_parts)
        
        # Build messages
        messages = [{"role": "system", "content": system_content}]
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages max
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current question
        messages.append({"role": "user", "content": question})
        
        return BuiltPrompt(messages=messages, cache_info=cache_info)
    
    def _get_relevant_examples_cached(
        self,
        query_type: QueryType,
        relevant_tables: List[str]
    ) -> Optional[str]:
        """Get relevant examples with caching"""
        cache_key = f"examples:{query_type.value}:{':'.join(sorted(relevant_tables[:3]))}"
        
        if self.enable_caching and self.cache_manager:
            cached = self.cache_manager.get(cache_key, CacheLevel.EXAMPLES)
            if cached:
                return cached
        
        # Get relevant examples - use table names as pseudo-question for matching
        # since get_relevant_examples expects a question string
        pseudo_question = ' '.join(relevant_tables)
        examples = get_relevant_examples(pseudo_question, max_examples=3)
        
        if not examples:
            return None
        
        examples_text = format_examples_for_prompt(examples)
        
        if self.enable_caching and self.cache_manager:
            self.cache_manager.set(cache_key, examples_text, CacheLevel.EXAMPLES)
        
        return examples_text
    
    def build_correction_prompt(
        self,
        original_sql: str,
        error_message: str,
        schema_text: str,
        database_type: str,
        available_tables: Optional[List[str]] = None
    ) -> BuiltPrompt:
        """
        Build prompt for SQL correction
        
        Args:
            original_sql: SQL that caused error
            error_message: Error message from database
            schema_text: Database schema
            database_type: Type of database
            available_tables: List of valid table names
            
        Returns:
            BuiltPrompt for correction
        """
        tables = available_tables or []
        correction_prompt = get_self_correction_prompt(
            original_query=original_sql,
            error_message=error_message,
            available_tables=tables
        )
        
        messages = [
            {"role": "system", "content": f"You are a SQL expert. Fix the following SQL query error.\n\nDatabase type: {database_type}\n\nSchema:\n{schema_text}"},
            {"role": "user", "content": correction_prompt}
        ]
        
        return BuiltPrompt(messages=messages)
    
    def invalidate_cache(self, schema_version: Optional[str] = None):
        """Invalidate prompt cache"""
        if not self.cache_manager:
            return
        
        if schema_version:
            self.cache_manager.update_schema_version(schema_version)
        
        self.cache_manager.invalidate_level(CacheLevel.PROMPT)
        self._cached_components = None
        self._components_key = None
        
        logger.info("Prompt cache invalidated")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "caching_enabled": self.enable_caching,
            "components_cached": self._components_key is not None,
            "current_schema_version": None
        }
        
        if self._cached_components:
            stats["cached_tokens"] = self._cached_components.total_static_tokens
            stats["current_schema_version"] = self._cached_components.schema_version
        
        if self.cache_manager:
            stats["cache_metrics"] = self.cache_manager.get_metrics()
        
        return stats


# Convenience function
def build_nl2sql_prompt(
    question: str,
    schema_text: str,
    database_type: str = "mysql",
    schema_version: Optional[str] = None,
    query_type: Optional[QueryType] = None,
    conversation_history: Optional[List[Dict]] = None,
    enable_caching: bool = True
) -> BuiltPrompt:
    """
    Convenience function to build NL2SQL prompt with caching
    
    Args:
        question: User's question
        schema_text: Database schema
        database_type: Database type
        schema_version: Schema version (computed if None)
        query_type: Detected query type
        conversation_history: Conversation history
        enable_caching: Enable caching
        
    Returns:
        BuiltPrompt object
    """
    if schema_version is None:
        schema_version = hashlib.sha256(schema_text.encode()).hexdigest()[:16]
    
    builder = PromptBuilder(enable_caching=enable_caching)
    
    return builder.build_prompt(
        question=question,
        schema_text=schema_text,
        database_type=database_type,
        schema_version=schema_version,
        query_type=query_type,
        conversation_history=conversation_history
    )
