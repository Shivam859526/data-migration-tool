"""Shared state for an active migration run."""

from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Engine

from config.constants import BATCH_SIZE


class MigrationContext:
    """Holds engines, options, and runtime state for a migration job."""

    def __init__(
        self,
        source_engine: Engine,
        target_engine: Engine,
        job_id: str,
        tables: Optional[List[str]] = None,
        batch_size: int = BATCH_SIZE,
        skip_existing_tables: bool = True,
        validate_after_migration: bool = True,
    ) -> None:
        self.source_engine = source_engine
        self.target_engine = target_engine
        self.job_id = job_id
        self.tables = tables or []
        self.batch_size = batch_size
        self.skip_existing_tables = skip_existing_tables
        self.validate_after_migration = validate_after_migration

        self.current_table: Optional[str] = None
        self.current_batch: int = 0
        self.total_rows: int = 0
        self.migrated_rows: int = 0
        self.is_paused: bool = False
        self.is_stopped: bool = False
        self.errors: List[Dict[str, Any]] = []
        self.auto_added_tables: List[str] = []

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def stop(self) -> None:
        self.is_stopped = True
        self.is_paused = False
