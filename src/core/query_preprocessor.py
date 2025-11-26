"""
Query Preprocessor Module
Handles question preprocessing, classification, and Vietnamese support
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of SQL queries based on user intent"""
    LOOKUP = "lookup"           # Simple SELECT without aggregation
    AGGREGATION = "aggregation" # COUNT, SUM, AVG, etc.
    FILTER = "filter"           # WHERE conditions focused
    JOIN = "join"               # Multi-table queries
    GROUPBY = "groupby"         # GROUP BY with aggregation
    RANKING = "ranking"         # TOP N, ORDER BY focused
    NESTED = "nested"           # Subqueries needed
    SCHEMA = "schema"           # Schema/metadata questions
    UNKNOWN = "unknown"


@dataclass
class ProcessedQuery:
    """Result of query preprocessing"""
    original: str
    normalized: str
    query_type: QueryType
    entities: List[str]           # Extracted entities (table/column names)
    keywords: List[str]           # Important keywords
    time_references: List[str]    # Date/time references
    aggregations: List[str]       # Aggregation keywords found
    confidence: float             # Classification confidence


# Vietnamese to English synonyms mapping
VIETNAMESE_SYNONYMS = {
    # Aggregations
    "tổng": "sum total",
    "tổng cộng": "sum total",
    "đếm": "count",
    "số lượng": "count",
    "bao nhiêu": "count how many",
    "trung bình": "average avg",
    "cao nhất": "max maximum highest",
    "thấp nhất": "min minimum lowest",
    "lớn nhất": "max maximum largest",
    "nhỏ nhất": "min minimum smallest",
    
    # Time
    "hôm nay": "today",
    "hôm qua": "yesterday",
    "tuần này": "this week",
    "tuần trước": "last week",
    "tháng này": "this month",
    "tháng trước": "last month",
    "năm nay": "this year",
    "năm ngoái": "last year",
    "quý này": "this quarter",
    "quý trước": "last quarter",
    "gần đây": "recent recently",
    
    # Entities
    "khách hàng": "customer client",
    "người dùng": "user",
    "đơn hàng": "order",
    "sản phẩm": "product item",
    "doanh thu": "revenue sales amount",
    "doanh số": "sales revenue",
    "giá": "price",
    "giá trị": "value amount",
    "nhân viên": "employee staff",
    "danh mục": "category",
    "thanh toán": "payment",
    "giao hàng": "shipping delivery",
    "địa chỉ": "address",
    "đánh giá": "review rating",
    "bình luận": "comment review",
    
    # Actions
    "hiển thị": "show display list",
    "cho tôi biết": "show tell",
    "cho tôi xem": "show display",
    "liệt kê": "list show",
    "tìm": "find search",
    "tìm kiếm": "find search",
    "lấy": "get retrieve",
    "xem": "view show",
    "so sánh": "compare",
    "phân tích": "analyze",
    "thống kê": "statistics stats",
    
    # Filters
    "lớn hơn": "greater than more than",
    "nhỏ hơn": "less than fewer than",
    "bằng": "equal equals",
    "từ": "from since",
    "đến": "to until",
    "trong khoảng": "between range",
    "chứa": "contains includes",
    "bắt đầu bằng": "starts with",
    "kết thúc bằng": "ends with",
    
    # Ordering
    "sắp xếp": "order sort",
    "tăng dần": "ascending asc",
    "giảm dần": "descending desc",
    "top": "top best",
    "đầu tiên": "first top",
    "cuối cùng": "last bottom",
    
    # Grouping
    "theo": "by per",
    "nhóm theo": "group by",
    "mỗi": "each per every",
    
    # Schema
    "cấu trúc": "structure schema",
    "bảng": "table tables",
    "cột": "column columns field",
    "trường": "field column",
    "database": "database db",
    "cơ sở dữ liệu": "database",
}

