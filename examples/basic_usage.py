"""Basic usage example for NL2SQL"""

import os
from dotenv import load_dotenv
from src.core.converter import NL2SQLConverter
from src.models.sql_query import DatabaseType

# Load environment variables
load_dotenv()


def main():
    """Basic usage example"""
    
    # Initialize converter
    converter = NL2SQLConverter(
        connection_string=os.getenv("DATABASE_URL"),
        database_type=DatabaseType.POSTGRESQL,  # or DatabaseType.MYSQL
        enable_few_shot=True,
        enable_auto_execute=False
    )
    
    print("=" * 80)
    print("NL2SQL Basic Usage Example")
    print("=" * 80)
    
    # Test connection
    print("\n1. Testing database connection...")
    if converter.test_connection():
        print("✓ Connection successful!")
    else:
        print("✗ Connection failed!")
        return
    
    # Load schema
    print("\n2. Loading database schema...")
    schema = converter.load_schema()
    print(f"✓ Loaded schema: {schema.total_tables} tables")
    print("\nTables:")
    for table in schema.tables:
        print(f"  - {table.table_name} ({len(table.columns)} columns)")
    
    # Generate SQL queries
    print("\n3. Generating SQL queries...")
    
    questions = [
        "Show me all users",
        "How many orders do we have?",
        "What are the top 5 most expensive products?",
        "Find users who have never placed an order"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n--- Question {i} ---")
        print(f"Q: {question}")
        
        try:
            sql_query = converter.generate_sql(question)
            print(f"\nGenerated SQL:")
            print(sql_query.query)
            print(f"\nExplanation: {sql_query.explanation}")
            print(f"Confidence: {sql_query.confidence:.2%}")
            
            if sql_query.potential_issues:
                print(f"Warnings: {', '.join(sql_query.potential_issues)}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    # Execute a query
    print("\n" + "=" * 80)
    print("4. Executing a query...")
    print("=" * 80)
    
    question = "Show me all users"
    print(f"Q: {question}\n")
    
    try:
        sql_query, result = converter.generate_and_execute(question)
        
        print("Generated SQL:")
        print(sql_query.query)
        print()
        
        if result.success:
            print(f"✓ Query executed successfully!")
            print(f"Rows returned: {result.row_count}")
            print(f"Execution time: {result.execution_time:.3f}s")
            
            if result.rows:
                print("\nResults:")
                for row in result.rows[:5]:  # Show first 5 rows
                    print(f"  {row}")
        else:
            print(f"✗ Query failed: {result.error_message}")
    
    except Exception as e:
        print(f"Error: {e}")
    
    # Clean up
    converter.close()
    print("\n" + "=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == "__main__":
    main()
