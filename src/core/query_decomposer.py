"""
Query Decomposition Module
Handles complex multi-part questions by breaking them into simpler sub-queries
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DecompositionStrategy(Enum):
    """Strategy for decomposing complex queries"""
    SEQUENTIAL = "sequential"      # Sub-queries depend on each other
    PARALLEL = "parallel"          # Sub-queries are independent
    NESTED = "nested"              # Sub-queries form nested structure
    SINGLE = "single"              # No decomposition needed


@dataclass
class SubQuery:
    """A single sub-query extracted from complex question"""
    id: int
    question: str
    dependency_ids: List[int] = field(default_factory=list)  # IDs this depends on
    is_final: bool = False
    result: Optional[str] = None  # SQL result after generation


@dataclass
class DecomposedQuery:
    """Result of query decomposition"""
    original: str
    strategy: DecompositionStrategy
    sub_queries: List[SubQuery]
    requires_aggregation: bool = False  # Final step needs to combine results
    reasoning: str = ""


class QueryDecompositionPlan(BaseModel):
    """LLM response model for query decomposition"""
    needs_decomposition: bool = Field(
        ..., 
        description="Whether the question needs to be broken down"
    )
    reasoning: str = Field(
        ..., 
        description="Explanation of why/how to decompose"
    )
    sub_questions: List[str] = Field(
        default_factory=list,
        description="List of simpler sub-questions if decomposition needed"
    )
    dependencies: List[List[int]] = Field(
        default_factory=list,
        description="For each sub-question, list indices of questions it depends on"
    )
    final_aggregation: str = Field(
        default="",
        description="How to combine sub-query results (if applicable)"
    )


# Patterns indicating compound/complex questions
COMPOUND_PATTERNS = [
    # Multiple questions combined
    r'\b(và|and)\s+(cũng|also)\b',
    r'\b(sau đó|then|tiếp theo|next)\b',
    r'\b(đồng thời|meanwhile|cùng lúc)\b',
    
    # Comparison requiring multiple queries
    r'\b(so sánh|compare)\s+.+\s+(với|with|to|và)\s+',
    r'\b(difference|khác biệt|chênh lệch)\s+between\b',
    r'\b(more than|less than|nhiều hơn|ít hơn)\s+.+\s+(of|trong)\b',
    
    # Conditional/dependent queries
    r'\b(if|nếu)\s+.+\s+(then|thì)\b',
    r'\b(based on|dựa trên|theo)\s+.+\s+(of|từ)\b',
    r'\b(for each|với mỗi|cho từng)\b',
    
    # Multi-step questions with explicit markers
    r'\d+\.\s+',  # Numbered steps
    r'[•\-]\s+',  # Bullet points
    r'\?\s*.+\?',  # Multiple question marks
    
    # Questions with "and" connecting clauses
    r',\s*(và|and)\s+\w+',
    r'\b(both|cả)\s+.+\s+(and|và)\s+',
]

# Patterns for splitting compound questions
SPLIT_PATTERNS = [
    # Explicit conjunctions
    (r'\.\s*(?=[A-ZÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶĐÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ])', '.'),
    (r'\?\s*(?=[A-Z])', '?'),
    (r'\b(và cũng|and also|then also)\b', ' [SPLIT] '),
    (r'\b(sau đó|then|tiếp theo)\b', ' [SPLIT] '),
    
    # Compare patterns
    (r'\b(so sánh|compare)\b', '[COMPARE]'),
]


class QueryDecomposer:
    """
    Decomposes complex questions into simpler sub-queries
    
    Strategies:
    1. Pattern-based: Use regex to detect and split compound questions
    2. LLM-based: Use LLM to decompose ambiguous complex questions
    """
    
    def __init__(
        self,
        table_names: Optional[List[str]] = None,
        llm_client: Optional[Any] = None
    ):
        """
        Initialize query decomposer
        
        Args:
            table_names: Known table names for context
            llm_client: Optional LLM client for complex decomposition
        """
        self.table_names = table_names or []
        self.llm_client = llm_client
        
    def needs_decomposition(self, question: str) -> Tuple[bool, str]:
        """
        Check if question needs decomposition
        
        Args:
            question: User's question
            
        Returns:
            Tuple of (needs_decomposition, reason)
        """
        question_lower = question.lower()
        
        # Check for compound patterns
        for pattern in COMPOUND_PATTERNS:
            if re.search(pattern, question_lower, re.IGNORECASE):
                match = re.search(pattern, question_lower, re.IGNORECASE)
                return True, f"Detected compound pattern: {match.group() if match else pattern}"
        
        # Check for multiple question marks
        if question.count('?') > 1:
            return True, "Multiple questions detected"
        
        # Check for very long questions (likely complex)
        word_count = len(question.split())
        if word_count > 30:
            return True, f"Long question ({word_count} words) may need breakdown"
        
        # Check for multiple table references
        table_refs = sum(1 for t in self.table_names if t.lower() in question_lower)
        if table_refs > 3:
            return True, f"References {table_refs} tables, may need decomposition"
        
        return False, "Question is simple enough"
    
    def decompose(
        self, 
        question: str,
        use_llm: bool = False
    ) -> DecomposedQuery:
        """
        Decompose a complex question into sub-queries
        
        Args:
            question: Complex question
            use_llm: Whether to use LLM for decomposition
            
        Returns:
            DecomposedQuery with sub-queries
        """
        needs_decomp, reason = self.needs_decomposition(question)
        
        if not needs_decomp:
            return DecomposedQuery(
                original=question,
                strategy=DecompositionStrategy.SINGLE,
                sub_queries=[SubQuery(id=0, question=question, is_final=True)],
                reasoning="No decomposition needed"
            )
        
        logger.info(f"Decomposing question: {reason}")
        
        # Try pattern-based decomposition first
        sub_queries = self._pattern_decompose(question)
        
        if len(sub_queries) > 1:
            strategy = self._determine_strategy(sub_queries)
            return DecomposedQuery(
                original=question,
                strategy=strategy,
                sub_queries=sub_queries,
                reasoning=f"Pattern-based decomposition: {reason}"
            )
        
        # If LLM available and pattern-based didn't work, use LLM
        if use_llm and self.llm_client:
            return self._llm_decompose(question)
        
        # Fallback: return as single query
        return DecomposedQuery(
            original=question,
            strategy=DecompositionStrategy.SINGLE,
            sub_queries=[SubQuery(id=0, question=question, is_final=True)],
            reasoning="Could not decompose, treating as single query"
        )
    
    def _pattern_decompose(self, question: str) -> List[SubQuery]:
        """
        Decompose using pattern matching
        
        Args:
            question: Input question
            
        Returns:
            List of sub-queries
        """
        # Handle comparison questions
        compare_match = re.search(
            r'(so sánh|compare)\s+(.+?)\s+(với|with|và|and|to)\s+(.+)',
            question, 
            re.IGNORECASE
        )
        if compare_match:
            entity1 = compare_match.group(2).strip()
            entity2 = compare_match.group(4).strip()
            
            # Create sub-queries for each entity
            return [
                SubQuery(id=0, question=f"Thông tin về {entity1}"),
                SubQuery(id=1, question=f"Thông tin về {entity2}"),
                SubQuery(
                    id=2, 
                    question=f"So sánh {entity1} và {entity2}",
                    dependency_ids=[0, 1],
                    is_final=True
                )
            ]
        
        # Handle multi-part questions with conjunctions
        parts = self._split_by_conjunctions(question)
        if len(parts) > 1:
            sub_queries = []
            for i, part in enumerate(parts):
                part = part.strip()
                if part:
                    is_final = (i == len(parts) - 1)
                    # Later parts may depend on earlier ones
                    deps = list(range(i)) if i > 0 and self._has_reference(part) else []
                    sub_queries.append(SubQuery(
                        id=i,
                        question=part,
                        dependency_ids=deps,
                        is_final=is_final
                    ))
            return sub_queries
        
        # Handle numbered/bulleted lists
        list_items = self._extract_list_items(question)
        if list_items:
            return [
                SubQuery(id=i, question=item, is_final=(i == len(list_items) - 1))
                for i, item in enumerate(list_items)
            ]
        
        # No pattern matched
        return [SubQuery(id=0, question=question, is_final=True)]
    
    def _split_by_conjunctions(self, question: str) -> List[str]:
        """Split question by conjunction markers"""
        # First, normalize some patterns
        text = question
        
        # Split by sentence-level conjunctions
        splits = re.split(
            r'\.\s+(?=[A-ZÁÀẢÃẠ])|(?:\band\s+also\b|\bsau đó\b|\bthen\b|\btiếp theo\b)',
            text,
            flags=re.IGNORECASE
        )
        
        # Clean up and filter
        parts = [s.strip() for s in splits if s and len(s.strip()) > 10]
        
        return parts if len(parts) > 1 else [question]
    
    def _extract_list_items(self, question: str) -> List[str]:
        """Extract items from numbered or bulleted lists"""
        # Check for numbered list
        numbered = re.findall(r'\d+\.\s*([^0-9]+?)(?=\d+\.|$)', question)
        if len(numbered) > 1:
            return [item.strip() for item in numbered if item.strip()]
        
        # Check for bulleted list
        bulleted = re.split(r'[•\-]\s+', question)
        if len(bulleted) > 2:
            return [item.strip() for item in bulleted if item.strip()]
        
        return []
    
    def _has_reference(self, text: str) -> bool:
        """Check if text references previous results"""
        reference_patterns = [
            r'\b(those|these|them|they|nó|chúng|đó|này)\b',
            r'\b(above|previous|trên|trước)\b',
            r'\b(same|such|tương tự)\b',
            r'\b(result|kết quả)\b',
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in reference_patterns)
    
    def _determine_strategy(self, sub_queries: List[SubQuery]) -> DecompositionStrategy:
        """Determine decomposition strategy based on dependencies"""
        has_deps = any(sq.dependency_ids for sq in sub_queries)
        
        if not has_deps:
            return DecompositionStrategy.PARALLEL
        
        # Check for nested pattern (each depends on previous)
        is_sequential = all(
            sq.dependency_ids == list(range(sq.id))
            for sq in sub_queries 
            if sq.dependency_ids
        )
        
        if is_sequential:
            return DecompositionStrategy.SEQUENTIAL
        
        return DecompositionStrategy.NESTED
    
    def _llm_decompose(self, question: str) -> DecomposedQuery:
        """
        Use LLM to decompose complex question
        
        Args:
            question: Complex question
            
        Returns:
            DecomposedQuery with LLM-determined breakdown
        """
        if not self.llm_client:
            return DecomposedQuery(
                original=question,
                strategy=DecompositionStrategy.SINGLE,
                sub_queries=[SubQuery(id=0, question=question, is_final=True)],
                reasoning="LLM not available for decomposition"
            )
        
        system_prompt = """You are a query decomposition expert. 
