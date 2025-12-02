"""
Query Plan Cache Module
Caches SQL query templates/plans for similar query patterns to avoid redundant LLM calls
"""

import re
import json
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import OrderedDict

logger = logging.getLogger(__name__)


class QueryPattern(Enum):
    """Common query patterns"""
    TOP_N = "top_n"                    # "top N items by metric"
    COUNT = "count"                     # "how many X"
    AGGREGATE = "aggregate"             # "total/sum/average of X"
    LIST = "list"                       # "list/show all X"
    FILTER = "filter"                   # "X where condition"
    TIME_RANGE = "time_range"           # "X in last N days/months"
    COMPARISON = "comparison"           # "compare X and Y"
    RANKING = "ranking"                 # "rank X by Y"
    GROUP_BY = "group_by"               # "X by category/group"
    JOIN = "join"                       # "X with related Y"
    EXISTS = "exists"                   # "X that have/don't have Y"
    UNKNOWN = "unknown"


@dataclass
class QueryPlan:
    """A cached query execution plan"""
    pattern: QueryPattern
    sql_template: str
    parameters: Dict[str, Any]
    tables_used: List[str]
    columns_used: List[str]
    confidence: float
    created_at: datetime = field(default_factory=datetime.now)
    hit_count: int = 0
    last_used: datetime = field(default_factory=datetime.now)
    
    # Metadata for template filling
    placeholders: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pattern": self.pattern.value,
            "sql_template": self.sql_template,
            "parameters": self.parameters,
            "tables_used": self.tables_used,
            "columns_used": self.columns_used,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "hit_count": self.hit_count,
            "placeholders": self.placeholders
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueryPlan":
        """Create from dictionary"""
        return cls(
            pattern=QueryPattern(data["pattern"]),
            sql_template=data["sql_template"],
            parameters=data.get("parameters", {}),
            tables_used=data.get("tables_used", []),
            columns_used=data.get("columns_used", []),
            confidence=data.get("confidence", 0.8),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            hit_count=data.get("hit_count", 0),
            placeholders=data.get("placeholders", [])
        )


@dataclass
class PatternMatch:
    """Result of pattern matching"""
    pattern: QueryPattern
    confidence: float
    extracted_params: Dict[str, Any]
    normalized_question: str


