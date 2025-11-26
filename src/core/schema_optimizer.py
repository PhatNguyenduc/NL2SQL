"""
Schema Optimization Module
Implements compact schema representation with semantic grouping
"""

import re
import logging
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from src.models.sql_query import DatabaseSchema, TableSchema

logger = logging.getLogger(__name__)


@dataclass
class TableGroup:
    """Group of semantically related tables"""
    name: str
    description: str
    tables: List[str] = field(default_factory=list)


# Semantic table groupings based on common patterns
DEFAULT_TABLE_GROUPS = {
    "sales": {
        "keywords": ["order", "sale", "invoice", "payment", "transaction", "cart", "checkout"],
        "description": "Sales & Orders"
    },
    "customers": {
        "keywords": ["customer", "user", "client", "member", "account", "profile"],
        "description": "Customers & Users"
    },
    "products": {
        "keywords": ["product", "item", "sku", "catalog", "inventory", "stock", "warehouse"],
        "description": "Products & Inventory"
    },
    "hr": {
        "keywords": ["employee", "staff", "department", "salary", "payroll", "job", "position"],
        "description": "HR & Employees"
    },
    "content": {
        "keywords": ["post", "article", "blog", "comment", "review", "rating", "feedback"],
        "description": "Content & Reviews"
    },
    "shipping": {
        "keywords": ["shipping", "delivery", "address", "location", "tracking", "carrier"],
        "description": "Shipping & Delivery"
    },
    "finance": {
        "keywords": ["payment", "refund", "credit", "discount", "coupon", "promotion", "tax"],
        "description": "Finance & Payments"
    },
    "analytics": {
        "keywords": ["log", "event", "session", "visit", "click", "metric", "stat"],
        "description": "Analytics & Logs"
    }
}


