"""
Semantic Cache for SQL Queries

Caches SQL results and uses semantic similarity to return cached
results for similar queries, reducing LLM calls.
"""

import os
import re
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
import json

from src.core.cache_manager import CacheManager, CacheLevel, get_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class CachedSQLEntry:
    """Cached SQL entry with metadata"""
    question: str
    normalized_question: str
    sql: str
    explanation: str
    query_type: str
    tables_used: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    hit_count: int = 0
    schema_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "question": self.question,
            "normalized_question": self.normalized_question,
            "sql": self.sql,
            "explanation": self.explanation,
            "query_type": self.query_type,
            "tables_used": self.tables_used,
            "created_at": self.created_at.isoformat(),
            "hit_count": self.hit_count,
            "schema_version": self.schema_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachedSQLEntry':
        """Deserialize from dictionary"""
        return cls(
            question=data["question"],
            normalized_question=data["normalized_question"],
            sql=data["sql"],
            explanation=data.get("explanation", ""),
            query_type=data.get("query_type", "unknown"),
            tables_used=data.get("tables_used", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            hit_count=data.get("hit_count", 0),
            schema_version=data.get("schema_version")
        )


class QueryNormalizer:
    """
    Normalizes queries for semantic comparison
    
    Handles:
    - Lowercasing
    - Whitespace normalization
    - Number abstraction
    - Date abstraction
    - Vietnamese diacritics normalization
    - Common synonym replacement
    """
    
    # Common synonyms to normalize
    SYNONYMS = {
        # English
        "show": "get",
        "display": "get",
        "list": "get",
        "find": "get",
        "fetch": "get",
        "retrieve": "get",
        "count": "count",
        "total": "count",
        "number of": "count",
        "how many": "count",
        "top": "limit",
        "first": "limit",
        "highest": "max",
        "maximum": "max",
        "lowest": "min",
        "minimum": "min",
        "average": "avg",
        "mean": "avg",
        
        # Vietnamese
        "hiển thị": "get",
        "cho xem": "get",
        "liệt kê": "get",
        "tìm": "get",
        "lấy": "get",
        "đếm": "count",
        "bao nhiêu": "count",
        "số lượng": "count",
        "cao nhất": "max",
        "lớn nhất": "max",
        "thấp nhất": "min",
        "nhỏ nhất": "min",
        "trung bình": "avg"
    }
    
    # Patterns for abstraction
    NUMBER_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\b')
    DATE_PATTERN = re.compile(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b')
    EMAIL_PATTERN = re.compile(r'\b[\w.-]+@[\w.-]+\.\w+\b')
    
    @classmethod
    def normalize(cls, question: str) -> str:
        """
        Normalize question for semantic comparison
        
        Args:
            question: Raw question string
            
        Returns:
            Normalized question string
        """
        # Lowercase
        text = question.lower().strip()
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Abstract dates
        text = cls.DATE_PATTERN.sub('<DATE>', text)
        
        # Abstract numbers (but keep small numbers that might be counts)
        def replace_number(match):
            num = float(match.group())
            if num < 20:
                return match.group()  # Keep small numbers
            return '<NUM>'
        text = cls.NUMBER_PATTERN.sub(replace_number, text)
        
        # Abstract emails
        text = cls.EMAIL_PATTERN.sub('<EMAIL>', text)
        
        # Apply synonyms
        words = text.split()
        normalized_words = []
        i = 0
        while i < len(words):
            # Try multi-word phrases first
            found = False
            for phrase_len in range(3, 0, -1):
                if i + phrase_len <= len(words):
                    phrase = ' '.join(words[i:i+phrase_len])
                    if phrase in cls.SYNONYMS:
                        normalized_words.append(cls.SYNONYMS[phrase])
                        i += phrase_len
                        found = True
                        break
            
            if not found:
                word = words[i]
                normalized_words.append(cls.SYNONYMS.get(word, word))
                i += 1
        
        return ' '.join(normalized_words)
    
    @classmethod
    def extract_keywords(cls, question: str) -> List[str]:
        """Extract key terms from question"""
        normalized = cls.normalize(question)
        
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can',
            'for', 'of', 'to', 'in', 'on', 'at', 'by', 'with', 'from',
            'and', 'or', 'but', 'not', 'all', 'any', 'each', 'every',
            'this', 'that', 'these', 'those', 'it', 'its',
            'i', 'me', 'my', 'we', 'our', 'you', 'your',
            # Vietnamese stop words
            'của', 'và', 'hoặc', 'trong', 'từ', 'đến', 'với', 'cho',
            'là', 'có', 'không', 'được', 'để', 'những', 'các', 'này',
            'đó', 'tôi', 'bạn', 'chúng', 'nó'
        }
        
        words = normalized.split()
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        
        return keywords


class SemanticSQLCache:
    """
    Semantic cache for SQL queries
    
    Features:
    - Exact match caching with hash lookup
    - Semantic similarity for fuzzy matching
    - Query type aware caching
    - Schema version validation
    - LRU eviction policy
    """
    
    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        similarity_threshold: float = 0.85,
        max_entries: int = 1000
    ):
        """
        Initialize semantic SQL cache
        
        Args:
            cache_manager: Cache manager for storage
            similarity_threshold: Minimum similarity for cache hit (0-1)
            max_entries: Maximum cache entries
        """
        self.cache_manager = cache_manager or get_cache_manager()
        self.similarity_threshold = float(os.getenv(
            "CACHE_SEMANTIC_THRESHOLD",
            str(similarity_threshold)
        ))
        self.max_entries = max_entries
        self.normalizer = QueryNormalizer()
        
        # In-memory index for fast similarity lookup
        self._keyword_index: Dict[str, List[str]] = {}  # keyword -> [cache_keys]
        self._cache_keys: List[str] = []  # For LRU tracking
    
    def _compute_hash(self, normalized_question: str) -> str:
        """Compute hash key from normalized question"""
        return hashlib.sha256(normalized_question.encode()).hexdigest()[:16]
    
    def _compute_similarity(self, q1: str, q2: str) -> float:
        """
        Compute similarity between two normalized questions
        
        Uses Jaccard similarity on keyword sets with position weighting.
        
        Args:
            q1: First normalized question
            q2: Second normalized question
            
        Returns:
            Similarity score 0-1
        """
        kw1 = set(self.normalizer.extract_keywords(q1))
        kw2 = set(self.normalizer.extract_keywords(q2))
        
        if not kw1 or not kw2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(kw1 & kw2)
        union = len(kw1 | kw2)
        
        jaccard = intersection / union if union > 0 else 0.0
        
        # Boost for matching key terms
        key_terms = {'count', 'max', 'min', 'avg', 'sum', 'get', 'limit'}
        key_match = len((kw1 & key_terms) & (kw2 & key_terms))
        key_boost = 0.1 * key_match
        
        return min(1.0, jaccard + key_boost)
    
    def cache_sql(
        self,
        question: str,
        sql: str,
        explanation: str = "",
        query_type: str = "unknown",
        tables_used: Optional[List[str]] = None,
        schema_version: Optional[str] = None
    ) -> bool:
        """
        Cache SQL result
        
        Args:
            question: Original question
            sql: Generated SQL
            explanation: SQL explanation
            query_type: Type of query
            tables_used: Tables referenced in SQL
            schema_version: Current schema version
            
        Returns:
            True if cached successfully
        """
        normalized = self.normalizer.normalize(question)
        cache_key = self._compute_hash(normalized)
        
        entry = CachedSQLEntry(
            question=question,
            normalized_question=normalized,
            sql=sql,
            explanation=explanation,
            query_type=query_type,
            tables_used=tables_used or [],
            schema_version=schema_version
        )
        
        # Store in cache
        success = self.cache_manager.set(
            f"sql:{cache_key}",
            entry.to_dict(),
            CacheLevel.SQL,
            schema_version=schema_version
        )
        
        if success:
            # Update keyword index for similarity lookup
            keywords = self.normalizer.extract_keywords(normalized)
            for kw in keywords:
                if kw not in self._keyword_index:
                    self._keyword_index[kw] = []
                if cache_key not in self._keyword_index[kw]:
                    self._keyword_index[kw].append(cache_key)
            
            # Track for LRU
            if cache_key in self._cache_keys:
                self._cache_keys.remove(cache_key)
            self._cache_keys.append(cache_key)
            
            # Evict if needed
            if len(self._cache_keys) > self.max_entries:
                self._evict_oldest()
            
            logger.debug(f"Cached SQL: {cache_key[:8]}...")
        
        return success
    
    def get_sql(
        self,
        question: str,
        schema_version: Optional[str] = None,
        allow_semantic: bool = True
    ) -> Optional[Tuple[CachedSQLEntry, float]]:
        """
        Get cached SQL for question
        
        Args:
            question: Question to lookup
            schema_version: Expected schema version
            allow_semantic: Allow semantic matching (not just exact)
            
        Returns:
            Tuple of (CachedSQLEntry, similarity_score) or None
        """
        normalized = self.normalizer.normalize(question)
        cache_key = self._compute_hash(normalized)
        
        # Try exact match first
        cached_data = self.cache_manager.get(f"sql:{cache_key}", CacheLevel.SQL)
        if cached_data:
            entry = CachedSQLEntry.from_dict(cached_data)
            
            # Validate schema version
            if schema_version and entry.schema_version and entry.schema_version != schema_version:
                logger.debug(f"Cache miss: schema version mismatch")
                return None
            
            logger.debug(f"Exact cache hit: {cache_key[:8]}...")
            return (entry, 1.0)
        
        if not allow_semantic:
            return None
        
        # Try semantic matching
        keywords = self.normalizer.extract_keywords(normalized)
        candidate_keys = set()
        
        for kw in keywords:
            if kw in self._keyword_index:
                candidate_keys.update(self._keyword_index[kw])
        
        best_match: Optional[Tuple[CachedSQLEntry, float]] = None
        best_similarity = 0.0
        
        for candidate_key in candidate_keys:
            cached_data = self.cache_manager.get(f"sql:{candidate_key}", CacheLevel.SQL)
            if not cached_data:
                continue
            
            entry = CachedSQLEntry.from_dict(cached_data)
            
            # Validate schema version
            if schema_version and entry.schema_version and entry.schema_version != schema_version:
                continue
            
            # Compute similarity
            similarity = self._compute_similarity(normalized, entry.normalized_question)
            
            if similarity >= self.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = (entry, similarity)
        
        if best_match:
            logger.info(f"Semantic cache hit: similarity={best_match[1]:.2f}")
            return best_match
        
        return None
    
    def _evict_oldest(self):
        """Evict oldest entries (LRU)"""
        while len(self._cache_keys) > self.max_entries:
            oldest_key = self._cache_keys.pop(0)
            self.cache_manager.invalidate(f"sql:{oldest_key}", CacheLevel.SQL)
            
            # Remove from keyword index
            for kw, keys in list(self._keyword_index.items()):
                if oldest_key in keys:
                    keys.remove(oldest_key)
                    if not keys:
                        del self._keyword_index[kw]
    
    def invalidate_all(self):
        """Invalidate all cached SQL"""
        self.cache_manager.invalidate_level(CacheLevel.SQL)
        self._keyword_index.clear()
        self._cache_keys.clear()
        logger.info("SQL cache invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cached_queries": len(self._cache_keys),
            "indexed_keywords": len(self._keyword_index),
            "similarity_threshold": self.similarity_threshold,
            "max_entries": self.max_entries
        }


# Singleton instance
_semantic_cache: Optional[SemanticSQLCache] = None


def get_semantic_cache() -> SemanticSQLCache:
    """Get or create semantic cache singleton"""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticSQLCache()
    return _semantic_cache


def reset_semantic_cache():
    """Reset semantic cache singleton"""
    global _semantic_cache
    if _semantic_cache:
        _semantic_cache.invalidate_all()
    _semantic_cache = None
