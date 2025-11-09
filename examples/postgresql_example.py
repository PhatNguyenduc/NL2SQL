"""PostgreSQL-specific example"""

import os
from dotenv import load_dotenv
from src.core.converter import NL2SQLConverter
from src.models.sql_query import DatabaseType

load_dotenv()


def main():
    """PostgreSQL example with advanced queries"""
    
    # Initialize for PostgreSQL
    converter = NL2SQLConverter(
        connection_string=os.getenv("DATABASE_URL"),
        database_type=DatabaseType.POSTGRESQL,
        model="gpt-4o-mini",
        enable_few_shot=True
    )
    
    print("PostgreSQL NL2SQL Examples")
    print("=" * 80)
    
    # PostgreSQL-specific queries
    questions = [
        # Date/time functions
        "Show users registered in the last 30 days",
        "What's the total revenue by month for 2024?",
        
        # Window functions
        "Show users with their order count and rank by spending",
        
        # JSON operations (if you have JSON columns)
        "Find all products with specific attributes",
        
        # Full-text search
        "Search products by description containing 'laptop'",
        
        # CTEs (Common Table Expressions)
        "Show average order value compared to overall average",
        
        # Array operations (if you use arrays)
        "Find orders with multiple items"
    ]
    
    for question in questions:
        print(f"\nQuestion: {question}")
        print("-" * 80)
        
        try:
            sql_query = converter.generate_sql(question, temperature=0.1)
            
            print(f"SQL:\n{sql_query.query}")
            print(f"\nExplanation: {sql_query.explanation}")
            print(f"Confidence: {sql_query.confidence:.2%}")
            
            # Optionally execute
            # result = converter.query_executor.execute(sql_query.query)
            # if result.success:
            #     print(f"Rows: {result.row_count}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    converter.close()


if __name__ == "__main__":
    main()
