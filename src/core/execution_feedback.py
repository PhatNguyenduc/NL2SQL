"""
SQL Execution Feedback Module
Uses SQL execution errors to improve query generation through iterative refinement
"""

import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SQLErrorType(Enum):
    """Types of SQL execution errors"""
    SYNTAX = "syntax"               # SQL syntax error
    TABLE_NOT_FOUND = "table_not_found"
    COLUMN_NOT_FOUND = "column_not_found"
    AMBIGUOUS_COLUMN = "ambiguous_column"
    TYPE_MISMATCH = "type_mismatch"
    CONSTRAINT = "constraint"       # FK/UK violations
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    UNKNOWN = "unknown"


@dataclass
class ErrorAnalysis:
    """Analysis of SQL execution error"""
    error_type: SQLErrorType
    error_message: str
    problematic_element: Optional[str] = None  # Table/column name causing issue
    suggested_fix: Optional[str] = None
    related_tables: List[str] = field(default_factory=list)
    related_columns: List[str] = field(default_factory=list)


@dataclass 
class ExecutionFeedback:
    """Feedback from SQL execution for query improvement"""
    original_query: str
    error_analysis: ErrorAnalysis
    correction_prompt: str
    schema_hints: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3


class CorrectedQuery(BaseModel):
    """LLM response model for corrected query"""
    corrected_sql: str = Field(..., description="The corrected SQL query")
    explanation: str = Field(..., description="What was fixed and why")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the fix")


# Error pattern recognition
ERROR_PATTERNS = {
    SQLErrorType.TABLE_NOT_FOUND: [
        r"Table '([^']+)' doesn't exist",
        r"relation \"([^\"]+)\" does not exist",
        r"Unknown table '([^']+)'",
        r"no such table: (\w+)",
    ],
    SQLErrorType.COLUMN_NOT_FOUND: [
        r"Unknown column '([^']+)'",
        r"column \"([^\"]+)\" does not exist",
        r"column ([^\s]+) not found",
        r"no such column: (\w+)",
    ],
    SQLErrorType.AMBIGUOUS_COLUMN: [
        r"Column '([^']+)' in .+ is ambiguous",
        r"column reference \"([^\"]+)\" is ambiguous",
        r"ambiguous column name: (\w+)",
    ],
    SQLErrorType.SYNTAX: [
        r"You have an error in your SQL syntax",
        r"syntax error at or near",
        r"near \"([^\"]+)\": syntax error",
        r"Incorrect syntax near",
    ],
    SQLErrorType.TYPE_MISMATCH: [
        r"Incorrect (date|datetime|integer|float) value",
        r"invalid input syntax for type",
        r"cannot cast",
        r"type mismatch",
    ],
    SQLErrorType.TIMEOUT: [
        r"Query execution was interrupted",
        r"statement timeout",
        r"Lock wait timeout exceeded",
    ],
}