class SchemaOptimizer:
    """
    Optimizes schema representation for LLM consumption
    
    Features:
    - Compact schema format (table + columns in one line)
    - Semantic grouping of related tables
    - FK/PK relationship extraction
    - Intelligent schema pruning based on question
    """
    
    def __init__(self, schema: DatabaseSchema):
        self.schema = schema
        self.table_groups: Dict[str, List[str]] = {}
        self.relationships: List[Dict] = []
        self._analyze_schema()
    
    def _analyze_schema(self):
        """Analyze schema and build groups + relationships"""
        self._build_table_groups()
        self._extract_relationships()
    
    def _build_table_groups(self):
        """Group tables semantically based on naming patterns"""
        grouped_tables: Set[str] = set()
        
        for group_name, group_info in DEFAULT_TABLE_GROUPS.items():
            matching_tables = []
            for table in self.schema.tables:
                table_lower = table.table_name.lower()
                for keyword in group_info["keywords"]:
                    if keyword in table_lower:
                        matching_tables.append(table.table_name)
                        grouped_tables.add(table.table_name)
                        break
            
            if matching_tables:
                self.table_groups[group_name] = {
                    "description": group_info["description"],
                    "tables": matching_tables
                }
        
        # Add ungrouped tables to "other"
        other_tables = [
            t.table_name for t in self.schema.tables 
            if t.table_name not in grouped_tables
        ]
        if other_tables:
            self.table_groups["other"] = {
                "description": "Other Tables",
                "tables": other_tables
            }
    
    def _extract_relationships(self):
        """Extract important FK relationships for JOIN hints"""
        for table in self.schema.tables:
            # Handle case where foreign_keys is None
            fks = table.foreign_keys if table.foreign_keys else []
            for fk in fks:
                self.relationships.append({
                    "from_table": table.table_name,
                    "from_column": fk.get("column", fk.get("from_column", "")),
                    "to_table": fk.get("referenced_table", fk.get("to_table", "")),
                    "to_column": fk.get("referenced_column", fk.get("to_column", ""))
                })
    
    def format_compact_schema(self, include_types: bool = False) -> str:
        """
        Format schema in compact one-line-per-table format
        
        Args:
            include_types: Include column types (increases tokens)
            
        Returns:
            Compact schema string
        """
        output = []
        output.append(f"# Database: {self.schema.database_name}")
        output.append(f"# Tables: {self.schema.total_tables}\n")
        
        # Output by semantic groups
        for group_name, group_info in self.table_groups.items():
            output.append(f"## {group_info['description']}")
            
            for table_name in group_info["tables"]:
                table = self._get_table(table_name)
                if table:
                    line = self._format_table_compact(table, include_types)
                    output.append(line)
            
            output.append("")  # Empty line between groups
        
        # Add relationships section
        if self.relationships:
            output.append("## Relationships (JOIN keys)")
            for rel in self.relationships:
                output.append(
                    f"{rel['from_table']}.{rel['from_column']} → "
                    f"{rel['to_table']}.{rel['to_column']}"
                )
        
        return "\n".join(output)
    
    def _format_table_compact(self, table: TableSchema, include_types: bool) -> str:
        """Format single table in compact format"""
        # Mark primary keys with asterisk
        cols = []
        for col in table.columns:
            col_name = col["name"]
            if col_name in table.primary_keys:
                col_name = f"*{col_name}"  # PK marker
            
            if include_types:
                # Simplify types
                col_type = self._simplify_type(col["type"])
                cols.append(f"{col_name}:{col_type}")
            else:
                cols.append(col_name)
        
        return f"{table.table_name}({', '.join(cols)})"
    
    def _simplify_type(self, type_str: str) -> str:
        """Simplify SQL type to short form"""
        type_lower = str(type_str).lower()
        
        if "int" in type_lower:
            return "int"
        elif "varchar" in type_lower or "text" in type_lower or "char" in type_lower:
            return "str"
        elif "decimal" in type_lower or "numeric" in type_lower or "float" in type_lower or "double" in type_lower:
            return "num"
        elif "date" in type_lower or "time" in type_lower:
            return "dt"
        elif "bool" in type_lower:
            return "bool"
        elif "json" in type_lower:
            return "json"
        else:
            return "?"
    
    def _get_table(self, table_name: str) -> Optional[TableSchema]:
        """Get table by name"""
        for table in self.schema.tables:
            if table.table_name == table_name:
                return table
        return None
    
    def get_relevant_tables(
        self, 
        question: str, 
        max_tables: int = 10
    ) -> List[TableSchema]:
        """
        Get tables most relevant to the question (simple keyword matching)
        
        Args:
            question: User's question
            max_tables: Maximum tables to return
            
        Returns:
            List of relevant TableSchema objects
        """
        question_lower = question.lower()
        scored_tables = []
        
        for table in self.schema.tables:
            score = 0
            table_lower = table.table_name.lower()
            
            # Check if table name appears in question
            if table_lower in question_lower:
                score += 10
            
            # Check individual words
            table_words = re.split(r'[_\s]', table_lower)
            for word in table_words:
                if len(word) > 2 and word in question_lower:
                    score += 5
            
            # Check column names
            for col in table.columns:
                col_lower = col["name"].lower()
                if col_lower in question_lower:
                    score += 3
            
            if score > 0:
                scored_tables.append((score, table))
        
        # Sort by score descending
        scored_tables.sort(key=lambda x: x[0], reverse=True)
        
        # If no matches, return all tables (up to max)
        if not scored_tables:
            return self.schema.tables[:max_tables]
        
        return [t for _, t in scored_tables[:max_tables]]
    
    def format_relevant_schema(
        self, 
        question: str, 
        include_types: bool = False,
        max_tables: int = 10
    ) -> str:
        """
        Format only relevant tables for the question
        
        Args:
            question: User's question
            include_types: Include column types
            max_tables: Maximum tables to include
            
        Returns:
            Compact schema for relevant tables
        """
        relevant = self.get_relevant_tables(question, max_tables)
        
        if len(relevant) == len(self.schema.tables):
            # All tables relevant, use full compact schema
            return self.format_compact_schema(include_types)
        
        output = []
        output.append(f"# Relevant Tables ({len(relevant)}/{self.schema.total_tables})")
        
        for table in relevant:
            output.append(self._format_table_compact(table, include_types))
        
        # Add relevant relationships
        relevant_names = {t.table_name for t in relevant}
        relevant_rels = [
            r for r in self.relationships
            if r["from_table"] in relevant_names and r["to_table"] in relevant_names
        ]
        
        if relevant_rels:
            output.append("\n## JOIN keys")
            for rel in relevant_rels:
                output.append(
                    f"{rel['from_table']}.{rel['from_column']} → "
                    f"{rel['to_table']}.{rel['to_column']}"
                )
        
        return "\n".join(output)
    
    def get_join_path(
        self, 
        table1: str, 
        table2: str
    ) -> Optional[List[Dict]]:
        """
        Find JOIN path between two tables
        
        Args:
            table1: First table name
            table2: Second table name
            
        Returns:
            List of relationship dicts forming the path, or None
        """
        # Direct relationship
        for rel in self.relationships:
            if (rel["from_table"] == table1 and rel["to_table"] == table2) or \
               (rel["from_table"] == table2 and rel["to_table"] == table1):
                return [rel]
        
        # One-hop relationship (through intermediate table)
        for rel1 in self.relationships:
            if rel1["from_table"] == table1 or rel1["to_table"] == table1:
                intermediate = rel1["to_table"] if rel1["from_table"] == table1 else rel1["from_table"]
                
                for rel2 in self.relationships:
                    if (rel2["from_table"] == intermediate and rel2["to_table"] == table2) or \
                       (rel2["from_table"] == table2 and rel2["to_table"] == intermediate):
                        return [rel1, rel2]
        
        return None
