"""NL2SQL - Natural Language to SQL Converter"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from src.core.converter import NL2SQLConverter
from src.models.sql_query import SQLQuery, DatabaseConfig

__all__ = ["NL2SQLConverter", "SQLQuery", "DatabaseConfig"]
