"""High-performance bulk insert engine with transaction support."""

import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from config.constants import CONNECTION_RETRY_ATTEMPTS, CONNECTION_RETRY_DELAY


class BulkInsertEngine:
    """Performs batch inserts into MySQL with retry and rollback."""

    @staticmethod
    def _quote_identifier(name: str) -> str:
        return f"`{name.replace('`', '``')}`"

    @classmethod
    @contextmanager
    def foreign_key_session(
        cls, engine: Engine, enabled: bool = False
    ) -> Generator[Connection, None, None]:
        """
        Control MySQL FOREIGN_KEY_CHECKS for the duration of data loading.

        Disabled during bulk load to safely handle self-references and cycles;
        re-enabled afterward so integrity is enforced going forward.
        """
        with engine.connect() as conn:
            conn.execute(
                text(f"SET FOREIGN_KEY_CHECKS={1 if enabled else 0}")
            )
            conn.commit()
            try:
                yield conn
            finally:
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
                conn.commit()

    @classmethod
    def insert_batch(
        cls,
        engine: Engine,
        table_name: str,
        rows: List[Dict[str, Any]],
        retries: int = CONNECTION_RETRY_ATTEMPTS,
        connection: Optional[Connection] = None,
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
                if connection is not None:
                    connection.execute(text(sql), rows)
                    connection.commit()
                else:
                    with engine.begin() as conn:
                        conn.execute(text(sql), rows)
                return len(rows)
            except SQLAlchemyError as exc:
                last_error = exc
                if connection is not None:
                    connection.rollback()
                if attempt < retries:
                    time.sleep(CONNECTION_RETRY_DELAY)

        raise RuntimeError(
            f"Batch insert failed for {table_name} after {retries} attempts: {last_error}"
        )
