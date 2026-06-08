"""Data transformation engine for PostgreSQL → MySQL value conversion."""

import json
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from utils.logger import Logger

logger = Logger.get_logger("transform")

TransformHook = Callable[[str, Any], Any]


class TransformationEngine:
    """Transforms row values between PostgreSQL and MySQL representations."""

    def __init__(self) -> None:
        self._custom_hooks: Dict[str, TransformHook] = {}

    def register_hook(self, column_name: str, hook: TransformHook) -> None:
        """Register a custom per-column transformation hook."""
        self._custom_hooks[column_name] = hook

    def transform_value(self, column_name: str, value: Any) -> Any:
        """Transform a single cell value."""
        if column_name in self._custom_hooks:
            return self._custom_hooks[column_name](column_name, value)

        if value is None:
            return None

        if isinstance(value, bool):
            return 1 if value else 0

        if isinstance(value, uuid.UUID):
            return str(value)

        if isinstance(value, (dict, list)):
            return json.dumps(value)

        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value

        if isinstance(value, (date, time, Decimal)):
            return value

        if isinstance(value, bytes):
            return value

        if isinstance(value, memoryview):
            return bytes(value)

        return value

    def transform_row(
        self, row: Dict[str, Any], column_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Transform all values in a row dict."""
        keys = column_names or list(row.keys())
        return {key: self.transform_value(key, row[key]) for key in keys}

    def transform_chunk(
        self,
        rows: List[Dict[str, Any]],
        column_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Transform a batch of rows."""
        return [self.transform_row(row, column_names) for row in rows]