Analyze complex questions and break them into simpler sub-questions that can be answered individually.

Rules:
1. Only decompose if the question has multiple distinct parts
2. Each sub-question should be answerable with a single SQL query
3. Identify dependencies between sub-questions
4. Simpler is better - don't over-decompose

Return your analysis as structured output."""

        user_prompt = f"""Analyze this question and determine if it needs decomposition:

Question: {question}

Available tables: {', '.join(self.table_names) if self.table_names else 'Unknown'}

If decomposition is needed, break it into simpler sub-questions."""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm_client.chat.completions.create(
                response_model=QueryDecompositionPlan,
                messages=messages,
                temperature=0.1
            )
            
            if not response.needs_decomposition:
                return DecomposedQuery(
                    original=question,
                    strategy=DecompositionStrategy.SINGLE,
                    sub_queries=[SubQuery(id=0, question=question, is_final=True)],
                    reasoning=response.reasoning
                )
            
            # Build sub-queries from LLM response
            sub_queries = []
            for i, sub_q in enumerate(response.sub_questions):
                deps = response.dependencies[i] if i < len(response.dependencies) else []
                is_final = (i == len(response.sub_questions) - 1)
                sub_queries.append(SubQuery(
                    id=i,
                    question=sub_q,
                    dependency_ids=deps,
                    is_final=is_final
                ))
            
            strategy = self._determine_strategy(sub_queries)
            
            return DecomposedQuery(
                original=question,
                strategy=strategy,
                sub_queries=sub_queries,
                requires_aggregation=bool(response.final_aggregation),
                reasoning=response.reasoning
            )
            
        except Exception as e:
            logger.error(f"LLM decomposition failed: {e}")
            return DecomposedQuery(
                original=question,
                strategy=DecompositionStrategy.SINGLE,
                sub_queries=[SubQuery(id=0, question=question, is_final=True)],
                reasoning=f"LLM decomposition failed: {e}"
            )
    
    def format_for_combined_query(
        self, 
        decomposed: DecomposedQuery,
        results: Dict[int, str]
    ) -> str:
        """
        Format sub-query results for final combined query
        
        Args:
            decomposed: Decomposed query info
            results: Dict mapping sub-query id to SQL result
            
        Returns:
            Combined query hint for final SQL generation
        """
        if decomposed.strategy == DecompositionStrategy.SINGLE:
            return ""
        
        context_parts = ["Previous sub-query results:"]
        
        for sq in decomposed.sub_queries:
            if sq.id in results and not sq.is_final:
                context_parts.append(f"Q{sq.id}: {sq.question}")
                context_parts.append(f"SQL{sq.id}: {results[sq.id]}")
        
        return "\n".join(context_parts)


def decompose_question(
    question: str,
    table_names: Optional[List[str]] = None,
    use_llm: bool = False,
    llm_client: Optional[Any] = None
) -> DecomposedQuery:
    """
    Convenience function to decompose a question
    
    Args:
        question: User's question
        table_names: Available table names
        use_llm: Whether to use LLM for decomposition
        llm_client: Optional LLM client
        
    Returns:
        DecomposedQuery object
    """
    decomposer = QueryDecomposer(table_names, llm_client)
    return decomposer.decompose(question, use_llm)