class QueryPatternDetector:
    """
    Detects query patterns from natural language questions
    Uses regex and keyword matching for fast pattern detection
    """
    
    # Pattern definitions with regex and keywords
    PATTERNS = {
        QueryPattern.TOP_N: {
            "regex": [
                r"top\s+(\d+)",
                r"first\s+(\d+)",
                r"best\s+(\d+)",
                r"highest\s+(\d+)",
                r"lowest\s+(\d+)"
            ],
            "keywords": ["top", "best", "highest", "lowest", "first", "leading"],
            "extract": {"limit": r"(?:top|first|best|highest|lowest)\s+(\d+)"}
        },
        QueryPattern.COUNT: {
            "regex": [
                r"how many",
                r"count of",
                r"number of",
                r"total count"
            ],
            "keywords": ["how many", "count", "number of", "total number"],
            "extract": {}
        },
        QueryPattern.AGGREGATE: {
            "regex": [
                r"(?:total|sum|average|avg|mean|min|max|minimum|maximum)\s+(?:of\s+)?",
                r"what is the (?:total|sum|average)"
            ],
            "keywords": ["total", "sum", "average", "avg", "mean", "min", "max"],
            "extract": {"agg_func": r"(total|sum|average|avg|mean|min|max|minimum|maximum)"}
        },
        QueryPattern.LIST: {
            "regex": [
                r"^(?:list|show|display|get|fetch)\s+(?:all\s+)?",
                r"^what are",
                r"^give me"
            ],
            "keywords": ["list", "show", "display", "all", "get all"],
            "extract": {}
        },
        QueryPattern.TIME_RANGE: {
            "regex": [
                r"(?:in|from|during)\s+(?:the\s+)?(?:last|past)\s+(\d+)\s*(day|week|month|year)s?",
                r"(?:this|current)\s+(week|month|year)",
                r"(?:yesterday|today|last week|last month)"
            ],
            "keywords": ["last", "past", "recent", "this week", "this month", "yesterday", "today"],
            "extract": {
                "time_value": r"(?:last|past)\s+(\d+)",
                "time_unit": r"(?:last|past)\s+\d+\s*(day|week|month|year)s?"
            }
        },
        QueryPattern.FILTER: {
            "regex": [
                r"(?:where|with|having|that have|that has)\s+",
                r"(?:greater|less|more|fewer)\s+than",
                r"(?:equal|equals)\s+to"
            ],
            "keywords": ["where", "with", "having", "greater than", "less than", "equal"],
            "extract": {}
        },
        QueryPattern.GROUP_BY: {
            "regex": [
                r"(?:by|per|for each|grouped by)\s+(\w+)",
                r"breakdown\s+by"
            ],
            "keywords": ["by", "per", "each", "grouped", "breakdown"],
            "extract": {"group_column": r"(?:by|per|for each)\s+(\w+)"}
        },
        QueryPattern.EXISTS: {
            "regex": [
                r"(?:that|who|which)\s+(?:have|has|had|never|don't have|doesn't have)",
                r"without\s+(?:any\s+)?"
            ],
            "keywords": ["never", "without", "don't have", "no orders", "no purchases"],
            "extract": {}
        },
        QueryPattern.RANKING: {
            "regex": [
                r"rank(?:ed|ing)?\s+by",
                r"order(?:ed)?\s+by"
            ],
            "keywords": ["rank", "ranked", "ranking", "order by", "sorted"],
            "extract": {}
        },
        QueryPattern.COMPARISON: {
            "regex": [
                r"compare\s+",
                r"(?:versus|vs\.?)\s+",
                r"difference\s+between"
            ],
            "keywords": ["compare", "versus", "vs", "difference", "comparison"],
            "extract": {}
        }
    }
    
    def detect_pattern(self, question: str) -> PatternMatch:
        """
        Detect the query pattern from a natural language question
        
        Args:
            question: Natural language question
            
        Returns:
            PatternMatch with detected pattern and extracted parameters
        """
        question_lower = question.lower().strip()
        
        best_match = None
        best_confidence = 0.0
        
        for pattern, config in self.PATTERNS.items():
            confidence = 0.0
            
            # Check regex patterns
            for regex in config["regex"]:
                if re.search(regex, question_lower):
                    confidence = max(confidence, 0.8)
                    break
            
            # Check keywords
            keyword_matches = sum(
                1 for kw in config["keywords"] 
                if kw in question_lower
            )
            if keyword_matches > 0:
                keyword_conf = min(0.3 * keyword_matches, 0.6)
                confidence = max(confidence, keyword_conf)
            
            if confidence > best_confidence:
                best_confidence = confidence
                # Extract parameters
                extracted = {}
                for param_name, param_regex in config.get("extract", {}).items():
                    match = re.search(param_regex, question_lower)
                    if match:
                        extracted[param_name] = match.group(1)
                
                best_match = PatternMatch(
                    pattern=pattern,
                    confidence=confidence,
                    extracted_params=extracted,
                    normalized_question=question_lower
                )
        
        if best_match is None or best_confidence < 0.3:
            return PatternMatch(
                pattern=QueryPattern.UNKNOWN,
                confidence=0.0,
                extracted_params={},
                normalized_question=question_lower
            )
        
        return best_match


