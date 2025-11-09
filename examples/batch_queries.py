"""Batch processing example"""

import os
import json
from dotenv import load_dotenv
from src.core.converter import NL2SQLConverter
from src.models.sql_query import DatabaseType

load_dotenv()


def main():
    """Process multiple questions in batch"""
    
    converter = NL2SQLConverter(
        connection_string=os.getenv("DATABASE_URL"),
        database_type=DatabaseType.POSTGRESQL,
        enable_few_shot=True
    )
    
    print("Batch Query Generation Example")
    print("=" * 80)
    
    # List of questions to process
    questions = [
        "How many users are there?",
        "What's the average order value?",
        "Show top 10 products by sales",
        "Find inactive users (no orders in last 90 days)",
        "What's the total revenue this month?",
        "Show customer lifetime value",
        "Find products that are low in stock",
        "What's the order fulfillment rate?"
    ]
    
    print(f"Processing {len(questions)} questions...\n")
    
    # Generate queries in batch
    results = converter.batch_generate(questions, temperature=0.1)
    
    # Display results
    for i, (question, sql_query) in enumerate(zip(questions, results), 1):
        print(f"{i}. {question}")
        print(f"   SQL: {sql_query.query[:100]}...")
        print(f"   Confidence: {sql_query.confidence:.2%}")
        print()
    
    # Save to JSON file
    output_file = "batch_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        output_data = []
        for question, sql_query in zip(questions, results):
            output_data.append({
                "question": question,
                "sql": sql_query.query,
                "explanation": sql_query.explanation,
                "confidence": sql_query.confidence,
                "tables_used": sql_query.tables_used
            })
        json.dump(output_data, f, indent=2)
    
    print(f"Results saved to {output_file}")
    
    # Execute all queries (optional)
    print("\n" + "=" * 80)
    print("Executing all queries...")
    print("=" * 80 + "\n")
    
    for i, (question, sql_query) in enumerate(zip(questions, results), 1):
        print(f"{i}. {question}")
        
        try:
            result = converter.query_executor.execute(sql_query.query)
            
            if result.success:
                print(f"   ✓ Success: {result.row_count} rows in {result.execution_time:.3f}s")
                if result.rows:
                    print(f"   First result: {result.rows[0]}")
            else:
                print(f"   ✗ Failed: {result.error_message}")
        
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        print()
    
    converter.close()


if __name__ == "__main__":
    main()
