"""
Cache Manager for Prompt Caching

Multi-level caching with Redis backend for NL2SQL system.
Supports schema caching, prompt caching, and SQL result caching.
"""

import os
import json
import hashlib
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache levels with different TTLs and purposes"""
    SYSTEM = "system"       # System prompts - longest TTL
    SCHEMA = "schema"       # Schema cache - invalidated on schema change
    EXAMPLES = "examples"   # Few-shot examples - medium TTL
    PROMPT = "prompt"       # Built prompts - session-aware
    SQL = "sql"             # SQL results - shortest TTL
    SEMANTIC = "semantic"   # Semantic query cache


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    level: CacheLevel
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    hit_count: int = 0
    schema_version: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "key": self.key,
            "value": self.value,
            "level": self.level.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "hit_count": self.hit_count,
            "schema_version": self.schema_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Deserialize from dictionary"""
        return cls(
            key=data["key"],
            value=data["value"],
            level=CacheLevel(data["level"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            hit_count=data.get("hit_count", 0),
            schema_version=data.get("schema_version")
        )


@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0
    memory_usage_bytes: int = 0
    last_reset: datetime = field(default_factory=datetime.now)
    hits_by_level: Dict[str, int] = field(default_factory=dict)
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate percentage"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    def record_hit(self, level: CacheLevel):
        """Record a cache hit"""
        self.hits += 1
        level_key = level.value
        self.hits_by_level[level_key] = self.hits_by_level.get(level_key, 0) + 1
    
    def record_miss(self):
        """Record a cache miss"""
        self.misses += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 2),
            "evictions": self.evictions,
            "total_entries": self.total_entries,
            "memory_usage_bytes": self.memory_usage_bytes,
            "last_reset": self.last_reset.isoformat(),
            "hits_by_level": self.hits_by_level
        }
    
    def reset(self):
        """Reset metrics"""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.hits_by_level = {}
        self.last_reset = datetime.now()


class CacheConfig:
    """Cache configuration from environment"""
    
    def __init__(self):
        self.enabled = os.getenv("CACHE_ENABLED", "true").lower() == "true"
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # TTL settings (in seconds)
        self.ttl_system = int(os.getenv("CACHE_TTL_SYSTEM", "7200"))      # 2 hours
        self.ttl_schema = int(os.getenv("CACHE_TTL_SCHEMA", "3600"))      # 1 hour
        self.ttl_examples = int(os.getenv("CACHE_TTL_EXAMPLES", "3600"))  # 1 hour
        self.ttl_prompt = int(os.getenv("CACHE_TTL_PROMPT", "1800"))      # 30 min
        self.ttl_sql = int(os.getenv("CACHE_TTL_SQL", "600"))             # 10 min
        self.ttl_semantic = int(os.getenv("CACHE_TTL_SEMANTIC", "1800"))  # 30 min
        
        # Semantic cache settings
        self.semantic_threshold = float(os.getenv("CACHE_SEMANTIC_THRESHOLD", "0.85"))
        
        # Key prefix for namespacing
        self.key_prefix = os.getenv("CACHE_KEY_PREFIX", "nl2sql")
    
    def get_ttl(self, level: CacheLevel) -> int:
        """Get TTL for cache level"""
        ttl_map = {
            CacheLevel.SYSTEM: self.ttl_system,
            CacheLevel.SCHEMA: self.ttl_schema,
            CacheLevel.EXAMPLES: self.ttl_examples,
            CacheLevel.PROMPT: self.ttl_prompt,
            CacheLevel.SQL: self.ttl_sql,
            CacheLevel.SEMANTIC: self.ttl_semantic
        }
        return ttl_map.get(level, self.ttl_prompt)


