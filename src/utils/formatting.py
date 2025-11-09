"""SQL formatting and output formatting utilities"""

import sqlparse
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel
import json

console = Console()


def format_sql(query: str, reindent: bool = True, keyword_case: str = 'upper') -> str:
    """
    Format SQL query for better readability
    
    Args:
        query: SQL query to format
        reindent: Whether to reindent the query
        keyword_case: 'upper', 'lower', or 'capitalize' for SQL keywords
        
    Returns:
        Formatted SQL query
    """
    try:
        formatted = sqlparse.format(
            query,
            reindent=reindent,
            keyword_case=keyword_case,
            strip_comments=False,
            use_space_around_operators=True
        )
        return formatted
    except Exception as e:
        # If formatting fails, return original query
        return query


def format_results(
    results: List[Dict[str, Any]], 
    columns: Optional[List[str]] = None,
    max_rows: int = 100
) -> str:
    """
    Format query results as a readable string
    
    Args:
        results: List of result rows as dictionaries
        columns: List of column names (optional, will be inferred)
        max_rows: Maximum number of rows to display
        
    Returns:
        Formatted results string
    """
    if not results:
        return "No results found"
    
    # Limit rows
    if len(results) > max_rows:
        results = results[:max_rows]
        truncated = True
    else:
        truncated = False
    
    # Get columns
    if columns is None:
        columns = list(results[0].keys())
    
    # Create table
    output = []
    
    # Header
    header = " | ".join(columns)
    separator = "-+-".join(["-" * len(col) for col in columns])
    output.append(header)
    output.append(separator)
    
    # Rows
    for row in results:
        row_str = " | ".join([str(row.get(col, "")) for col in columns])
        output.append(row_str)
    
    if truncated:
        output.append(f"\n... (showing {max_rows} of {len(results)} rows)")
    
    return "\n".join(output)


def print_sql(query: str, title: str = "Generated SQL"):
    """
    Pretty print SQL query with syntax highlighting
    
    Args:
        query: SQL query to print
        title: Title for the panel
    """
    formatted = format_sql(query)
    syntax = Syntax(formatted, "sql", theme="monokai", line_numbers=True)
    panel = Panel(syntax, title=title, border_style="blue")
    console.print(panel)


def print_results_table(
    results: List[Dict[str, Any]], 
    title: str = "Query Results",
    max_rows: int = 100
):
    """
    Pretty print query results as a Rich table
    
    Args:
        results: List of result rows
        title: Title for the table
        max_rows: Maximum rows to display
    """
    if not results:
        console.print(f"[yellow]{title}: No results found[/yellow]")
        return
    
    # Limit rows
    if len(results) > max_rows:
        results = results[:max_rows]
        truncated = True
    else:
        truncated = False
    
    # Create Rich table
    table = Table(title=title, show_header=True, header_style="bold magenta")
    
    # Add columns
    columns = list(results[0].keys())
    for col in columns:
        table.add_column(col, style="cyan")
    
    # Add rows
    for row in results:
        table.add_row(*[str(row.get(col, "")) for col in columns])
    
    console.print(table)
    
    if truncated:
        console.print(f"[yellow]... (showing {max_rows} rows)[/yellow]")


def print_schema_info(schema_text: str):
    """
    Pretty print database schema information
    
    Args:
        schema_text: Formatted schema text
    """
    panel = Panel(
        schema_text,
        title="Database Schema",
        border_style="green",
        padding=(1, 2)
    )
    console.print(panel)


def print_error(error_message: str, title: str = "Error"):
    """
    Pretty print error message
    
    Args:
        error_message: Error message to print
        title: Title for the error panel
    """
    panel = Panel(
        f"[red]{error_message}[/red]",
        title=title,
        border_style="red"
    )
    console.print(panel)


def print_warning(warning_message: str, title: str = "Warning"):
    """
    Pretty print warning message
    
    Args:
        warning_message: Warning message to print
        title: Title for the warning panel
    """
    panel = Panel(
        f"[yellow]{warning_message}[/yellow]",
        title=title,
        border_style="yellow"
    )
    console.print(panel)


def print_success(success_message: str, title: str = "Success"):
    """
    Pretty print success message
    
    Args:
        success_message: Success message to print
        title: Title for the success panel
    """
    panel = Panel(
        f"[green]{success_message}[/green]",
        title=title,
        border_style="green"
    )
    console.print(panel)


def format_json(data: Dict[str, Any], indent: int = 2) -> str:
    """
    Format dictionary as pretty JSON
    
    Args:
        data: Dictionary to format
        indent: Indentation level
        
    Returns:
        Formatted JSON string
    """
    return json.dumps(data, indent=indent, default=str)


def truncate_string(text: str, max_length: int = 100) -> str:
    """
    Truncate string to maximum length
    
    Args:
        text: String to truncate
        max_length: Maximum length
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_execution_time(seconds: float) -> str:
    """
    Format execution time in human-readable format
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    if seconds < 0.001:
        return f"{seconds * 1000000:.2f} μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    else:
        return f"{seconds:.2f} s"


def format_row_count(count: int) -> str:
    """
    Format row count with proper pluralization
    
    Args:
        count: Number of rows
        
    Returns:
        Formatted string
    """
    if count == 1:
        return "1 row"
    else:
        return f"{count:,} rows"
