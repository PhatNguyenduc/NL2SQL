"""Few-shot examples for NL2SQL conversion"""

from typing import List, Dict, Any


def get_few_shot_examples(database_type: str = "postgresql") -> List[Dict[str, Any]]:
    """
    Get few-shot examples for in-context learning
    
    Args:
        database_type: Type of database (postgresql or mysql)
        
    Returns:
        List of example dictionaries
    """
    
    # Common examples that work for both PostgreSQL and MySQL
    examples = [
        {
            "question": "Show me all users",
            "query": "SELECT * FROM users LIMIT 100",
            "explanation": "Retrieves all columns from the users table, limited to 100 rows for safety",
            "confidence": 1.0,
            "tables_used": ["users"]
        },
        {
            "question": "How many users do we have?",
            "query": "SELECT COUNT(*) as total_users FROM users",
            "explanation": "Counts the total number of users in the users table",
            "confidence": 1.0,
            "tables_used": ["users"]
        },
        {
            "question": "Find users older than 25",
            "query": "SELECT * FROM users WHERE age > 25 LIMIT 100",
            "explanation": "Retrieves all users whose age is greater than 25",
            "confidence": 1.0,
            "tables_used": ["users"]
        },
        {
            "question": "List all orders with customer information",
            "query": """SELECT o.id, o.order_date, o.total_amount, 
       u.name, u.email
FROM orders o
INNER JOIN users u ON o.user_id = u.id
LIMIT 100""",
            "explanation": "Joins orders with users table to show order details along with customer name and email",
            "confidence": 1.0,
            "tables_used": ["orders", "users"]
        },
        {
            "question": "What's the average order amount?",
            "query": "SELECT AVG(total_amount) as average_amount FROM orders",
            "explanation": "Calculates the average total amount across all orders",
            "confidence": 1.0,
            "tables_used": ["orders"]
        },
        {
            "question": "Show top 10 customers by total spending",
            "query": """SELECT u.id, u.name, u.email, 
       SUM(o.total_amount) as total_spent
FROM users u
INNER JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name, u.email
ORDER BY total_spent DESC
LIMIT 10""",
            "explanation": "Groups orders by user and calculates total spending, showing top 10 spenders",
            "confidence": 1.0,
            "tables_used": ["users", "orders"]
        },
        {
            "question": "Find users who haven't placed any orders",
            "query": """SELECT u.id, u.name, u.email
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.id IS NULL
LIMIT 100""",
            "explanation": "Uses LEFT JOIN to find users with no matching orders",
            "confidence": 1.0,
            "tables_used": ["users", "orders"]
        },
        {
            "question": "Show monthly order counts for 2024",
            "query": """SELECT DATE_TRUNC('month', order_date) as month,
       COUNT(*) as order_count
FROM orders
WHERE order_date >= '2024-01-01' 
  AND order_date < '2025-01-01'
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY month""",
            "explanation": "Groups orders by month and counts them for the year 2024",
            "confidence": 0.9,
            "tables_used": ["orders"],
            "potential_issues": ["Date functions may vary by database type"]
        },
        {
            "question": "Find products that are out of stock",
            "query": """SELECT id, name, price, stock_quantity
FROM products
WHERE stock_quantity = 0 OR stock_quantity IS NULL
LIMIT 100""",
            "explanation": "Retrieves products with zero or NULL stock quantity",
            "confidence": 1.0,
            "tables_used": ["products"]
        },
        {
            "question": "Show users registered in the last 30 days",
            "query": """SELECT id, name, email, created_at
FROM users
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY created_at DESC
LIMIT 100""",
            "explanation": "Filters users by registration date within the last 30 days",
            "confidence": 0.9,
            "tables_used": ["users"],
            "potential_issues": ["Date interval syntax may vary by database"]
        }
    ]
    
    # Adjust examples for MySQL if needed
    if database_type.lower() == "mysql":
        # Modify PostgreSQL-specific queries for MySQL
        for example in examples:
            # Replace DATE_TRUNC with DATE_FORMAT
            if "DATE_TRUNC" in example["query"]:
                example["query"] = example["query"].replace(
                    "DATE_TRUNC('month', order_date)",
                    "DATE_FORMAT(order_date, '%Y-%m-01')"
                )
            
            # Replace INTERVAL syntax
            if "INTERVAL '30 days'" in example["query"]:
                example["query"] = example["query"].replace(
                    "INTERVAL '30 days'",
                    "INTERVAL 30 DAY"
                )
    
    return examples


def format_examples_for_prompt(examples: List[Dict[str, Any]]) -> str:
    """
    Format few-shot examples for inclusion in prompt
    
    Args:
        examples: List of example dictionaries
        
    Returns:
        Formatted examples string
    """
    formatted = ["FEW-SHOT EXAMPLES:"]
    formatted.append("Here are some example conversions from natural language to SQL:\n")
    
    for i, example in enumerate(examples, 1):
        formatted.append(f"Example {i}:")
        formatted.append(f"Question: {example['question']}")
        formatted.append(f"SQL Query: {example['query']}")
        formatted.append(f"Explanation: {example['explanation']}")
        formatted.append("")
    
    return "\n".join(formatted)


def get_examples_by_complexity(complexity: str = "simple") -> List[Dict[str, Any]]:
    """
    Get examples filtered by complexity level
    
    Args:
        complexity: 'simple', 'medium', or 'complex'
        
    Returns:
        Filtered list of examples
    """
    all_examples = get_few_shot_examples()
    
    if complexity == "simple":
        # Examples with no JOINs or aggregations
        return [ex for ex in all_examples if len(ex["tables_used"]) == 1 and "JOIN" not in ex["query"]]
    
    elif complexity == "medium":
        # Examples with JOINs or simple aggregations
        return [ex for ex in all_examples if "JOIN" in ex["query"] or "GROUP BY" in ex["query"]]
    
    elif complexity == "complex":
        # Examples with multiple JOINs, subqueries, or complex aggregations
        return [ex for ex in all_examples if ex["query"].count("JOIN") > 1 or "GROUP BY" in ex["query"]]
    
    return all_examples


def get_relevant_examples(question: str, max_examples: int = 3) -> List[Dict[str, Any]]:
    """
    Get most relevant examples based on the question
    
    Args:
        question: Natural language question
        max_examples: Maximum number of examples to return
        
    Returns:
        List of relevant examples
    """
    all_examples = get_few_shot_examples()
    question_lower = question.lower()
    
    # Simple keyword matching for relevance
    scored_examples = []
    for example in all_examples:
        score = 0
        example_lower = example["question"].lower()
        
        # Check for common words
        question_words = set(question_lower.split())
        example_words = set(example_lower.split())
        common_words = question_words & example_words
        score += len(common_words)
        
        # Check for specific keywords
        if "count" in question_lower and "COUNT" in example["query"]:
            score += 5
        if "average" in question_lower or "avg" in question_lower and "AVG" in example["query"]:
            score += 5
        if "join" in question_lower or "with" in question_lower and "JOIN" in example["query"]:
            score += 3
        if "top" in question_lower or "most" in question_lower and "ORDER BY" in example["query"]:
            score += 3
        
        scored_examples.append((score, example))
    
    # Sort by score and return top examples
    scored_examples.sort(key=lambda x: x[0], reverse=True)
    return [ex for score, ex in scored_examples[:max_examples]]
