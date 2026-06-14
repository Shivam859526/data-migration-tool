"""Migration progress and control screen."""

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.migration_worker import MigrationWorker
from sqlalchemy.engine import Engine


class MigrationScreen(QWidget):
    """Controls migration execution and displays progress."""

    migration_done = pyqtSignal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.source_engine: Optional[Engine] = None
        self.target_engine: Optional[Engine] = None
        self.tables: List[str] = []
        self.options: Dict[str, Any] = {}
        self.worker: Optional[MigrationWorker] = None
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_elapsed)
        self._elapsed_seconds = 0

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Migration Progress</h2>"))

        info_layout = QHBoxLayout()
        self.current_table_label = QLabel("Current table: —")
        self.rows_label = QLabel("Rows: 0 / 0")
        self.elapsed_label = QLabel("Elapsed: 0s")
        self.status_label = QLabel("Status: Ready")
        info_layout.addWidget(self.current_table_label)
        info_layout.addWidget(self.rows_label)
        info_layout.addStretch()
        info_layout.addWidget(self.elapsed_label)
        layout.addLayout(info_layout)
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Overall Progress"))
        self.overall_progress = QProgressBar()
        layout.addWidget(self.overall_progress)

        layout.addWidget(QLabel("Table Progress"))
        self.table_progress = QProgressBar()
        layout.addWidget(self.table_progress)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.resume_btn = QPushButton("Resume")
        self.stop_btn = QPushButton("Stop")

        self.start_btn.clicked.connect(self._start)
        self.pause_btn.clicked.connect(self._pause)
        self.resume_btn.clicked.connect(self._resume)
        self.stop_btn.clicked.connect(self._stop)

        for btn in (self.start_btn, self.pause_btn, self.resume_btn, self.stop_btn):
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addStretch()

        self._set_running_state(False)

    def configure(
        self,
        source_engine: Engine,
        target_engine: Engine,
        tables: List[str],
        options: Dict[str, Any],
    ) -> None:
        self.source_engine = source_engine
        self.target_engine = target_engine
        self.tables = tables
        self.options = options
        self.status_label.setText(f"Status: Ready — {len(tables)} table(s) selected")

    def _set_running_state(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.resume_btn.setEnabled(running)
        self.stop_btn.setEnabled(running)

    def _start(self) -> None:
        if not self.source_engine or not self.target_engine:
            return

        self.worker = MigrationWorker(
            source_engine=self.source_engine,
            target_engine=self.target_engine,
            tables=self.tables,
            batch_size=self.options.get("batch_size", 50000),
            skip_existing=self.options.get("skip_existing", True),
            validate=self.options.get("validate", True),
        )
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.migration_finished.connect(self._on_finished)
        self.worker.migration_error.connect(self._on_error)

        self._elapsed_seconds = 0
        self._timer.start(1000)
        self._set_running_state(True)
        self.status_label.setText("Status: Running")
        self.worker.start()

    def _pause(self) -> None:
        if self.worker:
            self.worker.pause()
            self.status_label.setText("Status: Paused")

    def _resume(self) -> None:
        if self.worker:
            self.worker.resume()
            self.status_label.setText("Status: Running")

    def _stop(self) -> None:
        if self.worker:
            self.worker.stop()
            self.status_label.setText("Status: Stopping...")

    def _on_progress(self, snapshot: Dict[str, Any]) -> None:
        self.current_table_label.setText(
            f"Current table: {snapshot.get('current_table', '—')}"
        )
        self.rows_label.setText(
            f"Rows: {snapshot.get('rows_processed', 0):,} / {snapshot.get('total_rows', 0):,}"
        )
        self.overall_progress.setValue(int(snapshot.get("overall_progress", 0)))
        self.table_progress.setValue(int(snapshot.get("table_progress", 0)))

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        self.elapsed_label.setText(f"Elapsed: {self._elapsed_seconds}s")

    def _on_finished(self, result: Dict[str, Any]) -> None:
        self._timer.stop()
        self._set_running_state(False)
        self.status_label.setText(f"Status: {result.get('status', 'unknown')}")
        self.migration_done.emit(result)

    def _on_error(self, error: str) -> None:
        self._timer.stop()
        self._set_running_state(False)
        self.status_label.setText(f"Status: Failed — {error}")
