"""Command-line interface for NL2SQL"""

import os
import sys
import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from src.core.converter import NL2SQLConverter
from src.models.sql_query import DatabaseType
from src.utils.formatting import (
    print_sql,
    print_results_table,
    print_schema_info,
    print_error,
    print_success,
    print_warning,
    format_execution_time,
    format_row_count
)

# Load environment variables
load_dotenv()

console = Console()


def get_converter_from_env():
    """Create NL2SQLConverter from environment variables"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print_error("DATABASE_URL not set in environment variables")
        sys.exit(1)
    
    # Detect database type from URL
    if db_url.startswith("postgresql://"):
        db_type = DatabaseType.POSTGRESQL
    elif db_url.startswith("mysql://") or db_url.startswith("mysql+pymysql://"):
        db_type = DatabaseType.MYSQL
    else:
        print_error("Unsupported database type in DATABASE_URL")
        sys.exit(1)
    
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    default_limit = int(os.getenv("DEFAULT_LIMIT", "100"))
    
    try:
        converter = NL2SQLConverter(
            connection_string=db_url,
            database_type=db_type,
            model=model,
            default_limit=default_limit
        )
        return converter
    except Exception as e:
        print_error(f"Failed to initialize converter: {e}")
        sys.exit(1)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """NL2SQL - Natural Language to SQL Converter
    
    Convert natural language questions to SQL queries for PostgreSQL and MySQL.
    """
    pass


@cli.command()
@click.argument('question', type=str)
@click.option('--execute', '-e', is_flag=True, help='Execute the generated query')
@click.option('--temperature', '-t', type=float, default=0.1, help='Model temperature (0.0-1.0)')
@click.option('--show-confidence', '-c', is_flag=True, help='Show confidence score')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def query(question, execute, temperature, show_confidence, output_json):
    """Generate SQL from natural language question
    
    Example:
        nl2sql query "Show me all users"
        nl2sql query "How many orders were placed last month?" --execute
    """
    converter = get_converter_from_env()
    
    try:
        if execute:
            # Generate and execute
            console.print(f"[cyan]Question:[/cyan] {question}\n")
            
            sql_query, result = converter.generate_and_execute(question, temperature)
            
            # Show query
            print_sql(sql_query.query, title="Generated SQL")
            
            if show_confidence:
                console.print(f"\n[dim]Confidence: {sql_query.confidence:.2%}[/dim]")
            
            console.print(f"\n[dim]{sql_query.explanation}[/dim]\n")
            
            # Show results
            if result.success:
                if result.rows:
                    print_results_table(result.rows, title="Query Results")
                    console.print(f"\n[green]✓[/green] {format_row_count(result.row_count)} in {format_execution_time(result.execution_time)}")
                else:
                    print_warning("Query executed successfully but returned no results")
            else:
                print_error(f"Query execution failed: {result.error_message}")
        
        else:
            # Just generate
            console.print(f"[cyan]Question:[/cyan] {question}\n")
            
            sql_query = converter.generate_sql(question, temperature)
            
            if output_json:
                import json
                console.print(json.dumps(sql_query.model_dump(), indent=2))
            else:
                print_sql(sql_query.query, title="Generated SQL")
                
                if show_confidence:
                    console.print(f"\n[dim]Confidence: {sql_query.confidence:.2%}[/dim]")
                
                console.print(f"\n[dim]{sql_query.explanation}[/dim]")
                
                if sql_query.potential_issues:
                    print_warning("Potential Issues:\n" + "\n".join(f"- {issue}" for issue in sql_query.potential_issues))
    
    except Exception as e:
        print_error(f"Error: {e}")
        sys.exit(1)
    
    finally:
        converter.close()


@cli.command()
@click.option('--sample-data', '-s', is_flag=True, help='Include sample data from tables')
def schema(sample_data):
    """Display database schema information
    
    Example:
        nl2sql schema
        nl2sql schema --sample-data
    """
    converter = get_converter_from_env()
    
    try:
        console.print("[cyan]Loading database schema...[/cyan]\n")
        
        schema = converter.load_schema(include_sample_data=sample_data)
        schema_text = converter.get_schema_info()
        
        print_schema_info(schema_text)
        
        console.print(f"\n[green]✓[/green] Found {schema.total_tables} tables")
    
    except Exception as e:
        print_error(f"Error loading schema: {e}")
        sys.exit(1)
    
    finally:
        converter.close()


@cli.command()
def test():
    """Test database connection
    
    Example:
        nl2sql test
    """
    converter = get_converter_from_env()
    
    try:
        console.print("[cyan]Testing database connection...[/cyan]\n")
        
        if converter.test_connection():
            print_success("Database connection successful!")
        else:
            print_error("Database connection failed!")
            sys.exit(1)
    
    except Exception as e:
        print_error(f"Connection test failed: {e}")
        sys.exit(1)
    
    finally:
        converter.close()


@cli.command()
@click.option('--input-file', '-i', type=click.Path(exists=True), help='Input file with questions (one per line)')
@click.option('--output-file', '-o', type=click.Path(), help='Output file for results')
@click.option('--execute', '-e', is_flag=True, help='Execute all generated queries')
def batch(input_file, output_file, execute):
    """Process multiple questions in batch
    
    Example:
        nl2sql batch -i questions.txt -o results.json
    """
    if not input_file:
        print_error("Input file required for batch processing")
        sys.exit(1)
    
    converter = get_converter_from_env()
    
    try:
        # Read questions
        with open(input_file, 'r', encoding='utf-8') as f:
            questions = [line.strip() for line in f if line.strip()]
        
        console.print(f"[cyan]Processing {len(questions)} questions...[/cyan]\n")
        
        results = []
        
        for i, question in enumerate(questions, 1):
            console.print(f"[dim]Question {i}/{len(questions)}:[/dim] {question}")
            
            try:
                if execute:
                    sql_query, query_result = converter.generate_and_execute(question)
                    results.append({
                        "question": question,
                        "sql": sql_query.model_dump(),
                        "result": query_result.model_dump()
                    })
                else:
                    sql_query = converter.generate_sql(question)
                    results.append({
                        "question": question,
                        "sql": sql_query.model_dump()
                    })
                
                console.print(f"[green]✓[/green] Generated\n")
            
            except Exception as e:
                console.print(f"[red]✗[/red] Error: {e}\n")
                results.append({
                    "question": question,
                    "error": str(e)
                })
        
        # Save results
        if output_file:
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            print_success(f"Results saved to {output_file}")
        else:
            import json
            console.print(json.dumps(results, indent=2, default=str))
    
    except Exception as e:
        print_error(f"Batch processing failed: {e}")
        sys.exit(1)
    
    finally:
        converter.close()


@cli.command()
def config():
    """Show current configuration
    
    Example:
        nl2sql config
    """
    console.print(Panel("[bold]Current Configuration[/bold]", style="blue"))
    
    configs = {
        "DATABASE_URL": os.getenv("DATABASE_URL", "[red]Not set[/red]"),
        "OPENAI_API_KEY": "[green]Set[/green]" if os.getenv("OPENAI_API_KEY") else "[red]Not set[/red]",
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "DEFAULT_LIMIT": os.getenv("DEFAULT_LIMIT", "100"),
        "ENABLE_CACHING": os.getenv("ENABLE_CACHING", "true"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO")
    }
    
    for key, value in configs.items():
        # Mask sensitive parts of DATABASE_URL
        if key == "DATABASE_URL" and value != "[red]Not set[/red]":
            try:
                # Mask password in URL
                parts = value.split("@")
                if len(parts) > 1:
                    user_pass = parts[0].split("://")[1]
                    if ":" in user_pass:
                        user = user_pass.split(":")[0]
                        value = value.replace(user_pass, f"{user}:****")
            except:
                pass
        
        console.print(f"[cyan]{key}:[/cyan] {value}")


def main():
    """Main entry point"""
    cli()


if __name__ == '__main__':
    main()