class SQLExecutionFeedbackHandler:
    """
    Handles SQL execution errors and generates correction prompts
    
    Features:
    - Classifies error types
    - Extracts problematic elements from errors
    - Generates targeted correction prompts
    - Tracks retry history
    """
    
    def __init__(
        self,
        schema_tables: Optional[List[str]] = None,
        schema_columns: Optional[Dict[str, List[str]]] = None,
        max_retries: int = 3
    ):
        """
        Initialize feedback handler
        
        Args:
            schema_tables: List of valid table names
            schema_columns: Dict mapping table names to column lists
            max_retries: Maximum correction attempts
        """
        self.schema_tables = schema_tables or []
        self.schema_columns = schema_columns or {}
        self.max_retries = max_retries
        self._correction_history: List[Tuple[str, str]] = []  # (query, error) pairs
        
    def analyze_error(self, error_message: str, query: str) -> ErrorAnalysis:
        """
        Analyze SQL execution error
        
        Args:
            error_message: Error message from database
            query: The query that failed
            
        Returns:
            ErrorAnalysis with classified error info
        """
        error_lower = error_message.lower()
        
        # Try to match known patterns
        for error_type, patterns in ERROR_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, error_message, re.IGNORECASE)
                if match:
                    problematic = match.group(1) if match.lastindex else None
                    
                    analysis = ErrorAnalysis(
                        error_type=error_type,
                        error_message=error_message,
                        problematic_element=problematic
                    )
                    
                    # Add specific suggestions based on error type
                    self._add_suggestions(analysis, query)
                    
                    return analysis
        
        # Unknown error
        return ErrorAnalysis(
            error_type=SQLErrorType.UNKNOWN,
            error_message=error_message,
            suggested_fix="Review query syntax and schema"
        )
    
    def _add_suggestions(self, analysis: ErrorAnalysis, query: str):
        """Add specific suggestions based on error analysis"""
        
        if analysis.error_type == SQLErrorType.TABLE_NOT_FOUND:
            problematic = analysis.problematic_element
            if problematic and self.schema_tables:
                # Find similar table names
                similar = self._find_similar(problematic, self.schema_tables)
                if similar:
                    analysis.suggested_fix = f"Did you mean: {', '.join(similar[:3])}?"
                    analysis.related_tables = similar[:3]
                else:
                    analysis.suggested_fix = f"Available tables: {', '.join(self.schema_tables[:10])}"
                    
        elif analysis.error_type == SQLErrorType.COLUMN_NOT_FOUND:
            problematic = analysis.problematic_element
            if problematic:
                # Extract table context from query
                table_match = re.search(
                    rf'FROM\s+(\w+)|JOIN\s+(\w+)', 
                    query, 
                    re.IGNORECASE
                )
                if table_match:
                    table = table_match.group(1) or table_match.group(2)
                    if table in self.schema_columns:
                        similar = self._find_similar(problematic, self.schema_columns[table])
                        if similar:
                            analysis.suggested_fix = f"Did you mean: {', '.join(similar[:3])}?"
                            analysis.related_columns = similar[:3]
                        else:
                            analysis.suggested_fix = f"Columns in {table}: {', '.join(self.schema_columns[table][:10])}"
                            
        elif analysis.error_type == SQLErrorType.AMBIGUOUS_COLUMN:
            problematic = analysis.problematic_element
            analysis.suggested_fix = f"Add table alias prefix to '{problematic}' (e.g., t.{problematic})"
            
        elif analysis.error_type == SQLErrorType.SYNTAX:
            analysis.suggested_fix = "Check SQL syntax, keywords, and quote usage"
            
        elif analysis.error_type == SQLErrorType.TYPE_MISMATCH:
            analysis.suggested_fix = "Check data types and use appropriate casting/formatting"
    
    def _find_similar(self, target: str, candidates: List[str], threshold: float = 0.6) -> List[str]:
        """Find similar strings using simple matching"""
        target_lower = target.lower()
        similar = []
        
        for candidate in candidates:
            candidate_lower = candidate.lower()
            
            # Exact containment
            if target_lower in candidate_lower or candidate_lower in target_lower:
                similar.append((candidate, 1.0))
                continue
            
            # Simple similarity: common characters
            common = len(set(target_lower) & set(candidate_lower))
            total = len(set(target_lower) | set(candidate_lower))
            similarity = common / total if total > 0 else 0
            
            if similarity >= threshold:
                similar.append((candidate, similarity))
        
        # Sort by similarity descending
        similar.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in similar]
    
    def generate_correction_prompt(
        self,
        original_question: str,
        failed_query: str,
        error_analysis: ErrorAnalysis
    ) -> str:
        """
        Generate a prompt for LLM to correct the query
        
        Args:
            original_question: User's original question
            failed_query: The SQL that failed
            error_analysis: Analysis of the error
            
        Returns:
            Correction prompt for LLM
        """
        prompt_parts = [
            "The following SQL query failed with an error. Please fix it.",
            "",
            f"Original Question: {original_question}",
            "",
            f"Failed SQL:",
            f"```sql",
            f"{failed_query}",
            f"```",
            "",
            f"Error Type: {error_analysis.error_type.value}",
            f"Error Message: {error_analysis.error_message}",
        ]
        
        if error_analysis.problematic_element:
            prompt_parts.append(f"Problematic Element: {error_analysis.problematic_element}")
        
        if error_analysis.suggested_fix:
            prompt_parts.append(f"Suggestion: {error_analysis.suggested_fix}")
        
        if error_analysis.related_tables:
            prompt_parts.append(f"Similar Tables: {', '.join(error_analysis.related_tables)}")
            
        if error_analysis.related_columns:
            prompt_parts.append(f"Similar Columns: {', '.join(error_analysis.related_columns)}")
        
        prompt_parts.extend([
            "",
            "Please provide the corrected SQL query.",
            "Focus on fixing the specific error while maintaining the original intent.",
        ])
        
        return "\n".join(prompt_parts)
    
    def create_feedback(
        self,
        original_question: str,
        query: str,
        error_message: str
    ) -> ExecutionFeedback:
        """
        Create execution feedback from error
        
        Args:
            original_question: User's original question
            query: Failed query
            error_message: Error message
            
        Returns:
            ExecutionFeedback object
        """
        # Track correction history
        self._correction_history.append((query, error_message))
        
        # Analyze error
        analysis = self.analyze_error(error_message, query)
        
        # Generate correction prompt
        prompt = self.generate_correction_prompt(
            original_question, query, analysis
        )
        
        # Add schema hints
        schema_hints = []
        if analysis.related_tables:
            for table in analysis.related_tables:
                if table in self.schema_columns:
                    schema_hints.append(f"{table}: {', '.join(self.schema_columns[table][:5])}")
        
        return ExecutionFeedback(
            original_query=query,
            error_analysis=analysis,
            correction_prompt=prompt,
            schema_hints=schema_hints,
            retry_count=len(self._correction_history),
            max_retries=self.max_retries
        )
    
    def should_retry(self, feedback: ExecutionFeedback) -> bool:
        """Check if we should attempt another correction"""
        # Don't retry for permission/connection errors
        if feedback.error_analysis.error_type in [
            SQLErrorType.PERMISSION, 
            SQLErrorType.CONNECTION
        ]:
            return False
        
        # Check retry limit
        if feedback.retry_count >= feedback.max_retries:
            logger.warning(f"Max retries ({feedback.max_retries}) reached")
            return False
        
        # Check if we're looping on same error
        if len(self._correction_history) >= 2:
            last_two = self._correction_history[-2:]
            if last_two[0][1] == last_two[1][1]:  # Same error twice
                logger.warning("Same error repeated, stopping retry")
                return False
        
        return True
    
    def reset_history(self):
        """Reset correction history for new query"""
        self._correction_history = []