class CacheManager:
    """
    Multi-level cache manager with Redis backend
    
    Features:
    - Multi-level caching (system, schema, examples, prompt, sql, semantic)
    - Redis backend with fallback to in-memory
    - TTL-based expiration per level
    - Schema version-aware invalidation
    - Performance metrics tracking
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize cache manager
        
        Args:
            config: Cache configuration (uses defaults from env if None)
        """
        self.config = config or CacheConfig()
        self.metrics = CacheMetrics()
        self._redis_client = None
        self._local_cache: Dict[str, CacheEntry] = {}  # Fallback cache
        self._current_schema_version: Optional[str] = None
        
        if self.config.enabled:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            import redis
            self._redis_client = redis.from_url(
                self.config.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self._redis_client.ping()
            logger.info(f"Redis cache connected: {self.config.redis_url}")
        except ImportError:
            logger.warning("Redis package not installed, using local cache only")
            self._redis_client = None
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using local cache.")
            self._redis_client = None
    
    def _make_key(self, key: str, level: CacheLevel) -> str:
        """Create namespaced cache key"""
        return f"{self.config.key_prefix}:{level.value}:{key}"
    
    def _hash_key(self, data: str) -> str:
        """Create hash key from string"""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def set(
        self,
        key: str,
        value: Any,
        level: CacheLevel,
        ttl: Optional[int] = None,
        schema_version: Optional[str] = None
    ) -> bool:
        """
        Set cache entry
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            level: Cache level
            ttl: Time-to-live in seconds (uses default for level if None)
            schema_version: Schema version for invalidation
            
        Returns:
            True if successful
        """
        if not self.config.enabled:
            return False
        
        full_key = self._make_key(key, level)
        ttl = ttl or self.config.get_ttl(level)
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        entry = CacheEntry(
            key=key,
            value=value,
            level=level,
            expires_at=expires_at,
            schema_version=schema_version or self._current_schema_version
        )
        
        try:
            if self._redis_client:
                # Store in Redis
                self._redis_client.setex(
                    full_key,
                    ttl,
                    json.dumps(entry.to_dict())
                )
            else:
                # Store in local cache
                self._local_cache[full_key] = entry
            
            self.metrics.total_entries += 1
            logger.debug(f"Cache SET: {full_key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Cache SET failed: {e}")
            return False
    
    def get(
        self,
        key: str,
        level: CacheLevel,
        check_schema_version: bool = True
    ) -> Optional[Any]:
        """
        Get cache entry
        
        Args:
            key: Cache key
            level: Cache level
            check_schema_version: Validate against current schema version
            
        Returns:
            Cached value or None if not found/expired
        """
        if not self.config.enabled:
            return None
        
        full_key = self._make_key(key, level)
        
        try:
            entry = None
            
            if self._redis_client:
                data = self._redis_client.get(full_key)
                if data:
                    entry = CacheEntry.from_dict(json.loads(data))
            else:
                entry = self._local_cache.get(full_key)
            
            if entry is None:
                self.metrics.record_miss()
                return None
            
            # Check expiration for local cache
            if not self._redis_client and entry.is_expired():
                self._local_cache.pop(full_key, None)
                self.metrics.record_miss()
                return None
            
            # Check schema version for schema-dependent caches
            if check_schema_version and level in (CacheLevel.SCHEMA, CacheLevel.EXAMPLES, CacheLevel.PROMPT):
                if entry.schema_version and entry.schema_version != self._current_schema_version:
                    self.invalidate(key, level)
                    self.metrics.record_miss()
                    logger.debug(f"Cache MISS (schema mismatch): {full_key}")
                    return None
            
            # Update hit count in Redis
            if self._redis_client:
                entry.hit_count += 1
                self._redis_client.setex(
                    full_key,
                    self._redis_client.ttl(full_key),
                    json.dumps(entry.to_dict())
                )
            else:
                entry.hit_count += 1
            
            self.metrics.record_hit(level)
            logger.debug(f"Cache HIT: {full_key}")
            return entry.value
            
        except Exception as e:
            logger.error(f"Cache GET failed: {e}")
            self.metrics.record_miss()
            return None
    
    def invalidate(self, key: str, level: CacheLevel) -> bool:
        """Invalidate specific cache entry"""
        if not self.config.enabled:
            return False
        
        full_key = self._make_key(key, level)
        
        try:
            if self._redis_client:
                self._redis_client.delete(full_key)
            else:
                self._local_cache.pop(full_key, None)
            
            self.metrics.evictions += 1
            logger.debug(f"Cache INVALIDATE: {full_key}")
            return True
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return False
    
    def invalidate_level(self, level: CacheLevel) -> int:
        """Invalidate all entries at a cache level"""
        if not self.config.enabled:
            return 0
        
        pattern = f"{self.config.key_prefix}:{level.value}:*"
        count = 0
        
        try:
            if self._redis_client:
                keys = self._redis_client.keys(pattern)
                if keys:
                    count = self._redis_client.delete(*keys)
            else:
                keys_to_delete = [k for k in self._local_cache if k.startswith(f"{self.config.key_prefix}:{level.value}:")]
                for k in keys_to_delete:
                    self._local_cache.pop(k, None)
                    count += 1
            
            self.metrics.evictions += count
            logger.info(f"Cache level invalidated: {level.value} ({count} entries)")
            return count
        except Exception as e:
            logger.error(f"Level invalidation failed: {e}")
            return 0
    
    def invalidate_schema_dependent(self) -> int:
        """Invalidate all schema-dependent caches"""
        count = 0
        for level in [CacheLevel.SCHEMA, CacheLevel.EXAMPLES, CacheLevel.PROMPT]:
            count += self.invalidate_level(level)
        return count
    
    def update_schema_version(self, version: str) -> bool:
        """
        Update current schema version and invalidate if changed
        
        Args:
            version: New schema version hash
            
        Returns:
            True if schema changed
        """
        if version == self._current_schema_version:
            return False
        
        old_version = self._current_schema_version
        self._current_schema_version = version
        
        if old_version is not None:
            # Schema changed, invalidate dependent caches
            count = self.invalidate_schema_dependent()
            logger.info(f"Schema version updated: {old_version} -> {version} (invalidated {count} entries)")
        
        return True
    
    def clear_all(self) -> int:
        """Clear all cache entries"""
        if not self.config.enabled:
            return 0
        
        pattern = f"{self.config.key_prefix}:*"
        count = 0
        
        try:
            if self._redis_client:
                keys = self._redis_client.keys(pattern)
                if keys:
                    count = self._redis_client.delete(*keys)
            else:
                count = len(self._local_cache)
                self._local_cache.clear()
            
            self.metrics.evictions += count
            self.metrics.total_entries = 0
            logger.info(f"Cache cleared: {count} entries")
            return count
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        metrics = self.metrics.to_dict()
        
        # Add Redis info if available
        if self._redis_client:
            try:
                info = self._redis_client.info("memory")
                metrics["redis_memory_used"] = info.get("used_memory_human", "unknown")
                metrics["redis_connected"] = True
            except:
                metrics["redis_connected"] = False
        else:
            metrics["redis_connected"] = False
            metrics["using_local_cache"] = True
        
        metrics["cache_enabled"] = self.config.enabled
        metrics["current_schema_version"] = self._current_schema_version
        
        return metrics
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        health = {
            "status": "healthy",
            "cache_enabled": self.config.enabled,
            "redis_connected": False,
            "latency_ms": None
        }
        
        if not self.config.enabled:
            health["status"] = "disabled"
            return health
        
        try:
            if self._redis_client:
                start = time.time()
                self._redis_client.ping()
                health["latency_ms"] = round((time.time() - start) * 1000, 2)
                health["redis_connected"] = True
            else:
                health["status"] = "degraded"
                health["message"] = "Using local cache (Redis unavailable)"
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
    
    # Convenience methods for specific cache types
    
    def cache_system_prompt(self, prompt_key: str, prompt: str) -> bool:
        """Cache system prompt"""
        return self.set(prompt_key, prompt, CacheLevel.SYSTEM)
    
    def get_system_prompt(self, prompt_key: str) -> Optional[str]:
        """Get cached system prompt"""
        return self.get(prompt_key, CacheLevel.SYSTEM, check_schema_version=False)
    
    def cache_schema(self, schema_data: Dict[str, Any], version: str) -> bool:
        """Cache schema with version"""
        self.update_schema_version(version)
        return self.set(f"schema:{version}", schema_data, CacheLevel.SCHEMA, schema_version=version)
    
    def get_schema(self, version: str) -> Optional[Dict[str, Any]]:
        """Get cached schema by version"""
        return self.get(f"schema:{version}", CacheLevel.SCHEMA)
    
    def cache_examples(self, query_type: str, examples: List[Dict]) -> bool:
        """Cache few-shot examples by query type"""
        return self.set(f"examples:{query_type}", examples, CacheLevel.EXAMPLES)
    
    def get_examples(self, query_type: str) -> Optional[List[Dict]]:
        """Get cached examples"""
        return self.get(f"examples:{query_type}", CacheLevel.EXAMPLES)
    
    def cache_sql(self, question_hash: str, sql: str, explanation: str = "") -> bool:
        """Cache SQL result"""
        return self.set(
            f"sql:{question_hash}",
            {"sql": sql, "explanation": explanation},
            CacheLevel.SQL
        )
    
    def get_sql(self, question_hash: str) -> Optional[Dict[str, str]]:
        """Get cached SQL result"""
        return self.get(f"sql:{question_hash}", CacheLevel.SQL)


# Singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create cache manager singleton"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def reset_cache_manager():
    """Reset cache manager singleton (for testing)"""
    global _cache_manager
    if _cache_manager:
        _cache_manager.clear_all()
    _cache_manager = None
