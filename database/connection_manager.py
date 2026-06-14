"""Database connection factory with pooling, retry, and health checks."""

import time
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config.constants import (
    CONNECTION_MAX_OVERFLOW,
    CONNECTION_POOL_SIZE,
    CONNECTION_RETRY_ATTEMPTS,
    CONNECTION_RETRY_DELAY,
)


class ConnectionManager:
    """Creates and manages SQLAlchemy engines for PostgreSQL and MySQL."""

    _engines: Dict[str, Engine] = {}

    @classmethod
    def _build_engine(cls, url: str, key: str) -> Engine:
        """Create a pooled engine and cache it by key."""
        if key in cls._engines:
            return cls._engines[key]

        engine = create_engine(
            url,
            pool_size=CONNECTION_POOL_SIZE,
            max_overflow=CONNECTION_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        cls._engines[key] = engine
        return engine

    @staticmethod
    def get_postgres_engine(config: Dict[str, Any]) -> Engine:
        """Build a PostgreSQL engine from a config dict."""
        url = (
            f"postgresql+psycopg2://"
            f"{config['username']}:{config['password']}@"
            f"{config['host']}:{config['port']}/{config['database']}"
        )
        key = f"postgres:{config['host']}:{config['port']}:{config['database']}"
        return ConnectionManager._build_engine(url, key)

    @staticmethod
    def get_mysql_engine(config: Dict[str, Any]) -> Engine:
        """Build a MySQL engine from a config dict."""
        password = quote_plus(config["password"])
        url = (
            f"mysql+pymysql://"
            f"{config['username']}:{password}@"
            f"{config['host']}:{config['port']}/{config['database']}"
            f"?charset=utf8mb4"
        )
        key = f"mysql:{config['host']}:{config['port']}:{config['database']}"
        return ConnectionManager._build_engine(url, key)

    @classmethod
    def test_connection(
        cls,
        engine: Engine,
        retries: int = CONNECTION_RETRY_ATTEMPTS,
        delay: float = CONNECTION_RETRY_DELAY,
    ) -> bool:
        """Verify connectivity with retry support."""
        last_error: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            except SQLAlchemyError as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(delay)

        return False

    @classmethod
    def close_engine(cls, engine: Engine) -> None:
        """Dispose of a single engine and remove it from cache."""
        engine.dispose()
        keys_to_remove = [k for k, v in cls._engines.items() if v is engine]
        for key in keys_to_remove:
            del cls._engines[key]

    @classmethod
    def close_all(cls) -> None:
        """Dispose of all cached engines."""
        for engine in list(cls._engines.values()):
            engine.dispose()
        cls._engines.clear()
