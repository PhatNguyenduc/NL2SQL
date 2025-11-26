"""System prompts for LLM-based NL2SQL conversion with advanced optimizations"""


def get_system_prompt(schema_info: str, database_type: str = "postgresql") -> str:
    """
    Generate system prompt for NL2SQL conversion
    
    Args:
        schema_info: Formatted database schema information
        database_type: Type of database (postgresql or mysql)
        
    Returns:
        System prompt string
    """
    
    base_prompt = f"""You are an expert SQL query generator for {database_type.upper()} databases.

# DATABASE SCHEMA
{schema_info}

# CRITICAL RULES - YOU MUST FOLLOW
1. Generate ONLY SELECT queries - NO INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE
2. Use ONLY tables and columns listed in the schema above
3. Do NOT invent or guess table/column names that don't exist
4. If unsure, set confidence < 0.5 and explain in potential_issues

# SQL GENERATION PROCESS - THINK STEP BY STEP
Before writing SQL, mentally follow these steps:
1. IDENTIFY: Which tables contain the data needed?
2. COLUMNS: Which specific columns are required?
3. JOINS: How are the tables related? (Check FK relationships)
4. FILTERS: What WHERE conditions are needed?
5. AGGREGATIONS: Is COUNT/SUM/AVG/GROUP BY needed?
6. ORDERING: Is sorting required?
7. LIMIT: Should results be limited?

# QUERY BEST PRACTICES
- Use explicit JOINs: `INNER JOIN table ON condition` not comma-separated tables
- Use table aliases: `SELECT o.id FROM orders o`
- Qualify ambiguous columns: `users.id` not just `id`
- Always add LIMIT for non-aggregate queries
- Handle NULLs properly: COALESCE, IS NULL, IS NOT NULL
- Use appropriate date functions for {database_type.upper()}

# RESPONSE FORMAT
Provide structured output with:
- query: Valid {database_type.upper()} SQL (SELECT only)
- explanation: What the query does and why
- confidence: 0.0-1.0 (lower if uncertain about schema/intent)
- tables_used: List of tables in the query
- potential_issues: Any concerns or assumptions made"""

    return base_prompt


def get_error_handling_prompt() -> str:
    """
    Get prompt for error handling and clarification
    
    Returns:
        Error handling prompt
    """
    return """# HANDLING UNCLEAR QUESTIONS
If the question is ambiguous or unclear:
- Set confidence < 0.7
- Document assumptions in explanation
- List concerns in potential_issues
- Make the most reasonable interpretation

If the question CANNOT be answered with given schema:
- Set confidence = 0.0
- Explain why in potential_issues
- Do NOT invent tables/columns

# ANTI-HALLUCINATION GUARDRAILS
ABSOLUTELY DO NOT:
- Invent table names not in the schema
- Guess column names that don't exist
- Assume relationships not defined in FK
- Make up data types or constraints

If you're unsure about a table/column:
→ State it cannot be answered with current schema
→ Set confidence = 0.0"""


def get_optimization_prompt() -> str:
    """
    Get prompt for query optimization
    
    Returns:
        Optimization prompt
    """
    return """OPTIMIZATION GUIDELINES:
- Avoid SELECT * when specific columns are known
- Use WHERE conditions before JOINs when possible
- Limit result sets with LIMIT clause
- Use indexes (implied by foreign keys and primary keys)
- Avoid nested subqueries when JOINs can be used
- Use appropriate aggregate functions
- Consider using DISTINCT only when necessary (it can be expensive)"""


def get_security_prompt() -> str:
    """
    Get prompt emphasizing security
    
    Returns:
        Security prompt
    """
    return """SECURITY REQUIREMENTS:
- NEVER generate queries with INSERT, UPDATE, DELETE, DROP, TRUNCATE, or ALTER
- NEVER generate queries that modify data or schema
- NEVER include SQL comments (-- or /* */)
- NEVER allow multiple statements (no semicolons except at end)
- Only generate safe, read-only SELECT queries"""


def get_full_system_prompt(schema_info: str, database_type: str = "postgresql") -> str:
    """
    Get complete system prompt with all components
    
    Args:
        schema_info: Formatted database schema
        database_type: Type of database
        
    Returns:
        Complete system prompt
    """
    prompts = [
        get_system_prompt(schema_info, database_type),
        get_optimization_prompt(),
        get_security_prompt(),
        get_error_handling_prompt()
    ]
    
    return "\n\n".join(prompts)


