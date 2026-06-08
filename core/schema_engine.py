"""Metadata discovery engine using SQLAlchemy Inspector."""

from typing import Any, Dict, List, Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


class SchemaEngine:
    """Discovers schema metadata from a source database."""

    @staticmethod
    def _inspector(engine: Engine):
        return inspect(engine)

    @staticmethod
    def get_tables(engine: Engine, schema: Optional[str] = None) -> List[str]:
        inspector = SchemaEngine._inspector(engine)
        if schema:
            return inspector.get_table_names(schema=schema)
        return inspector.get_table_names()

    @staticmethod
    def get_columns(engine: Engine, table_name: str) -> List[Dict[str, Any]]:
        return SchemaEngine._inspector(engine).get_columns(table_name)

    @staticmethod
    def get_primary_key(engine: Engine, table_name: str) -> Dict[str, Any]:
        return SchemaEngine._inspector(engine).get_pk_constraint(table_name)

    @staticmethod
    def get_foreign_keys(engine: Engine, table_name: str) -> List[Dict[str, Any]]:
        return SchemaEngine._inspector(engine).get_foreign_keys(table_name)

    @staticmethod
    def get_indexes(engine: Engine, table_name: str) -> List[Dict[str, Any]]:
        return SchemaEngine._inspector(engine).get_indexes(table_name)

    @staticmethod
    def get_unique_constraints(
        engine: Engine, table_name: str
    ) -> List[Dict[str, Any]]:
        return SchemaEngine._inspector(engine).get_unique_constraints(table_name)

    @staticmethod
    def get_table_metadata(engine: Engine, table_name: str) -> Dict[str, Any]:
        """Return full metadata bundle for a table."""
        inspector = SchemaEngine._inspector(engine)

        columns = inspector.get_columns(table_name)
        primary_keys = inspector.get_pk_constraint(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        indexes = inspector.get_indexes(table_name)
        unique_constraints = inspector.get_unique_constraints(table_name)

        return {
            "table_name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
            "unique_constraints": unique_constraints,
        }

    @staticmethod
    def get_all_tables_metadata(
        engine: Engine, tables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Return metadata for all tables or a provided subset."""
        table_list = tables or SchemaEngine.get_tables(engine)
        return [
            SchemaEngine.get_table_metadata(engine, table) for table in table_list
        ]
