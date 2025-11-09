"""MySQL-specific example"""

import os
from dotenv import load_dotenv
from src.core.converter import NL2SQLConverter
from src.models.sql_query import DatabaseType

load_dotenv()


def main():
    """MySQL example with specific queries"""
    
    # Initialize for MySQL
    converter = NL2SQLConverter(
        connection_string=os.getenv("DATABASE_URL"),  # mysql+pymysql://...
        database_type=DatabaseType.MYSQL,
        model="gpt-4o-mini"
    )
    
    print("MySQL NL2SQL Examples")
    print("=" * 80)
    
    # MySQL-specific queries
    questions = [
        # Date/time functions
        "Show orders from the last 7 days",
        "What's the revenue by day of week?",
        
        # String functions
        "Find users whose name starts with 'J'",
        "Show products with names containing 'phone' (case-insensitive)",
        
        # Aggregations
        "Show category-wise product count and average price",
        
        # Subqueries
        "Find products priced above the average",
        
        # Group by with having
        "Show users who have placed more than 5 orders",
        
        # Joins
        "List all orders with customer and product details"
    ]
    
    for question in questions:
        print(f"\nQuestion: {question}")
        print("-" * 80)
        
        try:
            sql_query = converter.generate_sql(question, temperature=0.1)
            
            print(f"SQL:\n{sql_query.query}")
            print(f"\nExplanation: {sql_query.explanation}")
            print(f"Confidence: {sql_query.confidence:.2%}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    converter.close()


if __name__ == "__main__":
    main()
