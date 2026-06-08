"""MySQL database adapter using SQLAlchemy Inspector."""

from typing import Any, Dict, List

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from database.base_adapter import BaseAdapter


class MySQLAdapter(BaseAdapter):
    """MySQL metadata access via SQLAlchemy Inspector."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._inspector = inspect(engine)

    def get_tables(self) -> List[str]:
        return self._inspector.get_table_names()

    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        return self._inspector.get_columns(table_name)