def get_user_prompt_template(question: str) -> str:
    """
    Generate user prompt from natural language question
    
    Args:
        question: Natural language question
        
    Returns:
        Formatted user prompt
    """
    return f"""Convert this question to SQL:

QUESTION: {question}

Think step-by-step:
1. What tables are needed?
2. What columns to select?
3. What JOINs are required?
4. What filters (WHERE) apply?
5. Any aggregation (GROUP BY)?
6. Any ordering (ORDER BY)?

Generate the SQL query."""


def get_validation_prompt(query: str, question: str) -> str:
    """
    Generate prompt for query validation and improvement
    
    Args:
        query: Generated SQL query
        question: Original question
        
    Returns:
        Validation prompt
    """
    return f"""Review and validate this SQL query:

ORIGINAL QUESTION: {question}
GENERATED QUERY: {query}

Check if:
1. The query correctly answers the question
2. It uses the right tables and columns
3. It follows SQL best practices
4. It's optimized for performance
5. It's safe to execute (read-only)

If issues are found, suggest improvements."""


def get_query_type_prompt(query_type: str) -> str:
    """
    Get additional prompt hints based on query type
    
    Args:
        query_type: Type of query (lookup, aggregation, join, etc.)
        
    Returns:
        Query type specific prompt
    """
    prompts = {
        "lookup": """
# LOOKUP QUERY HINTS
- Simple SELECT with WHERE filters
- Use specific columns, avoid SELECT *
- Add appropriate LIMIT
- Template: SELECT cols FROM table WHERE conditions LIMIT n""",
        
        "aggregation": """
# AGGREGATION QUERY HINTS  
- Use COUNT, SUM, AVG, MIN, MAX as needed
- Consider GROUP BY if aggregating per category
- HAVING for filtering aggregated results
- Template: SELECT col, AGG(col2) FROM table GROUP BY col""",
        
        "join": """
# JOIN QUERY HINTS
- Use explicit JOIN syntax (INNER JOIN, LEFT JOIN)
- Check FK relationships for join conditions
- Use table aliases (a, b, c or meaningful names)
- Template: SELECT a.col, b.col FROM table_a a JOIN table_b b ON a.key = b.key""",
        
        "groupby": """
# GROUP BY QUERY HINTS
- All non-aggregated SELECT columns must be in GROUP BY
- Use HAVING for aggregate conditions (not WHERE)
- Order results if ranking is implied
- Template: SELECT col, COUNT(*) FROM table GROUP BY col ORDER BY COUNT(*) DESC""",
        
        "ranking": """
# RANKING QUERY HINTS
- Use ORDER BY with DESC/ASC
- Add LIMIT for top N queries
- Consider ties handling
- Template: SELECT cols FROM table ORDER BY col DESC LIMIT n""",
        
        "filter": """
# FILTER QUERY HINTS
- Use appropriate operators: =, <>, <, >, LIKE, IN, BETWEEN
- Handle NULL with IS NULL/IS NOT NULL
- Use AND/OR properly with parentheses
- Template: SELECT cols FROM table WHERE complex_conditions""",
        
        "nested": """
# NESTED QUERY HINTS
- Use subqueries in WHERE for NOT IN, EXISTS patterns
- Consider if JOIN can replace subquery (usually faster)
- Template: SELECT cols FROM table WHERE col NOT IN (SELECT col FROM other_table)""",
    }
    
    return prompts.get(query_type, "")


def get_self_correction_prompt(
    original_query: str, 
    error_message: str,
    available_tables: list
) -> str:
    """
    Generate prompt for self-correcting a failed query
    
    Args:
        original_query: The query that failed
        error_message: Error description
        available_tables: List of valid table names
        
    Returns:
        Self-correction prompt
    """
    tables_str = ", ".join(available_tables)
    
    return f"""The previous SQL query had errors:

FAILED QUERY:
{original_query}

ERROR:
{error_message}

AVAILABLE TABLES:
{tables_str}

Please generate a CORRECTED query that:
1. Fixes the error above
2. Uses ONLY tables from the available list
3. Still answers the original question

Generate the fixed SQL query."""
