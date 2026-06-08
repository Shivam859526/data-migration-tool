"""High-performance bulk insert engine with transaction support."""

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config.constants import CONNECTION_RETRY_ATTEMPTS, CONNECTION_RETRY_DELAY
from utils.logger import Logger

logger = Logger.get_logger("bulk_insert")


class BulkInsertEngine:
    """Performs batch inserts into MySQL with retry and rollback."""

    @staticmethod
    def _quote_identifier(name: str) -> str:
        return f"`{name.replace('`', '``')}`"

    @classmethod
    def insert_batch(
        cls,
        engine: Engine,
        table_name: str,
        rows: List[Dict[str, Any]],
        retries: int = CONNECTION_RETRY_ATTEMPTS,
    ) -> int:
        """Insert a batch of rows. Returns number of rows inserted."""
        if not rows:
            return 0

        columns = list(rows[0].keys())
        col_list = ", ".join(cls._quote_identifier(c) for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        sql = (
            f"INSERT INTO {cls._quote_identifier(table_name)} "
            f"({col_list}) VALUES ({placeholders})"
        )

        last_error: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql), rows)
                logger.debug(
                    "Inserted %d rows into %s", len(rows), table_name
                )
                return len(rows)
            except SQLAlchemyError as exc:
                last_error = exc
                logger.warning(
                    "Batch insert failed (attempt %d/%d) for %s: %s",
                    attempt,
                    retries,
                    table_name,
                    exc,
                )
                if attempt < retries:
                    time.sleep(CONNECTION_RETRY_DELAY)

        raise RuntimeError(
            f"Batch insert failed for {table_name} after {retries} attempts: {last_error}"
        )