# Query type detection patterns
QUERY_TYPE_PATTERNS = {
    QueryType.SCHEMA: [
        r'\b(schema|cấu trúc|structure)\b',
        r'\b(tables?|bảng)\b.*\b(list|liệt kê|có gì|nào|what)\b',
        r'\b(describe|mô tả)\b.*\b(database|db|table|bảng)\b',
        r'\bshow\s+(tables?|databases?)\b',
    ],
    QueryType.AGGREGATION: [
        r'\b(count|đếm|số lượng|bao nhiêu|how many)\b',
        r'\b(sum|total|tổng|tổng cộng)\b',
        r'\b(average|avg|trung bình)\b',
        r'\b(max|min|cao nhất|thấp nhất|lớn nhất|nhỏ nhất|highest|lowest)\b',
    ],
    QueryType.RANKING: [
        r'\b(top|first|last|đầu tiên|cuối)\s*\d*\b',
        r'\b(most|least|best|worst)\b',
        r'\b(ranking|rank|xếp hạng)\b',
        r'\blargest|smallest|highest|lowest\b',
    ],
    QueryType.GROUPBY: [
        r'\b(group\s*by|nhóm theo)\b',
        r'\b(by|theo|per|mỗi)\s+\w+',
        r'\beach\s+\w+',
        r'\bper\s+(day|week|month|year|ngày|tuần|tháng|năm)\b',
    ],
    QueryType.JOIN: [
        r'\b(with|và|cùng với|along with)\b.*\b(information|info|thông tin|details)\b',
        r'\b(from|của)\s+\w+\s+(and|và)\s+\w+\b',
        r'\b(join|kết hợp|liên kết)\b',
        r'multiple tables referenced',
    ],
    QueryType.FILTER: [
        r'\b(where|filter|lọc|điều kiện)\b',
        r'\b(greater|less|more|fewer|larger|smaller|lớn hơn|nhỏ hơn)\s*(than)?\b',
        r'\b(equal|equals|bằng|=)\b',
        r'\b(between|từ.*đến|trong khoảng)\b',
        r'\b(contains|chứa|like|giống)\b',
    ],
    QueryType.NESTED: [
        r'\b(not in|không trong|exclude|loại trừ)\b',
        r'\b(subquery|nested)\b',
        r'\bthose (who|which|that)\s+(do not|don\'t|haven\'t|không)\b',
    ],
}

# Time pattern extraction
TIME_PATTERNS = [
    (r'\b(today|hôm nay)\b', "CURDATE()"),
    (r'\b(yesterday|hôm qua)\b', "CURDATE() - INTERVAL 1 DAY"),
    (r'\b(this week|tuần này)\b', "YEARWEEK(CURDATE())"),
    (r'\b(last week|tuần trước)\b', "YEARWEEK(CURDATE() - INTERVAL 1 WEEK)"),
    (r'\b(this month|tháng này)\b', "MONTH(CURDATE()) AND YEAR(CURDATE())"),
    (r'\b(last month|tháng trước)\b', "MONTH(CURDATE() - INTERVAL 1 MONTH)"),
    (r'\b(this year|năm nay)\b', "YEAR(CURDATE())"),
    (r'\b(last year|năm ngoái)\b', "YEAR(CURDATE()) - 1"),
    (r'\blast\s*(\d+)\s*(days?|ngày)\b', r"CURDATE() - INTERVAL \1 DAY"),
    (r'\blast\s*(\d+)\s*(months?|tháng)\b', r"CURDATE() - INTERVAL \1 MONTH"),
]

# Aggregation keywords
AGGREGATION_KEYWORDS = {
    "count": ["count", "đếm", "số lượng", "bao nhiêu", "how many"],
    "sum": ["sum", "total", "tổng", "tổng cộng"],
    "avg": ["average", "avg", "trung bình", "mean"],
    "max": ["max", "maximum", "cao nhất", "lớn nhất", "highest", "largest"],
    "min": ["min", "minimum", "thấp nhất", "nhỏ nhất", "lowest", "smallest"],
}


