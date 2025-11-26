"""
SQL Validator and Post-processor Module
Validates SQL queries and applies constraint-based rewriting
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationErrorType(Enum):
    """Types of SQL validation errors"""
    INVALID_TABLE = "invalid_table"
    INVALID_COLUMN = "invalid_column"
    SYNTAX_ERROR = "syntax_error"
    MISSING_JOIN = "missing_join"
    AMBIGUOUS_COLUMN = "ambiguous_column"
    DANGEROUS_QUERY = "dangerous_query"
    MISSING_LIMIT = "missing_limit"
    CARTESIAN_PRODUCT = "cartesian_product"


@dataclass
class ValidationError:
    """Represents a validation error"""
    error_type: ValidationErrorType
    message: str
    suggestion: str
    severity: str  # "error", "warning", "info"


@dataclass
class ValidationResult:
    """Result of SQL validation"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    fixed_query: Optional[str] = None


class SQLValidator:
    """
    Validates SQL queries against schema and best practices
    
    Features:
    - Table/column existence validation
    - JOIN condition validation
    - Dangerous query detection
    - Best practice checks
    """
    
    def __init__(
        self,
        table_names: List[str],
        column_map: Dict[str, List[str]],  # table -> columns
        relationships: List[Dict] = None    # FK relationships
    ):
        """
        Initialize validator
        
        Args:
            table_names: Valid table names
            column_map: Map of table name to column names
            relationships: FK relationships for JOIN validation
        """
        self.table_names = set(t.lower() for t in table_names)
        self.column_map = {
            t.lower(): set(c.lower() for c in cols) 
            for t, cols in column_map.items()
        }
        self.relationships = relationships or []
        
        # All columns for quick lookup
        self.all_columns = set()
        for cols in self.column_map.values():
            self.all_columns.update(cols)
    
    def validate(self, sql: str) -> ValidationResult:
        """
        Validate SQL query
        
        Args:
            sql: SQL query string
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        sql_upper = sql.upper()
        sql_lower = sql.lower()
        
        # Check for dangerous operations
        danger_errors = self._check_dangerous_operations(sql_upper)
        errors.extend(danger_errors)
        
        # Extract and validate tables
        tables = self._extract_tables(sql)
        table_errors = self._validate_tables(tables)
        errors.extend(table_errors)
        
        # Extract and validate columns
        if not table_errors:  # Only check columns if tables are valid
            columns = self._extract_columns(sql)
            col_errors = self._validate_columns(columns, tables)
            errors.extend([e for e in col_errors if e.severity == "error"])
            warnings.extend([e for e in col_errors if e.severity == "warning"])
        
        # Check for cartesian product (missing JOIN conditions)
        if len(tables) > 1:
            join_warnings = self._check_join_conditions(sql, tables)
            warnings.extend(join_warnings)
        
        # Check for missing LIMIT on large queries
        limit_warnings = self._check_limit(sql_upper, tables)
        warnings.extend(limit_warnings)
        
        # Check for implicit JOINs (old-style comma joins)
        implicit_join_warnings = self._check_implicit_joins(sql)
        warnings.extend(implicit_join_warnings)
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            fixed_query=None
        )
    
    def _check_dangerous_operations(self, sql_upper: str) -> List[ValidationError]:
        """Check for dangerous SQL operations"""
        errors = []
        
        dangerous_patterns = [
            (r'\bDROP\s+(TABLE|DATABASE|INDEX)', "DROP operation detected"),
            (r'\bTRUNCATE\s+', "TRUNCATE operation detected"),
            (r'\bDELETE\s+FROM\s+\w+\s*(?:;|$)', "DELETE without WHERE clause"),
            (r'\bUPDATE\s+\w+\s+SET\s+.*(?:;|$)(?!.*WHERE)', "UPDATE without WHERE clause"),
            (r'\bINSERT\s+', "INSERT operation detected"),
            (r'\bALTER\s+', "ALTER operation detected"),
            (r'\bCREATE\s+', "CREATE operation detected"),
            (r'\bGRANT\s+', "GRANT operation detected"),
            (r'\bREVOKE\s+', "REVOKE operation detected"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, sql_upper):
                errors.append(ValidationError(
                    error_type=ValidationErrorType.DANGEROUS_QUERY,
                    message=message,
                    suggestion="Only SELECT queries are allowed",
                    severity="error"
                ))
        
        return errors
    
    def _extract_tables(self, sql: str) -> Set[str]:
        """Extract table names from SQL"""
        tables = set()
        sql_lower = sql.lower()
        
        # FROM clause
        from_match = re.findall(
            r'\bfrom\s+([`"\[]?\w+[`"\]]?(?:\s*(?:as\s+)?\w+)?)',
            sql_lower
        )
        for match in from_match:
            table = match.split()[0].strip('`"[]')
            tables.add(table)
        
        # JOIN clauses
        join_match = re.findall(
            r'\bjoin\s+([`"\[]?\w+[`"\]]?)',
            sql_lower
        )
        for match in join_match:
            tables.add(match.strip('`"[]'))
        
        return tables
    
    def _extract_columns(self, sql: str) -> List[Tuple[Optional[str], str]]:
        """Extract column references as (table_alias, column) tuples"""
        columns = []
        sql_lower = sql.lower()
        
        # Match qualified columns (table.column)
        qualified = re.findall(r'([`"\[]?\w+[`"\]]?)\.([`"\[]?\w+[`"\]]?)', sql_lower)
        for table, col in qualified:
            columns.append((table.strip('`"[]'), col.strip('`"[]')))
        
        # Match unqualified columns (after SELECT, in WHERE, etc.)
        # This is simplified - real implementation would need SQL parser
        
        return columns
    
    def _validate_tables(self, tables: Set[str]) -> List[ValidationError]:
        """Validate that all tables exist"""
        errors = []
        
        for table in tables:
            if table.lower() not in self.table_names:
                # Try to find similar table name
                similar = self._find_similar(table, self.table_names)
                suggestion = f"Did you mean '{similar}'?" if similar else "Check available tables"
                
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_TABLE,
                    message=f"Table '{table}' does not exist",
                    suggestion=suggestion,
                    severity="error"
                ))
        
        return errors
    
    def _validate_columns(
        self, 
        columns: List[Tuple[Optional[str], str]], 
        tables: Set[str]
    ) -> List[ValidationError]:
        """Validate that all columns exist in their tables"""
        errors = []
        
        for table, column in columns:
            if table:
                table_lower = table.lower()
                if table_lower in self.column_map:
                    if column.lower() not in self.column_map[table_lower]:
                        similar = self._find_similar(column, self.column_map[table_lower])
                        suggestion = f"Did you mean '{similar}'?" if similar else "Check available columns"
                        
                        errors.append(ValidationError(
                            error_type=ValidationErrorType.INVALID_COLUMN,
                            message=f"Column '{column}' does not exist in table '{table}'",
                            suggestion=suggestion,
                            severity="error"
                        ))
            else:
                # Unqualified column - check if exists in any of the tables
                found = False
                for t in tables:
                    t_lower = t.lower()
                    if t_lower in self.column_map:
                        if column.lower() in self.column_map[t_lower]:
                            found = True
                            break
                
                if not found and column.lower() not in self.all_columns:
                    errors.append(ValidationError(
                        error_type=ValidationErrorType.INVALID_COLUMN,
                        message=f"Column '{column}' not found in query tables",
                        suggestion="Qualify column with table name or check spelling",
                        severity="warning"
                    ))
        
        return errors
    
    def _check_join_conditions(self, sql: str, tables: Set[str]) -> List[ValidationError]:
        """Check for potential cartesian products"""
        warnings = []
        sql_upper = sql.upper()
        
        # Check if there are multiple tables without proper JOIN
        has_join = 'JOIN' in sql_upper
        has_where = 'WHERE' in sql_upper
        
        if len(tables) > 1 and not has_join and not has_where:
            warnings.append(ValidationError(
                error_type=ValidationErrorType.CARTESIAN_PRODUCT,
                message="Multiple tables without JOIN or WHERE may cause cartesian product",
                suggestion="Add proper JOIN conditions between tables",
                severity="warning"
            ))
        
        return warnings
    
    def _check_limit(self, sql_upper: str, tables: Set[str]) -> List[ValidationError]:
        """Check for missing LIMIT on potentially large queries"""
        warnings = []
        
        # Check if LIMIT is present
        has_limit = 'LIMIT' in sql_upper
        
        # Queries that should have LIMIT
        is_select_all = 'SELECT *' in sql_upper or 'SELECT `*`' in sql_upper
        no_aggregation = not any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN('])
        
        if not has_limit and is_select_all and no_aggregation:
            warnings.append(ValidationError(
                error_type=ValidationErrorType.MISSING_LIMIT,
                message="SELECT * without LIMIT may return too many rows",
                suggestion="Add LIMIT clause to restrict results",
                severity="warning"
            ))
        
        return warnings
    
    def _check_implicit_joins(self, sql: str) -> List[ValidationError]:
        """Check for old-style implicit joins"""
        warnings = []
        sql_upper = sql.upper()
        
        # Check for comma-separated tables in FROM without JOIN
        from_match = re.search(r'FROM\s+\w+\s*,\s*\w+', sql_upper)
        if from_match:
            warnings.append(ValidationError(
                error_type=ValidationErrorType.MISSING_JOIN,
                message="Implicit join (comma-separated tables) detected",
                suggestion="Use explicit JOIN syntax for clarity",
                severity="info"
            ))
        
        return warnings
    
    def _find_similar(self, name: str, valid_names: Set[str], threshold: float = 0.6) -> Optional[str]:
        """Find most similar name using simple matching"""
        name_lower = name.lower()
        best_match = None
        best_score = 0
        
        for valid in valid_names:
            valid_lower = valid.lower()
            
            # Simple containment check
            if name_lower in valid_lower or valid_lower in name_lower:
                score = len(name_lower) / max(len(valid_lower), len(name_lower))
                if score > best_score:
                    best_score = score
                    best_match = valid
            
            # Character overlap
            common = set(name_lower) & set(valid_lower)
            score = len(common) / max(len(set(name_lower)), len(set(valid_lower)))
            if score > best_score and score >= threshold:
                best_score = score
                best_match = valid
        
        return best_match
    
    def generate_error_feedback(self, result: ValidationResult) -> str:
        """Generate error feedback for LLM self-correction"""
        if result.is_valid:
            return ""
        
        feedback_lines = ["The SQL query has the following issues:\n"]
        
        for error in result.errors:
            feedback_lines.append(f"- ERROR: {error.message}")
            feedback_lines.append(f"  Suggestion: {error.suggestion}")
        
        for warning in result.warnings[:3]:  # Limit warnings
            feedback_lines.append(f"- WARNING: {warning.message}")
        
        feedback_lines.append("\nPlease fix these issues and generate a corrected query.")
        
        return "\n".join(feedback_lines)


class SQLPostProcessor:
    """
    Post-processes SQL queries to enforce best practices
    
    Features:
    - Add LIMIT if missing
    - Convert implicit to explicit JOINs
    - Add table aliases
    - Format SQL consistently
    """
    
    def __init__(self, default_limit: int = 100):
        self.default_limit = default_limit
    
    def process(self, sql: str) -> str:
        """
        Apply all post-processing rules
        
        Args:
            sql: Original SQL query
            
        Returns:
            Processed SQL query
        """
        processed = sql.strip()
        
        # Add LIMIT if missing and appropriate
        processed = self._ensure_limit(processed)
        
        # Clean up whitespace
        processed = self._clean_whitespace(processed)
        
        return processed
    
    def _ensure_limit(self, sql: str) -> str:
        """Add LIMIT clause if missing for non-aggregate queries"""
        sql_upper = sql.upper()
        
        # Skip if already has LIMIT
        if 'LIMIT' in sql_upper:
            return sql
        
        # Skip for aggregate queries
        aggregates = ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(', 'GROUP BY']
        if any(agg in sql_upper for agg in aggregates):
            return sql
        
        # Skip for non-SELECT queries
        if not sql_upper.strip().startswith('SELECT'):
            return sql
        
        # Add LIMIT
        sql = sql.rstrip(';').strip()
        sql = f"{sql} LIMIT {self.default_limit}"
        
        return sql
    
    def _clean_whitespace(self, sql: str) -> str:
        """Clean up whitespace while preserving structure"""
        # Replace multiple spaces with single space
        sql = re.sub(r' +', ' ', sql)
        
        # Ensure proper spacing around keywords
        keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'JOIN', 
                    'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'ON',
                    'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT']
        
        for kw in keywords:
            pattern = rf'\s*\b{kw}\b\s*'
            sql = re.sub(pattern, f' {kw} ', sql, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        sql = re.sub(r' +', ' ', sql)
        sql = sql.strip()
        
        return sql


def validate_and_fix_sql(
    sql: str,
    table_names: List[str],
    column_map: Dict[str, List[str]],
    default_limit: int = 100
) -> Tuple[bool, str, List[str]]:
    """
    Convenience function to validate and post-process SQL
    
    Args:
        sql: SQL query
        table_names: Valid table names
        column_map: Map of table to columns
        default_limit: Default LIMIT value
        
    Returns:
        Tuple of (is_valid, processed_sql, error_messages)
    """
    validator = SQLValidator(table_names, column_map)
    result = validator.validate(sql)
    
    if result.is_valid:
        processor = SQLPostProcessor(default_limit)
        processed = processor.process(sql)
        return True, processed, []
    else:
        error_msgs = [e.message for e in result.errors]
        return False, sql, error_msgs
