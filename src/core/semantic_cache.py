"""
Embedding-based Semantic Cache for SQL Queries

Enhanced semantic cache that uses vector embeddings for similarity matching.
Much more accurate than keyword-based matching for finding similar questions.

Features:
- Multiple embedding providers (OpenAI, Sentence Transformers, Gemini)
- Vector similarity search with cosine similarity
- Redis vector storage for persistence
- Hybrid matching (exact hash + semantic similarity)
- Query type aware matching
- Schema version validation
"""

import os
import re
import json
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
import numpy as np

from src.core.cache_manager import CacheManager, CacheLevel, get_cache_manager
from src.core.embedding_provider import (
    BaseEmbedder,
    get_default_embedder,
    cosine_similarity,
    batch_cosine_similarity,
    EmbeddingConfig,
    EmbeddingProvider
)

logger = logging.getLogger(__name__)


@dataclass
class CachedSQLEntry:
    """Cached SQL entry with metadata and embedding"""
    question: str
    normalized_question: str
    sql: str
    explanation: str
    query_type: str
    tables_used: List[str]
    embedding: Optional[List[float]] = None  # Stored as list for JSON serialization
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
            "embedding": self.embedding,
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
            embedding=data.get("embedding"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            hit_count=data.get("hit_count", 0),
            schema_version=data.get("schema_version")
        )
    
    def get_embedding_array(self) -> Optional[np.ndarray]:
        """Convert stored embedding to numpy array"""
        if self.embedding is None:
            return None
        return np.array(self.embedding, dtype=np.float32)