class QueryPreprocessor:
    """
    Preprocesses natural language queries for better SQL generation
    
    Features:
    - Vietnamese to English normalization
    - Query type classification
    - Entity extraction
    - Time reference detection
    """
    
    def __init__(self, table_names: List[str] = None, column_names: List[str] = None):
        """
        Initialize preprocessor
        
        Args:
            table_names: List of valid table names for entity matching
            column_names: List of valid column names for entity matching
        """
        self.table_names = set(t.lower() for t in (table_names or []))
        self.column_names = set(c.lower() for c in (column_names or []))
        
        # Build reverse synonym map for quick lookup
        self._build_synonym_index()
    
    def _build_synonym_index(self):
        """Build index for fast synonym lookup"""
        self.synonym_index = {}
        for vn, en in VIETNAMESE_SYNONYMS.items():
            self.synonym_index[vn.lower()] = en
    
    def process(self, question: str) -> ProcessedQuery:
        """
        Process a natural language question
        
        Args:
            question: Raw user question
            
        Returns:
            ProcessedQuery with normalized text and metadata
        """
        # Normalize text
        normalized = self._normalize_text(question)
        
        # Classify query type
        query_type, confidence = self._classify_query(normalized)
        
        # Extract entities
        entities = self._extract_entities(normalized)
        
        # Extract keywords
        keywords = self._extract_keywords(normalized)
        
        # Extract time references
        time_refs = self._extract_time_references(normalized)
        
        # Extract aggregations
        aggregations = self._extract_aggregations(normalized)
        
        return ProcessedQuery(
            original=question,
            normalized=normalized,
            query_type=query_type,
            entities=entities,
            keywords=keywords,
            time_references=time_refs,
            aggregations=aggregations,
            confidence=confidence
        )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize Vietnamese text and expand synonyms"""
        normalized = text.lower().strip()
        
        # Replace Vietnamese synonyms with English equivalents
        for vn, en in VIETNAMESE_SYNONYMS.items():
            pattern = r'\b' + re.escape(vn) + r'\b'
            if re.search(pattern, normalized, re.IGNORECASE):
                # Keep both Vietnamese and English for LLM
                normalized = re.sub(pattern, f"{vn} ({en})", normalized, flags=re.IGNORECASE)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized
    
    def _classify_query(self, text: str) -> Tuple[QueryType, float]:
        """
        Classify query type based on patterns
        
        Returns:
            Tuple of (QueryType, confidence)
        """
        text_lower = text.lower()
        scores = {qt: 0 for qt in QueryType}
        
        for query_type, patterns in QUERY_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    scores[query_type] += 1
        
        # Find highest scoring type
        max_type = max(scores, key=scores.get)
        max_score = scores[max_type]
        
        if max_score == 0:
            return QueryType.LOOKUP, 0.5  # Default to simple lookup
        
        # Calculate confidence based on score
        total_patterns = sum(len(p) for p in QUERY_TYPE_PATTERNS.values())
        confidence = min(0.5 + (max_score * 0.2), 1.0)
        
        return max_type, confidence
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract potential table/column names from text"""
        entities = []
        text_lower = text.lower()
        
        # Check for table names
        for table in self.table_names:
            if table in text_lower:
                entities.append(table)
        
        # Check for column names
        for column in self.column_names:
            if column in text_lower:
                entities.append(column)
        
        return list(set(entities))
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords for query understanding"""
        keywords = []
        text_lower = text.lower()
        
        # SQL-related keywords
        sql_keywords = [
            "select", "where", "order", "group", "having", "join",
            "and", "or", "not", "in", "between", "like", "null",
            "count", "sum", "avg", "max", "min", "distinct"
        ]
        
        for kw in sql_keywords:
            if kw in text_lower:
                keywords.append(kw)
        
        return keywords
    
    def _extract_time_references(self, text: str) -> List[str]:
        """Extract time-related references"""
        refs = []
        text_lower = text.lower()
        
        for pattern, sql_expr in TIME_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                refs.append(match.group(0))
        
        return refs
    
    def _extract_aggregations(self, text: str) -> List[str]:
        """Extract aggregation functions mentioned"""
        found = []
        text_lower = text.lower()
        
        for agg_type, keywords in AGGREGATION_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    found.append(agg_type)
                    break
        
        return list(set(found))
    
    def get_query_template(self, query_type: QueryType) -> str:
        """
        Get SQL template hint for query type
        
        Args:
            query_type: Classified query type
            
        Returns:
            Template hint string
        """
        templates = {
            QueryType.LOOKUP: "SELECT columns FROM table WHERE conditions LIMIT n",
            QueryType.AGGREGATION: "SELECT AGG_FUNC(column) FROM table WHERE conditions",
            QueryType.FILTER: "SELECT columns FROM table WHERE complex_conditions",
            QueryType.JOIN: "SELECT t1.cols, t2.cols FROM t1 JOIN t2 ON t1.key = t2.key",
            QueryType.GROUPBY: "SELECT col, AGG(col2) FROM table GROUP BY col",
            QueryType.RANKING: "SELECT columns FROM table ORDER BY col DESC LIMIT n",
            QueryType.NESTED: "SELECT cols FROM t1 WHERE col IN (SELECT col FROM t2)",
            QueryType.SCHEMA: "-- Schema query: return metadata",
            QueryType.UNKNOWN: "SELECT columns FROM table",
        }
        return templates.get(query_type, templates[QueryType.UNKNOWN])


def preprocess_question(
    question: str,
    table_names: List[str] = None,
    column_names: List[str] = None
) -> ProcessedQuery:
    """
    Convenience function to preprocess a question
    
    Args:
        question: User's question
        table_names: Valid table names
        column_names: Valid column names
        
    Returns:
        ProcessedQuery object
    """
    preprocessor = QueryPreprocessor(table_names, column_names)
    return preprocessor.process(question)
