"""Background worker thread for non-blocking migrations."""

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from core.job_manager import JobManager
from core.migration_context import MigrationContext
from core.migration_engine import MigrationEngine
from core.progress_tracker import ProgressTracker
from sqlalchemy.engine import Engine


class MigrationWorker(QThread):
    """Runs migration pipeline in a background thread."""

    progress_updated = pyqtSignal(dict)
    migration_finished = pyqtSignal(dict)
    migration_error = pyqtSignal(str)

    def __init__(
        self,
        source_engine: Engine,
        target_engine: Engine,
        tables: List[str],
        batch_size: int = 50000,
        skip_existing: bool = True,
        validate: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.source_engine = source_engine
        self.target_engine = target_engine
        self.tables = tables
        self.batch_size = batch_size
        self.skip_existing = skip_existing
        self.validate = validate
        self._context: Optional[MigrationContext] = None
        self._tracker = ProgressTracker()

    @property
    def context(self) -> Optional[MigrationContext]:
        return self._context

    def _on_progress(self, snapshot: Dict[str, Any]) -> None:
        self.progress_updated.emit(snapshot)

    def pause(self) -> None:
        if self._context:
            self._context.pause()

    def resume(self) -> None:
        if self._context:
            self._context.resume()

    def stop(self) -> None:
        if self._context:
            self._context.stop()

    def run(self) -> None:
        try:
            job = JobManager.create_job(self.tables)
            self._context = MigrationContext(
                source_engine=self.source_engine,
                target_engine=self.target_engine,
                job_id=job["job_id"],
                tables=self.tables,
                batch_size=self.batch_size,
                skip_existing_tables=self.skip_existing,
                validate_after_migration=self.validate,
            )

            engine = MigrationEngine(
                source_engine=self.source_engine,
                target_engine=self.target_engine,
                context=self._context,
                progress_tracker=self._tracker,
                progress_callback=self._on_progress,
            )

            result = engine.run_full_migration(
                tables=self.tables,
                migrate_schema=True,
                migrate_data=True,
                validate=self.validate,
            )
            self.migration_finished.emit(result)

        except Exception as exc:
            self.migration_error.emit(str(exc))
