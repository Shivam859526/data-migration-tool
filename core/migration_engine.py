"""Orchestrates schema migration, data transfer, and validation."""

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.constants import (
    BATCH_SIZE,
    MIGRATION_STATUS_COMPLETED,
    MIGRATION_STATUS_FAILED,
    MIGRATION_STATUS_RUNNING,
    MIGRATION_STATUS_STOPPED,
)
from core.bulk_insert_engine import BulkInsertEngine
from core.checkpoint_engine import CheckpointEngine
from core.create_table_engine import CreateTableEngine
from core.dependency_resolver import DependencyResolver
from core.job_manager import JobManager
from core.migration_context import MigrationContext
from core.progress_tracker import ProgressTracker
from core.schema_engine import SchemaEngine
from core.transformation_engine import TransformationEngine
from core.validation_engine import ValidationEngine

ProgressCallback = Callable[[Dict[str, Any]], None]


class MigrationEngine:
    """Full migration pipeline: schema → data → validation."""

    def __init__(
        self,
        source_engine: Engine,
        target_engine: Engine,
        context: Optional[MigrationContext] = None,
        progress_tracker: Optional[ProgressTracker] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        self.source_engine = source_engine
        self.target_engine = target_engine
        self.context = context
        self.progress = progress_tracker or ProgressTracker()
        self.progress_callback = progress_callback
        self.transformer = TransformationEngine()
        self._fk_connection = None
        self._validation_results: List[Dict[str, Any]] = []
        self._table_results: Dict[str, int] = {}

    def _notify(self) -> None:
        if self.progress_callback:
            self.progress_callback(self.progress.get_snapshot())

    def _wait_if_paused(self) -> bool:
        """Block while paused. Returns False if stopped."""
        if not self.context:
            return True
        while self.context.is_paused:
            if self.context.is_stopped:
                return False
            time.sleep(0.5)
        return not self.context.is_stopped

    def _build_result(self, status: str, job_id: str) -> Dict[str, Any]:
        return {
            "status": status,
            "job_id": job_id,
            "tables_migrated": self._table_results,
            "validation_results": self._validation_results,
            "errors": list(self.context.errors) if self.context else [],
        }

    def resolve_table_order(
        self, tables: Optional[List[str]] = None
    ) -> List[str]:
        """Order tables by FK dependencies; auto-include required parents."""
        selected = tables or (
            self.context.tables if self.context else SchemaEngine.get_tables(self.source_engine)
        )
        ordered, auto_added = DependencyResolver.expand_with_dependencies(
            self.source_engine, selected
        )
        if auto_added and self.context:
            self.context.auto_added_tables = auto_added

        if self.context:
            self.context.tables = ordered
        return ordered

    def migrate_schema(
        self,
        tables: Optional[List[str]] = None,
        skip_existing: bool = True,
    ) -> List[str]:
        """Create target tables in dependency order with deferred FK constraints."""
        table_list = self.resolve_table_order(tables)
        metadata_list = [
            SchemaEngine.get_table_metadata(self.source_engine, t) for t in table_list
        ]

        try:
            created = CreateTableEngine.migrate_schema_batch(
                self.target_engine,
                metadata_list,
                skip_existing=skip_existing,
            )
            self._notify()
            return created
        except Exception as exc:
            if self.context:
                self.context.errors.append({"phase": "schema", "error": str(exc)})
            raise

    def _get_order_columns(self, table_name: str) -> List[str]:
        pk = SchemaEngine.get_primary_key(self.source_engine, table_name)
        pk_cols = pk.get("constrained_columns", [])
        if pk_cols:
            return pk_cols
        columns = SchemaEngine.get_columns(self.source_engine, table_name)
        return [columns[0]["name"]] if columns else []

    def _extract_last_key(
        self, row: Dict[str, Any], order_columns: List[str]
    ) -> Tuple[Any, ...]:
        return tuple(row[col] for col in order_columns)

    def _fetch_chunk_offset(
        self,
        table_name: str,
        order_columns: List[str],
        offset: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Legacy OFFSET pagination for resuming old checkpoints."""
        order_clause = ", ".join(f'"{c}"' for c in order_columns)
        query = text(
            f'SELECT * FROM "{table_name}" '
            f"ORDER BY {order_clause} "
            f"LIMIT :limit OFFSET :offset"
        )
        with self.source_engine.connect() as conn:
            result = conn.execute(query, {"limit": limit, "offset": offset})
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def _fetch_chunk_keyset(
        self,
        table_name: str,
        order_columns: List[str],
        last_key: Optional[Tuple[Any, ...]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Fetch rows using keyset pagination (faster and safer than OFFSET)."""
        quoted_cols = ", ".join(f'"{c}"' for c in order_columns)
        order_clause = quoted_cols

        if last_key is None:
            query = text(
                f'SELECT * FROM "{table_name}" '
                f"ORDER BY {order_clause} "
                f"LIMIT :limit"
            )
            params: Dict[str, Any] = {"limit": limit}
        else:
            placeholders = ", ".join(f":k{i}" for i in range(len(order_columns)))
            query = text(
                f'SELECT * FROM "{table_name}" '
                f"WHERE ({order_clause}) > ({placeholders}) "
                f"ORDER BY {order_clause} "
                f"LIMIT :limit"
            )
            params = {f"k{i}": last_key[i] for i in range(len(order_columns))}
            params["limit"] = limit

        with self.source_engine.connect() as conn:
            result = conn.execute(query, params)
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def _verify_table_row_count(self, table_name: str, expected: int) -> None:
        """Ensure no rows were lost during migration of a single table."""
        target_count = ValidationEngine.get_row_count(
            self.target_engine, table_name, "mysql"
        )
        if target_count != expected:
            raise RuntimeError(
                f"Data loss detected in {table_name}: "
                f"source={expected}, target={target_count}"
            )

    def migrate_table_data(
        self,
        table_name: str,
        job_id: str,
        batch_size: int,
        resume: bool = True,
    ) -> int:
        """Migrate a single table in keyset-ordered chunks. Returns total rows migrated."""
        order_columns = self._get_order_columns(table_name)
        if not order_columns:
            raise RuntimeError(f"Cannot determine ordering columns for {table_name}")

        source_row_count = ValidationEngine.get_row_count(
            self.source_engine, table_name, "postgres"
        )

        checkpoint = CheckpointEngine.load_checkpoint(job_id, table_name) if resume else None
        total_migrated = int(checkpoint.get("offset", 0)) if checkpoint else 0
        last_key: Optional[Tuple[Any, ...]] = None
        if checkpoint and checkpoint.get("last_key"):
            last_key = tuple(checkpoint["last_key"])
        batch_number = int(checkpoint.get("batch_number", 0)) if checkpoint else 0

        self.progress.set_current_table(table_name, source_row_count)

        column_names = [
            c["name"] for c in SchemaEngine.get_columns(self.source_engine, table_name)
        ]

        use_legacy_offset = resume and total_migrated > 0 and last_key is None

        while True:
            if not self._wait_if_paused():
                break

            if use_legacy_offset:
                rows = self._fetch_chunk_offset(
                    table_name, order_columns, total_migrated, batch_size
                )
                use_legacy_offset = False
            else:
                rows = self._fetch_chunk_keyset(
                    table_name, order_columns, last_key, batch_size
                )
            if not rows:
                break

            transformed = self.transformer.transform_chunk(rows, column_names)
            inserted = BulkInsertEngine.insert_batch(
                self.target_engine,
                table_name,
                transformed,
                connection=self._fk_connection,
            )

            total_migrated += inserted
            batch_number += 1
            last_key = self._extract_last_key(rows[-1], order_columns)

            CheckpointEngine.save_checkpoint(
                job_id,
                table_name,
                total_migrated,
                batch_number,
                last_key=list(last_key),
            )

            self.progress.update(inserted)
            self._notify()

            if self.context:
                self.context.current_batch = batch_number
                self.context.migrated_rows = total_migrated

        self._verify_table_row_count(table_name, source_row_count)

        self.progress.complete_table()
        return total_migrated

    def migrate_data(
        self,
        tables: Optional[List[str]] = None,
        job_id: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> Dict[str, int]:
        """Migrate data in FK-safe order with deferred FK checks during load."""
        table_list = self.resolve_table_order(tables)
        jid = job_id or (self.context.job_id if self.context else "default")
        size = batch_size or (self.context.batch_size if self.context else BATCH_SIZE)

        self.progress.set_total_tables(len(table_list))
        results: Dict[str, int] = {}

        with BulkInsertEngine.foreign_key_session(
            self.target_engine, enabled=False
        ) as fk_conn:
            self._fk_connection = fk_conn
            try:
                for table in table_list:
                    if not self._wait_if_paused():
                        break
                    try:
                        count = self.migrate_table_data(table, jid, size)
                        results[table] = count
                        self._table_results[table] = count
                        JobManager.mark_table_complete(jid, table)
                    except Exception as exc:
                        JobManager.mark_table_failed(jid, table, str(exc))
                        if self.context:
                            self.context.errors.append({
                                "table": table,
                                "phase": "data",
                                "error": str(exc),
                            })
                        raise
            finally:
                self._fk_connection = None

        self._notify()
        return results

    def validate(
        self,
        tables: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Validate migrated tables."""
        table_list = self.resolve_table_order(tables)
        results: List[Dict[str, Any]] = []

        for table in table_list:
            columns = [
                c["name"]
                for c in SchemaEngine.get_columns(self.source_engine, table)
            ]
            result = ValidationEngine.validate_table(
                self.source_engine,
                self.target_engine,
                table,
                columns,
            )
            results.append(result)

        self._validation_results = results
        self._notify()
        return results

    def run_full_migration(
        self,
        tables: Optional[List[str]] = None,
        migrate_schema: bool = True,
        migrate_data: bool = True,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Execute the complete migration pipeline."""
        table_list = self.resolve_table_order(tables)
        job_id = self.context.job_id if self.context else "default"

        JobManager.update_status(job_id, MIGRATION_STATUS_RUNNING)

        try:
            if migrate_schema:
                self.migrate_schema(
                    table_list,
                    skip_existing=self.context.skip_existing_tables if self.context else True,
                )

            if self.context and self.context.is_stopped:
                return self._build_result(MIGRATION_STATUS_STOPPED, job_id)

            if migrate_data:
                self.migrate_data(table_list, job_id)

            if self.context and self.context.is_stopped:
                return self._build_result(MIGRATION_STATUS_STOPPED, job_id)

            if validate and (not self.context or self.context.validate_after_migration):
                self.validate(table_list)

            status = MIGRATION_STATUS_COMPLETED
            if self.context and self.context.errors:
                status = MIGRATION_STATUS_FAILED

            return self._build_result(status, job_id)

        except Exception as exc:
            JobManager.update_status(job_id, MIGRATION_STATUS_FAILED)
            if self.context:
                self.context.errors.append({"phase": "global", "error": str(exc)})
            return self._build_result(MIGRATION_STATUS_FAILED, job_id)
