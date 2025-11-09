"""SQL validation and security checking"""

import re
import sqlparse
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)

# Dangerous SQL keywords that should be blocked
DANGEROUS_KEYWORDS = [
    "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "MERGE", "GRANT", "REVOKE",
    "EXEC", "EXECUTE", "CALL"
]

# Allowed SQL keywords (primarily SELECT operations)
ALLOWED_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER",
    "OUTER", "ON", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN",
    "GROUP", "BY", "HAVING", "ORDER", "LIMIT", "OFFSET",
    "AS", "DISTINCT", "UNION", "INTERSECT", "EXCEPT",
    "WITH", "CASE", "WHEN", "THEN", "ELSE", "END"
]


def validate_sql(query: str) -> Tuple[bool, str]:
    """
    Validate SQL query syntax and structure
    
    Args:
        query: SQL query string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not query or not isinstance(query, str):
        return False, "Query must be a non-empty string"
    
    query = query.strip()
    
    if not query:
        return False, "Query cannot be empty"
    
    # Check if query ends with semicolon
    if query.endswith(';'):
        query = query[:-1].strip()
    
    # Try to parse with sqlparse
    try:
        parsed = sqlparse.parse(query)
        if not parsed:
            return False, "Failed to parse SQL query"
        
        # Check if we have at least one statement
        if len(parsed) == 0:
            return False, "No SQL statement found"
        
        # Check if we have multiple statements (potential SQL injection)
        if len(parsed) > 1:
            return False, "Multiple SQL statements are not allowed"
        
    except Exception as e:
        return False, f"SQL parsing error: {str(e)}"
    
    return True, "Valid SQL syntax"


def is_safe_query(query: str) -> Tuple[bool, List[str]]:
    """
    Check if query is safe (only SELECT, no dangerous operations)
    
    Args:
        query: SQL query string to check
        
    Returns:
        Tuple of (is_safe, list_of_issues)
    """
    issues = []
    query_upper = query.upper()
    
    # Check for dangerous keywords
    found_dangerous = []
    for keyword in DANGEROUS_KEYWORDS:
        # Use word boundary to avoid false positives
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, query_upper):
            found_dangerous.append(keyword)
    
    if found_dangerous:
        issues.append(f"Dangerous keywords found: {', '.join(found_dangerous)}")
    
    # Check if query starts with SELECT or WITH (for CTEs)
    query_stripped = query_upper.strip()
    if not (query_stripped.startswith('SELECT') or query_stripped.startswith('WITH')):
        issues.append("Query must start with SELECT or WITH")
    
    # Check for SQL comment injection attempts
    if '--' in query or '/*' in query or '*/' in query:
        issues.append("SQL comments are not allowed")
    
    # Check for semicolons (except at the end)
    semicolon_count = query.count(';')
    if semicolon_count > 1 or (semicolon_count == 1 and not query.strip().endswith(';')):
        issues.append("Multiple statements or suspicious semicolons detected")
    
    # Check for excessive wildcards (potential performance issue)
    if query_upper.count('*') > 3:
        issues.append("Warning: Excessive use of wildcards (*) may impact performance")
    
    is_safe = len(issues) == 0
    return is_safe, issues


def sanitize_query(query: str) -> str:
    """
    Sanitize SQL query by removing dangerous elements
    
    Args:
        query: SQL query to sanitize
        
    Returns:
        Sanitized query
    """
    # Remove SQL comments
    query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
    query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
    
    # Remove extra whitespace
    query = ' '.join(query.split())
    
    # Remove trailing semicolon
    query = query.rstrip(';').strip()
    
    return query


def add_query_limit(query: str, default_limit: int = 100) -> str:
    """
    Add LIMIT clause to query if not present
    
    Args:
        query: SQL query
        default_limit: Default limit to add
        
    Returns:
        Query with LIMIT clause
    """
    query_upper = query.upper()
    
    # Check if LIMIT already exists
    if 'LIMIT' in query_upper:
        return query
    
    # Add LIMIT at the end
    return f"{query.rstrip(';')} LIMIT {default_limit}"


def extract_table_names(query: str) -> List[str]:
    """
    Extract table names from SQL query
    
    Args:
        query: SQL query
        
    Returns:
        List of table names
    """
    tables = []
    
    try:
        parsed = sqlparse.parse(query)[0]
        
        # Look for FROM and JOIN clauses
        from_seen = False
        for token in parsed.tokens:
            if from_seen:
                if isinstance(token, sqlparse.sql.IdentifierList):
                    for identifier in token.get_identifiers():
                        table_name = identifier.get_real_name()
                        if table_name:
                            tables.append(table_name)
                elif isinstance(token, sqlparse.sql.Identifier):
                    table_name = token.get_real_name()
                    if table_name:
                        tables.append(table_name)
                from_seen = False
            
            if token.ttype is sqlparse.tokens.Keyword and token.value.upper() in ('FROM', 'JOIN'):
                from_seen = True
    
    except Exception as e:
        logger.warning(f"Failed to extract table names: {e}")
    
    return list(set(tables))  # Remove duplicates


def validate_query_against_schema(query: str, available_tables: List[str]) -> Tuple[bool, str]:
    """
    Validate that query only references tables that exist in schema
    
    Args:
        query: SQL query
        available_tables: List of available table names
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    query_tables = extract_table_names(query)
    
    if not query_tables:
        return False, "Could not extract any table names from query"
    
    # Check if all tables exist
    available_tables_lower = [t.lower() for t in available_tables]
    invalid_tables = []
    
    for table in query_tables:
        if table.lower() not in available_tables_lower:
            invalid_tables.append(table)
    
    if invalid_tables:
        return False, f"Tables not found in schema: {', '.join(invalid_tables)}"
    
    return True, "All tables exist in schema"


def check_query_complexity(query: str) -> Tuple[str, List[str]]:
    """
    Analyze query complexity and provide warnings
    
    Args:
        query: SQL query
        
    Returns:
        Tuple of (complexity_level, list_of_warnings)
    """
    warnings = []
    query_upper = query.upper()
    
    # Count JOINs
    join_count = query_upper.count('JOIN')
    if join_count > 5:
        warnings.append(f"High number of JOINs ({join_count}) may impact performance")
    
    # Check for nested subqueries
    subquery_count = query_upper.count('SELECT') - 1  # Subtract main SELECT
    if subquery_count > 3:
        warnings.append(f"Multiple nested subqueries ({subquery_count}) detected")
    
    # Check for UNION
    if 'UNION' in query_upper:
        warnings.append("UNION operations can be expensive")
    
    # Determine complexity level
    complexity = "simple"
    if join_count > 2 or subquery_count > 1:
        complexity = "medium"
    if join_count > 5 or subquery_count > 3:
        complexity = "complex"
    
    return complexity, warnings