class QueryPlanCache:
    """
    Caches query plans (SQL templates) for reuse
    
    Features:
    - Pattern-based caching (similar patterns share plans)
    - LRU eviction for memory management
    - Template parameterization
    - Statistics tracking
    """
    
    def __init__(
        self,
        max_size: int = 500,
        ttl_hours: int = 24,
        min_confidence: float = 0.7
    ):
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        self.min_confidence = min_confidence
        
        # LRU cache using OrderedDict
        self._cache: OrderedDict[str, QueryPlan] = OrderedDict()
        
        # Pattern detector
        self.detector = QueryPatternDetector()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._pattern_stats: Dict[str, int] = {}
    
    def _generate_cache_key(
        self,
        pattern: QueryPattern,
        tables: List[str],
        params: Dict[str, Any]
    ) -> str:
        """Generate cache key from pattern, tables, and key parameters"""
        key_data = {
            "pattern": pattern.value,
            "tables": sorted(tables),
            "key_params": {
                k: v for k, v in params.items()
                if k in ["agg_func", "group_column"]  # Only structural params
            }
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()[:16]
    
    def _normalize_sql_to_template(
        self,
        sql: str,
        params: Dict[str, Any]
    ) -> Tuple[str, List[str]]:
        """
        Convert SQL to template by replacing specific values with placeholders
        
        Returns:
            Tuple of (template_sql, list of placeholder names)
        """
        template = sql
        placeholders = []
        
        # Replace LIMIT values
        limit_match = re.search(r"LIMIT\s+(\d+)", template, re.IGNORECASE)
        if limit_match:
            template = re.sub(
                r"LIMIT\s+\d+",
                "LIMIT {limit}",
                template,
                flags=re.IGNORECASE
            )
            placeholders.append("limit")
        
        # Replace date/time ranges
        date_patterns = [
            (r"'\d{4}-\d{2}-\d{2}'", "{date_value}"),
            (r"INTERVAL\s+\d+\s+(DAY|WEEK|MONTH|YEAR)", "INTERVAL {time_value} {time_unit}"),
            (r"DATE_SUB\([^,]+,\s*INTERVAL\s+\d+", "DATE_SUB(NOW(), INTERVAL {time_value}")
        ]
        for pattern, replacement in date_patterns:
            if re.search(pattern, template, re.IGNORECASE):
                template = re.sub(pattern, replacement, template, flags=re.IGNORECASE)
                placeholders.extend(["date_value", "time_value", "time_unit"])
        
        # Replace specific numeric thresholds
        # e.g., "rating > 4.5" -> "rating > {threshold}"
        threshold_match = re.search(r"([<>=]+)\s*(\d+\.?\d*)", template)
        if threshold_match and "threshold" in params:
            template = re.sub(
                r"([<>=]+)\s*\d+\.?\d*",
                r"\1 {threshold}",
                template
            )
            placeholders.append("threshold")
        
        return template, list(set(placeholders))
    
    def get(
        self,
        question: str,
        tables_hint: Optional[List[str]] = None
    ) -> Optional[Tuple[QueryPlan, Dict[str, Any]]]:
        """
        Get cached query plan for a question
        
        Args:
            question: Natural language question
            tables_hint: Optional hint about tables involved
            
        Returns:
            Tuple of (QueryPlan, runtime_params) if found, None otherwise
        """
        # Detect pattern
        match = self.detector.detect_pattern(question)
        
        if match.pattern == QueryPattern.UNKNOWN or match.confidence < self.min_confidence:
            self._misses += 1
            return None
        
        # Generate cache key
        tables = tables_hint or []
        cache_key = self._generate_cache_key(
            match.pattern,
            tables,
            match.extracted_params
        )
        
        # Check cache
        if cache_key in self._cache:
            plan = self._cache[cache_key]
            
            # Check TTL
            if datetime.now() - plan.created_at > self.ttl:
                del self._cache[cache_key]
                self._misses += 1
                return None
            
            # Move to end (LRU)
            self._cache.move_to_end(cache_key)
            
            # Update stats
            plan.hit_count += 1
            plan.last_used = datetime.now()
            self._hits += 1
            self._pattern_stats[match.pattern.value] = \
                self._pattern_stats.get(match.pattern.value, 0) + 1
            
            logger.info(f"Query plan cache HIT: {match.pattern.value} (key: {cache_key})")
            
            # Return plan with runtime parameters
            runtime_params = self._extract_runtime_params(question, match, plan)
            return plan, runtime_params
        
        self._misses += 1
        return None
    
    def put(
        self,
        question: str,
        sql: str,
        tables_used: List[str],
        columns_used: List[str],
        confidence: float = 0.8
    ) -> Optional[str]:
        """
        Cache a query plan
        
        Args:
            question: Original question
            sql: Generated SQL
            tables_used: Tables in the query
            columns_used: Columns in the query
            confidence: Confidence score
            
        Returns:
            Cache key if stored, None if pattern not detected
        """
        # Detect pattern
        match = self.detector.detect_pattern(question)
        
        if match.pattern == QueryPattern.UNKNOWN:
            logger.debug(f"Skipping cache: unknown pattern for '{question[:50]}...'")
            return None
        
        # Generate cache key
        cache_key = self._generate_cache_key(
            match.pattern,
            tables_used,
            match.extracted_params
        )
        
        # Check if already exists
        if cache_key in self._cache:
            logger.debug(f"Plan already cached: {cache_key}")
            return cache_key
        
        # Normalize SQL to template
        sql_template, placeholders = self._normalize_sql_to_template(
            sql,
            match.extracted_params
        )
        
        # Create plan
        plan = QueryPlan(
            pattern=match.pattern,
            sql_template=sql_template,
            parameters=match.extracted_params,
            tables_used=tables_used,
            columns_used=columns_used,
            confidence=confidence,
            placeholders=placeholders
        )
        
        # Evict if needed
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # Remove oldest
        
        # Store
        self._cache[cache_key] = plan
        
        logger.info(f"Cached query plan: {match.pattern.value} (key: {cache_key})")
        
        return cache_key
    
    def _extract_runtime_params(
        self,
        question: str,
        match: PatternMatch,
        plan: QueryPlan
    ) -> Dict[str, Any]:
        """
        Extract runtime parameters from question to fill template
        """
        params = {}
        question_lower = question.lower()
        
        # Extract limit
        if "limit" in plan.placeholders:
            limit_match = re.search(r"(?:top|first|best)\s+(\d+)", question_lower)
            if limit_match:
                params["limit"] = int(limit_match.group(1))
            else:
                params["limit"] = 10  # Default
        
        # Extract time values
        if "time_value" in plan.placeholders:
            time_match = re.search(r"(?:last|past)\s+(\d+)\s*(day|week|month|year)", question_lower)
            if time_match:
                params["time_value"] = int(time_match.group(1))
                params["time_unit"] = time_match.group(2).upper()
            else:
                params["time_value"] = 7
                params["time_unit"] = "DAY"
        
        # Extract threshold values
        if "threshold" in plan.placeholders:
            threshold_match = re.search(r"(?:above|over|greater than|more than)\s+(\d+\.?\d*)", question_lower)
            if threshold_match:
                params["threshold"] = float(threshold_match.group(1))
        
        # Merge with extracted params from pattern matching
        params.update(match.extracted_params)
        
        return params
    
    def fill_template(
        self,
        plan: QueryPlan,
        params: Dict[str, Any]
    ) -> str:
        """
        Fill SQL template with runtime parameters
        
        Args:
            plan: Query plan with template
            params: Runtime parameters
            
        Returns:
            Filled SQL query
        """
        sql = plan.sql_template
        
        for key, value in params.items():
            placeholder = "{" + key + "}"
            if placeholder in sql:
                sql = sql.replace(placeholder, str(value))
        
        return sql
    
    def invalidate(self, pattern: Optional[QueryPattern] = None):
        """
        Invalidate cache entries
        
        Args:
            pattern: If provided, only invalidate entries with this pattern
        """
        if pattern is None:
            self._cache.clear()
            logger.info("Query plan cache cleared")
        else:
            keys_to_remove = [
                key for key, plan in self._cache.items()
                if plan.pattern == pattern
            ]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"Invalidated {len(keys_to_remove)} plans for pattern: {pattern.value}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "pattern_stats": self._pattern_stats,
            "most_used_patterns": sorted(
                self._pattern_stats.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
    
    def reset_stats(self):
        """Reset statistics"""
        self._hits = 0
        self._misses = 0
        self._pattern_stats.clear()


# Global instance
_query_plan_cache: Optional[QueryPlanCache] = None


def get_query_plan_cache(
    max_size: int = 500,
    ttl_hours: int = 24
) -> QueryPlanCache:
    """Get or create the global query plan cache"""
    global _query_plan_cache
    if _query_plan_cache is None:
        _query_plan_cache = QueryPlanCache(max_size=max_size, ttl_hours=ttl_hours)
    return _query_plan_cache


def reset_query_plan_cache():
    """Reset the global query plan cache"""
    global _query_plan_cache
    if _query_plan_cache:
        _query_plan_cache.invalidate()
    _query_plan_cache = None
