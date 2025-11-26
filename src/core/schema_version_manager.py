"""
Schema Version Manager for Cache Invalidation

Tracks schema versions using content hashing to detect changes
and invalidate caches when schema is modified.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SchemaSnapshot:
    """
    Immutable snapshot of database schema with version hash
    
    Used to detect schema changes for cache invalidation.
    The hash is computed from table structures, columns, types, and relationships.
    """
    version_hash: str
    table_count: int
    tables: Dict[str, Dict[str, Any]]  # table_name -> {columns, types, relationships}
    created_at: datetime = field(default_factory=datetime.now)
    
    def __hash__(self):
        return hash(self.version_hash)
    
    def __eq__(self, other):
        if not isinstance(other, SchemaSnapshot):
            return False
        return self.version_hash == other.version_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for serialization"""
        return {
            "version_hash": self.version_hash,
            "table_count": self.table_count,
            "tables": self.tables,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SchemaSnapshot':
        """Create snapshot from dictionary"""
        return cls(
            version_hash=data["version_hash"],
            table_count=data["table_count"],
            tables=data["tables"],
            created_at=datetime.fromisoformat(data["created_at"])
        )


class SchemaVersionManager:
    """
    Manages schema versions for cache invalidation
    
    Features:
    - Compute deterministic hash from schema structure
    - Detect schema changes by comparing hashes
    - Track schema history for debugging
    - Support incremental change detection
    """
    
    def __init__(self, max_history: int = 10):
        """
        Initialize schema version manager
        
        Args:
            max_history: Maximum number of schema versions to keep in history
        """
        self.max_history = max_history
        self.current_snapshot: Optional[SchemaSnapshot] = None
        self.history: List[SchemaSnapshot] = []
    
    def compute_schema_hash(self, schema: Any) -> str:
        """
        Compute deterministic hash from schema structure
        
        The hash is based on:
        - Table names (sorted)
        - Column names, types, and constraints for each table
        - Foreign key relationships
        - Primary keys
        
        Args:
            schema: DatabaseSchema object
            
        Returns:
            Hex string hash of schema structure
        """
        if schema is None:
            return hashlib.sha256(b"empty_schema").hexdigest()[:16]
        
        # Build normalized representation
        schema_data = self._normalize_schema(schema)
        
        # Create deterministic JSON string (sorted keys)
        json_str = json.dumps(schema_data, sort_keys=True, ensure_ascii=True)
        
        # Compute SHA256 hash and truncate for readability
        hash_bytes = hashlib.sha256(json_str.encode('utf-8')).digest()
        return hash_bytes.hex()[:16]
    
    def _normalize_schema(self, schema: Any) -> Dict[str, Any]:
        """
        Normalize schema to consistent dictionary format
        
        Args:
            schema: DatabaseSchema object
            
        Returns:
            Normalized dictionary representation
        """
        tables = {}
        
        for table in getattr(schema, 'tables', []):
            table_name = getattr(table, 'table_name', str(table))
            
            # Extract columns
            columns = []
            for col in getattr(table, 'columns', []):
                if isinstance(col, dict):
                    columns.append({
                        "name": col.get("name", ""),
                        "type": col.get("type", ""),
                        "nullable": col.get("nullable", True),
                        "primary_key": col.get("primary_key", False)
                    })
                else:
                    columns.append({
                        "name": getattr(col, 'name', str(col)),
                        "type": getattr(col, 'type', 'unknown'),
                        "nullable": getattr(col, 'nullable', True),
                        "primary_key": getattr(col, 'primary_key', False)
                    })
            
            # Sort columns by name for consistency
            columns.sort(key=lambda x: x["name"])
            
            # Extract foreign keys (handle None case)
            foreign_keys = []
            fk_list = getattr(table, 'foreign_keys', None) or []
            for fk in fk_list:
                if isinstance(fk, dict):
                    foreign_keys.append({
                        "column": fk.get("column", ""),
                        "references_table": fk.get("references_table", fk.get("referenced_table", "")),
                        "references_column": fk.get("references_column", fk.get("referenced_column", ""))
                    })
                else:
                    foreign_keys.append({
                        "column": getattr(fk, 'column', ''),
                        "references_table": getattr(fk, 'references_table', ''),
                        "references_column": getattr(fk, 'references_column', '')
                    })
            
            foreign_keys.sort(key=lambda x: x["column"])
            
            tables[table_name] = {
                "columns": columns,
                "foreign_keys": foreign_keys,
                "row_count": getattr(table, 'row_count', 0)
            }
        
        return {
            "tables": tables,
            "table_count": len(tables)
        }
    
    def create_snapshot(self, schema: Any) -> SchemaSnapshot:
        """
        Create a new schema snapshot
        
        Args:
            schema: DatabaseSchema object
            
        Returns:
            New SchemaSnapshot
        """
        version_hash = self.compute_schema_hash(schema)
        tables = self._normalize_schema(schema)["tables"]
        
        snapshot = SchemaSnapshot(
            version_hash=version_hash,
            table_count=len(tables),
            tables=tables
        )
        
        logger.debug(f"Created schema snapshot: {version_hash}")
        return snapshot
    
    def update_schema(self, schema: Any) -> bool:
        """
        Update current schema and check if it changed
        
        Args:
            schema: New DatabaseSchema object
            
        Returns:
            True if schema changed, False otherwise
        """
        new_snapshot = self.create_snapshot(schema)
        
        if self.current_snapshot is None:
            # First schema load
            self.current_snapshot = new_snapshot
            self.history.append(new_snapshot)
            logger.info(f"Initial schema loaded: {new_snapshot.version_hash}")
            return True
        
        if new_snapshot.version_hash != self.current_snapshot.version_hash:
            # Schema changed
            old_hash = self.current_snapshot.version_hash
            
            # Add to history
            self.history.append(new_snapshot)
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
            
            self.current_snapshot = new_snapshot
            
            # Log changes
            changes = self._detect_changes(self.history[-2], new_snapshot)
            logger.info(f"Schema changed: {old_hash} -> {new_snapshot.version_hash}")
            logger.info(f"Changes detected: {changes}")
            
            return True
        
        logger.debug(f"Schema unchanged: {new_snapshot.version_hash}")
        return False
    
    def _detect_changes(
        self, 
        old_snapshot: SchemaSnapshot, 
        new_snapshot: SchemaSnapshot
    ) -> Dict[str, List[str]]:
        """
        Detect specific changes between two snapshots
        
        Args:
            old_snapshot: Previous schema snapshot
            new_snapshot: New schema snapshot
            
        Returns:
            Dictionary of changes by category
        """
        changes = {
            "tables_added": [],
            "tables_removed": [],
            "tables_modified": []
        }
        
        old_tables = set(old_snapshot.tables.keys())
        new_tables = set(new_snapshot.tables.keys())
        
        changes["tables_added"] = list(new_tables - old_tables)
        changes["tables_removed"] = list(old_tables - new_tables)
        
        # Check for modifications in existing tables
        for table in old_tables & new_tables:
            old_cols = {c["name"]: c for c in old_snapshot.tables[table]["columns"]}
            new_cols = {c["name"]: c for c in new_snapshot.tables[table]["columns"]}
            
            if old_cols != new_cols:
                changes["tables_modified"].append(table)
        
        return changes
    
    def get_current_version(self) -> Optional[str]:
        """Get current schema version hash"""
        return self.current_snapshot.version_hash if self.current_snapshot else None
    
    def get_version_info(self) -> Dict[str, Any]:
        """Get detailed version information"""
        if not self.current_snapshot:
            return {"status": "not_loaded", "version": None}
        
        return {
            "status": "loaded",
            "version": self.current_snapshot.version_hash,
            "table_count": self.current_snapshot.table_count,
            "created_at": self.current_snapshot.created_at.isoformat(),
            "history_count": len(self.history)
        }
    
    def is_compatible(self, version_hash: str) -> bool:
        """
        Check if given version hash is compatible with current schema
        
        Args:
            version_hash: Hash to check
            
        Returns:
            True if compatible (matches current)
        """
        return self.current_snapshot and self.current_snapshot.version_hash == version_hash
    
    def get_cache_key_prefix(self) -> str:
        """
        Get cache key prefix based on current schema version
        
        Returns:
            String to use as cache key prefix
        """
        version = self.get_current_version() or "unknown"
        return f"schema:{version}"