class ExecutionFeedbackLoop:
    """
    Orchestrates the execution-feedback-correction loop
    """
    
    def __init__(
        self,
        feedback_handler: SQLExecutionFeedbackHandler,
        query_executor,  # QueryExecutor instance
        llm_client,      # Instructor-patched LLM client
        max_retries: int = 3
    ):
        self.feedback_handler = feedback_handler
        self.query_executor = query_executor
        self.llm_client = llm_client
        self.max_retries = max_retries
        
    def execute_with_feedback(
        self,
        question: str,
        initial_query: str,
        model: str = None
    ) -> Tuple[str, Any, List[ExecutionFeedback]]:
        """
        Execute query with feedback loop for corrections
        
        Args:
            question: Original user question
            initial_query: Initial SQL query
            model: LLM model to use for corrections
            
        Returns:
            Tuple of (final_query, result, feedback_history)
        """
        self.feedback_handler.reset_history()
        
        current_query = initial_query
        feedback_history = []
        
        for attempt in range(self.max_retries + 1):
            # Try to execute
            result = self.query_executor.execute(current_query)
            
            if result.success:
                logger.info(f"Query succeeded on attempt {attempt + 1}")
                return current_query, result, feedback_history
            
            # Execution failed
            logger.warning(f"Attempt {attempt + 1} failed: {result.error_message}")
            
            # Create feedback
            feedback = self.feedback_handler.create_feedback(
                question, current_query, result.error_message
            )
            feedback_history.append(feedback)
            
            # Check if we should retry
            if not self.feedback_handler.should_retry(feedback):
                break
            
            # Get correction from LLM
            try:
                corrected = self._get_correction(feedback, model)
                if corrected and corrected.corrected_sql != current_query:
                    logger.info(f"Got correction: {corrected.explanation}")
                    current_query = corrected.corrected_sql
                else:
                    logger.warning("No new correction, stopping")
                    break
            except Exception as e:
                logger.error(f"Correction failed: {e}")
                break
        
        # Return last state
        result = self.query_executor.execute(current_query)
        return current_query, result, feedback_history
    
    def _get_correction(
        self,
        feedback: ExecutionFeedback,
        model: Optional[str] = None
    ) -> Optional[CorrectedQuery]:
        """Get correction from LLM"""
        messages = [
            {
                "role": "system",
                "content": "You are a SQL expert. Fix the provided SQL query based on the error feedback."
            },
            {
                "role": "user", 
                "content": feedback.correction_prompt
            }
        ]
        
        kwargs = {
            "response_model": CorrectedQuery,
            "messages": messages,
            "temperature": 0.1,
            "max_retries": 1
        }
        
        if model:
            kwargs["model"] = model
            
        return self.llm_client.chat.completions.create(**kwargs)


def analyze_sql_error(
    error_message: str,
    query: str,
    schema_tables: Optional[List[str]] = None,
    schema_columns: Optional[Dict[str, List[str]]] = None
) -> ErrorAnalysis:
    """
    Convenience function to analyze SQL error
    
    Args:
        error_message: Database error message
        query: Failed SQL query
        schema_tables: Available table names
        schema_columns: Table-column mapping
        
    Returns:
        ErrorAnalysis object
    """
    handler = SQLExecutionFeedbackHandler(schema_tables, schema_columns)
    return handler.analyze_error(error_message, query)
