"""Orchestrates schema migration, data transfer, validation, and reporting."""

import time
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.constants import (
    MIGRATION_STATUS_COMPLETED,
    MIGRATION_STATUS_FAILED,
    MIGRATION_STATUS_RUNNING,
    MIGRATION_STATUS_STOPPED,
)
from core.bulk_insert_engine import BulkInsertEngine
from core.checkpoint_engine import CheckpointEngine
from core.create_table_engine import CreateTableEngine
from core.job_manager import JobManager
from core.migration_context import MigrationContext
from core.progress_tracker import ProgressTracker
from core.report_engine import ReportEngine
from core.schema_engine import SchemaEngine
from core.transformation_engine import TransformationEngine
from core.validation_engine import ValidationEngine
from utils.logger import Logger

logger = Logger.get_logger("migration")

ProgressCallback = Callable[[Dict[str, Any]], None]


class MigrationEngine:
    """Full migration pipeline: schema → data → validation → report."""

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
        self.report = ReportEngine()

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

    def migrate_schema(
        self,
        tables: Optional[List[str]] = None,
        skip_existing: bool = True,
    ) -> List[str]:
        """Create target tables from source metadata."""
        table_list = tables or SchemaEngine.get_tables(self.source_engine)
        created: List[str] = []

        for table in table_list:
            if not self._wait_if_paused():
                break

            metadata = SchemaEngine.get_table_metadata(self.source_engine, table)
            try:
                if CreateTableEngine.create_table_from_metadata(
                    self.target_engine,
                    metadata,
                    skip_existing=skip_existing,
                ):
                    created.append(table)
                self.progress.add_message(f"Schema ready: {table}")
                logger.info("Schema migrated for table %s", table)
            except Exception as exc:
                logger.error("Schema migration failed for %s: %s", table, exc)
                if self.context:
                    self.context.errors.append({"table": table, "phase": "schema", "error": str(exc)})
                raise

        self._notify()
        return created

    def _get_order_columns(self, table_name: str) -> List[str]:
        pk = SchemaEngine.get_primary_key(self.source_engine, table_name)
        pk_cols = pk.get("constrained_columns", [])
        if pk_cols:
            return pk_cols
        columns = SchemaEngine.get_columns(self.source_engine, table_name)
        return [columns[0]["name"]] if columns else []

    def _fetch_chunk(
        self,
        table_name: str,
        order_columns: List[str],
        offset: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
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

    def migrate_table_data(
        self,
        table_name: str,
        job_id: str,
        batch_size: int,
        resume: bool = True,
    ) -> int:
        """Migrate a single table in chunks. Returns total rows migrated."""
        order_columns = self._get_order_columns(table_name)
        offset = (
            CheckpointEngine.get_table_offset(job_id, table_name) if resume else 0
        )
        total_migrated = offset
        batch_number = offset // batch_size if batch_size else 0

        row_count = ValidationEngine.get_row_count(
            self.source_engine, table_name, "postgres"
        )
        self.progress.set_current_table(table_name, row_count)
        self.progress.add_message(f"Migrating {table_name} ({row_count} rows)")

        column_names = [c["name"] for c in SchemaEngine.get_columns(self.source_engine, table_name)]

        while True:
            if not self._wait_if_paused():
                break

            rows = self._fetch_chunk(table_name, order_columns, offset, batch_size)
            if not rows:
                break

            transformed = self.transformer.transform_chunk(rows, column_names)
            inserted = BulkInsertEngine.insert_batch(
                self.target_engine, table_name, transformed
            )

            offset += inserted
            total_migrated += inserted
            batch_number += 1

            CheckpointEngine.save_checkpoint(
                job_id, table_name, offset, batch_number
            )

            self.progress.update(inserted)
            self._notify()

            if self.context:
                self.context.current_batch = batch_number
                self.context.migrated_rows = total_migrated

        self.progress.complete_table()
        self.progress.add_message(f"Completed {table_name}: {total_migrated} rows")
        logger.info("Data migration complete for %s: %d rows", table_name, total_migrated)
        return total_migrated

    def migrate_data(
        self,
        tables: Optional[List[str]] = None,
        job_id: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> Dict[str, int]:
        """Migrate data for all specified tables."""
        table_list = tables or (self.context.tables if self.context else SchemaEngine.get_tables(self.source_engine))
        jid = job_id or (self.context.job_id if self.context else "default")
        size = batch_size or (self.context.batch_size if self.context else 5000)

        self.progress.set_total_tables(len(table_list))
        results: Dict[str, int] = {}

        for table in table_list:
            if not self._wait_if_paused():
                break
            try:
                count = self.migrate_table_data(table, jid, size)
                results[table] = count
                JobManager.mark_table_complete(jid, table)
                self.report.record_table(table, count)
            except Exception as exc:
                logger.error("Data migration failed for %s: %s", table, exc)
                JobManager.mark_table_failed(jid, table, str(exc))
                self.report.record_table(table, 0, status="FAILED", error=str(exc))
                if self.context:
                    self.context.errors.append({"table": table, "phase": "data", "error": str(exc)})

        self._notify()
        return results

    def validate(
        self,
        tables: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Validate migrated tables."""
        table_list = tables or (self.context.tables if self.context else SchemaEngine.get_tables(self.source_engine))
        results: List[Dict[str, Any]] = []

        for table in table_list:
            columns = [c["name"] for c in SchemaEngine.get_columns(self.source_engine, table)]
            result = ValidationEngine.validate_table(
                self.source_engine,
                self.target_engine,
                table,
                columns,
            )
            results.append(result)
            self.report.record_validation(result)
            self.progress.add_message(
                f"Validation {result['status']}: {table}"
            )

        self._notify()
        return results

    def generate_report(self, status: str = MIGRATION_STATUS_COMPLETED) -> Dict[str, Any]:
        """Finalize and export reports."""
        report_data = self.report.finish(status)
        paths = self.report.export_all()
        report_data["report_paths"] = paths
        logger.info("Report generated: %s", paths)
        return report_data

    def run_full_migration(
        self,
        tables: Optional[List[str]] = None,
        migrate_schema: bool = True,
        migrate_data: bool = True,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Execute the complete migration pipeline."""
        table_list = tables or (self.context.tables if self.context else [])
        job_id = self.context.job_id if self.context else "default"

        self.report.start(job_id)
        JobManager.update_status(job_id, MIGRATION_STATUS_RUNNING)

        try:
            if migrate_schema:
                self.progress.add_message("Starting schema migration...")
                self.migrate_schema(table_list, skip_existing=self.context.skip_existing_tables if self.context else True)

            if self.context and self.context.is_stopped:
                return self.generate_report(MIGRATION_STATUS_STOPPED)

            if migrate_data:
                self.progress.add_message("Starting data migration...")
                self.migrate_data(table_list, job_id)

            if self.context and self.context.is_stopped:
                return self.generate_report(MIGRATION_STATUS_STOPPED)

            if validate and (not self.context or self.context.validate_after_migration):
                self.progress.add_message("Starting validation...")
                self.validate(table_list)

            status = MIGRATION_STATUS_COMPLETED
            if self.context and self.context.errors:
                status = MIGRATION_STATUS_FAILED

            return self.generate_report(status)

        except Exception as exc:
            logger.error("Migration failed: %s", exc)
            JobManager.update_status(job_id, MIGRATION_STATUS_FAILED)
            self.report.record_table("_global_", 0, status="FAILED", error=str(exc))
            return self.generate_report(MIGRATION_STATUS_FAILED)