class QueryNormalizer:
    """
    Normalizes queries for comparison and embedding
    
    Handles:
    - Lowercasing and whitespace normalization
    - Number/date/email abstraction
    - Vietnamese diacritics preservation
    """
    
    NUMBER_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\b')
    DATE_PATTERN = re.compile(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b')
    EMAIL_PATTERN = re.compile(r'\b[\w.-]+@[\w.-]+\.\w+\b')
    
    @classmethod
    def normalize(cls, question: str) -> str:
        """
        Normalize question for comparison
        
        Args:
            question: Raw question string
            
        Returns:
            Normalized question string
        """
        # Lowercase and normalize whitespace
        text = question.lower().strip()
        text = ' '.join(text.split())
        
        # Abstract dates
        text = cls.DATE_PATTERN.sub('<DATE>', text)
        
        # Abstract large numbers (keep small numbers)
        def replace_number(match):
            try:
                num = float(match.group())
                if num < 20:
                    return match.group()
                return '<NUM>'
            except:
                return match.group()
        
        text = cls.NUMBER_PATTERN.sub(replace_number, text)
        
        # Abstract emails
        text = cls.EMAIL_PATTERN.sub('<EMAIL>', text)
        
        return text
    
    @classmethod
    def extract_query_intent(cls, question: str) -> Dict[str, Any]:
        """
        Extract query intent features for type matching
        
        Returns dict with:
        - aggregation_type: count, sum, avg, max, min, none
        - operation: select, compare, rank, group
        - temporal: today, week, month, year, range, none
        """
        text = question.lower()
        
        intent = {
            "aggregation": "none",
            "operation": "select",
            "temporal": "none"
        }
        
        # Detect aggregation
        agg_patterns = {
            "count": [r'\bcount\b', r'\bđếm\b', r'\bsố lượng\b', r'\bbao nhiêu\b', r'\bhow many\b'],
            "sum": [r'\bsum\b', r'\btổng\b', r'\btotal\b'],
            "avg": [r'\bavg\b', r'\baverage\b', r'\btrung bình\b', r'\bmean\b'],
            "max": [r'\bmax\b', r'\bhighest\b', r'\bcao nhất\b', r'\blớn nhất\b', r'\btop\b'],
            "min": [r'\bmin\b', r'\blowest\b', r'\bthấp nhất\b', r'\bnhỏ nhất\b']
        }
        
        for agg_type, patterns in agg_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    intent["aggregation"] = agg_type
                    break
        
        # Detect operation
        if re.search(r'\bcompare\b|\bso sánh\b|\bvs\b', text):
            intent["operation"] = "compare"
        elif re.search(r'\btop\b|\brank\b|\bxếp hạng\b', text):
            intent["operation"] = "rank"
        elif re.search(r'\bgroup\b|\bnhóm\b|\bby\s+\w+\b', text):
            intent["operation"] = "group"
        
        # Detect temporal
        temporal_patterns = {
            "today": [r'\btoday\b', r'\bhôm nay\b'],
            "week": [r'\bthis week\b', r'\btuần này\b', r'\blast week\b', r'\btuần trước\b'],
            "month": [r'\bthis month\b', r'\btháng này\b', r'\blast month\b', r'\btháng trước\b'],
            "year": [r'\bthis year\b', r'\bnăm nay\b', r'\blast year\b', r'\bnăm ngoái\b'],
            "range": [r'\bfrom\s+\S+\s+to\b', r'\bbetween\b', r'\btừ\s+\S+\s+đến\b']
        }
        
        for temp_type, patterns in temporal_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    intent["temporal"] = temp_type
                    break
        
        return intent


class EmbeddingVectorStore:
    """
    In-memory vector store with Redis persistence for embeddings
    
    Uses approximate nearest neighbor search for fast similarity lookup.
    """
    
    def __init__(
        self,
        cache_manager: CacheManager,
        dimension: int,
        max_vectors: int = 5000
    ):
        self.cache_manager = cache_manager
        self.dimension = dimension
        self.max_vectors = max_vectors
        
        # In-memory vector index
        self._vectors: Dict[str, np.ndarray] = {}  # cache_key -> embedding
        self._metadata: Dict[str, Dict] = {}  # cache_key -> {query_type, tables, schema_version}
        self._keys_order: List[str] = []  # For LRU eviction
        
        # Load from Redis on init
        self._load_from_redis()
    
    def _load_from_redis(self):
        """Load vector index from Redis"""
        try:
            index_data = self.cache_manager.get("embedding_index", CacheLevel.SEMANTIC)
            if index_data:
                for key, entry in index_data.items():
                    if entry.get("embedding"):
                        self._vectors[key] = np.array(entry["embedding"], dtype=np.float32)
                        self._metadata[key] = {
                            "query_type": entry.get("query_type", "unknown"),
                            "tables": entry.get("tables", []),
                            "schema_version": entry.get("schema_version")
                        }
                        self._keys_order.append(key)
                logger.info(f"Loaded {len(self._vectors)} vectors from Redis")
        except Exception as e:
            logger.warning(f"Failed to load vector index from Redis: {e}")
    
    def _save_to_redis(self):
        """Save vector index to Redis"""
        try:
            index_data = {}
            for key in self._vectors:
                index_data[key] = {
                    "embedding": self._vectors[key].tolist(),
                    **self._metadata.get(key, {})
                }
            
            self.cache_manager.set(
                "embedding_index",
                index_data,
                CacheLevel.SEMANTIC,
                ttl=86400  # 24 hours
            )
        except Exception as e:
            logger.warning(f"Failed to save vector index to Redis: {e}")
    
    def add(
        self,
        key: str,
        embedding: np.ndarray,
        query_type: str = "unknown",
        tables: Optional[List[str]] = None,
        schema_version: Optional[str] = None
    ):
        """Add vector to store"""
        # Evict if at capacity
        while len(self._vectors) >= self.max_vectors:
            self._evict_oldest()
        
        self._vectors[key] = embedding
        self._metadata[key] = {
            "query_type": query_type,
            "tables": tables or [],
            "schema_version": schema_version
        }
        
        # Update LRU order
        if key in self._keys_order:
            self._keys_order.remove(key)
        self._keys_order.append(key)
        
        # Periodically save to Redis
        if len(self._vectors) % 100 == 0:
            self._save_to_redis()
    
    def remove(self, key: str):
        """Remove vector from store"""
        if key in self._vectors:
            del self._vectors[key]
        if key in self._metadata:
            del self._metadata[key]
        if key in self._keys_order:
            self._keys_order.remove(key)
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        query_type: Optional[str] = None,
        schema_version: Optional[str] = None,
        min_similarity: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        Search for similar vectors
        
        Args:
            query_embedding: Query vector
            top_k: Maximum results to return
            query_type: Filter by query type (optional)
            schema_version: Filter by schema version (optional)
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (cache_key, similarity_score) tuples
        """
        if not self._vectors:
            return []
        
        # Filter candidates by metadata
        candidate_keys = []
        candidate_vectors = []
        
        for key, embedding in self._vectors.items():
            meta = self._metadata.get(key, {})
            
            # Schema version filter
            if schema_version and meta.get("schema_version"):
                if meta["schema_version"] != schema_version:
                    continue
            
            # Query type filter (soft - boost matching types)
            candidate_keys.append(key)
            candidate_vectors.append(embedding)
        
        if not candidate_vectors:
            return []
        
        # Compute similarities
        vectors_matrix = np.array(candidate_vectors)
        similarities = batch_cosine_similarity(query_embedding, vectors_matrix)
        
        # Apply query type boost
        if query_type:
            for i, key in enumerate(candidate_keys):
                meta = self._metadata.get(key, {})
                if meta.get("query_type") == query_type:
                    similarities[i] *= 1.1  # 10% boost for matching type
        
        # Get top k above threshold
        results = []
        for i, sim in enumerate(similarities):
            if sim >= min_similarity:
                results.append((candidate_keys[i], float(sim)))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def _evict_oldest(self):
        """Evict oldest entry (LRU)"""
        if self._keys_order:
            oldest_key = self._keys_order.pop(0)
            self.remove(oldest_key)
    
    def clear(self):
        """Clear all vectors"""
        self._vectors.clear()
        self._metadata.clear()
        self._keys_order.clear()
        self.cache_manager.invalidate("embedding_index", CacheLevel.SEMANTIC)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        return {
            "total_vectors": len(self._vectors),
            "dimension": self.dimension,
            "max_vectors": self.max_vectors,
            "memory_mb": len(self._vectors) * self.dimension * 4 / (1024 * 1024)  # float32
        }


class SemanticCache:
    """
    Semantic cache using embeddings for similarity matching
    
    Features:
    - Vector embedding based similarity (much more accurate)
    - Hybrid matching: exact hash + semantic similarity
    - Query type aware matching with intent extraction
    - Schema version validation
    - Redis persistence with vector index
    """
    
    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        embedder: Optional[BaseEmbedder] = None,
        similarity_threshold: float = 0.85,
        max_entries: int = 1000,
        enable_intent_matching: bool = True
    ):
        """
        Initialize embedding-based semantic cache
        
        Args:
            cache_manager: Cache manager for storage
            embedder: Embedding provider (auto-creates if None)
            similarity_threshold: Minimum similarity for cache hit (0-1)
            max_entries: Maximum cache entries
            enable_intent_matching: Enable query intent matching boost
        """
        self.cache_manager = cache_manager or get_cache_manager()
        self.embedder = embedder or get_default_embedder()
        self.similarity_threshold = float(os.getenv(
            "CACHE_SEMANTIC_THRESHOLD",
            str(similarity_threshold)
        ))
        self.max_entries = max_entries
        self.enable_intent_matching = enable_intent_matching
        self.normalizer = QueryNormalizer()
        
        # Initialize vector store
        self.vector_store = EmbeddingVectorStore(
            cache_manager=self.cache_manager,
            dimension=self.embedder.dimension,
            max_vectors=max_entries
        )
        
        # Stats
        self._exact_hits = 0
        self._semantic_hits = 0
        self._misses = 0
        
        logger.info(
            f"SemanticCache initialized: "
            f"embedder={type(self.embedder).__name__}, "
            f"dimension={self.embedder.dimension}, "
            f"threshold={self.similarity_threshold}"
        )
    
    def _compute_hash(self, normalized_question: str) -> str:
        """Compute hash key from normalized question"""
        return hashlib.sha256(normalized_question.encode()).hexdigest()[:16]
    
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
        Cache SQL result with embedding
        
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
        try:
            normalized = self.normalizer.normalize(question)
            cache_key = self._compute_hash(normalized)
            
            # Generate embedding
            embedding = self.embedder.embed_single(normalized)
            
            # Create entry
            entry = CachedSQLEntry(
                question=question,
                normalized_question=normalized,
                sql=sql,
                explanation=explanation,
                query_type=query_type,
                tables_used=tables_used or [],
                embedding=embedding.tolist(),
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
                # Add to vector store
                self.vector_store.add(
                    key=cache_key,
                    embedding=embedding,
                    query_type=query_type,
                    tables=tables_used,
                    schema_version=schema_version
                )
                logger.debug(f"Cached SQL with embedding: {cache_key[:8]}...")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cache SQL: {e}")
            return False
    
    def get_sql(
        self,
        question: str,
        schema_version: Optional[str] = None,
        allow_semantic: bool = True
    ) -> Optional[Tuple[CachedSQLEntry, float]]:
        """
        Get cached SQL for question using embedding similarity
        
        Args:
            question: Question to lookup
            schema_version: Expected schema version
            allow_semantic: Allow semantic matching (not just exact)
            
        Returns:
            Tuple of (CachedSQLEntry, similarity_score) or None
        """
        try:
            normalized = self.normalizer.normalize(question)
            cache_key = self._compute_hash(normalized)
            
            # Try exact match first
            cached_data = self.cache_manager.get(f"sql:{cache_key}", CacheLevel.SQL)
            if cached_data:
                entry = CachedSQLEntry.from_dict(cached_data)
                
                # Validate schema version
                if schema_version and entry.schema_version:
                    if entry.schema_version != schema_version:
                        logger.debug("Cache miss: schema version mismatch")
                        self._misses += 1
                        return None
                
                self._exact_hits += 1
                logger.debug(f"Exact cache hit: {cache_key[:8]}...")
                return (entry, 1.0)
            
            if not allow_semantic:
                self._misses += 1
                return None
            
            # Semantic search using embeddings
            query_embedding = self.embedder.embed_single(normalized)
            
            # Extract query intent for matching
            query_intent = None
            if self.enable_intent_matching:
                intent = self.normalizer.extract_query_intent(question)
                query_intent = intent.get("aggregation", "none")
                if query_intent == "none":
                    query_intent = intent.get("operation", "select")
            
            # Search vector store
            similar_entries = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=5,
                query_type=query_intent,
                schema_version=schema_version,
                min_similarity=self.similarity_threshold
            )
            
            # Find best match
            for matched_key, similarity in similar_entries:
                cached_data = self.cache_manager.get(f"sql:{matched_key}", CacheLevel.SQL)
                if not cached_data:
                    continue
                
                entry = CachedSQLEntry.from_dict(cached_data)
                
                # Double-check schema version
                if schema_version and entry.schema_version:
                    if entry.schema_version != schema_version:
                        continue
                
                self._semantic_hits += 1
                logger.info(
                    f"Semantic cache hit: similarity={similarity:.3f}, "
                    f"query_type={entry.query_type}"
                )
                return (entry, similarity)
            
            self._misses += 1
            return None
            
        except Exception as e:
            logger.error(f"Error in get_sql: {e}")
            self._misses += 1
            return None
    
    def invalidate_all(self):
        """Invalidate all cached SQL and embeddings"""
        self.cache_manager.invalidate_level(CacheLevel.SQL)
        self.vector_store.clear()
        self._exact_hits = 0
        self._semantic_hits = 0
        self._misses = 0
        logger.info("Embedding semantic cache invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._exact_hits + self._semantic_hits + self._misses
        
        return {
            "embedder": type(self.embedder).__name__,
            "embedding_dimension": self.embedder.dimension,
            "similarity_threshold": self.similarity_threshold,
            "max_entries": self.max_entries,
            "exact_hits": self._exact_hits,
            "semantic_hits": self._semantic_hits,
            "misses": self._misses,
            "hit_rate": (self._exact_hits + self._semantic_hits) / total_requests if total_requests > 0 else 0,
            "semantic_hit_rate": self._semantic_hits / total_requests if total_requests > 0 else 0,
            "vector_store": self.vector_store.get_stats()
        }


# Backwards compatibility aliases
SemanticSQLCache = SemanticCache
EmbeddingSemanticCache = SemanticCache


# Singleton instance
_semantic_cache: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """Get or create semantic cache singleton"""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
    return _semantic_cache


def reset_semantic_cache():
    """Reset semantic cache singleton"""
    global _semantic_cache
    if _semantic_cache:
        _semantic_cache.invalidate_all()
    _semantic_cache = None
