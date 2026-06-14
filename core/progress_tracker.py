"""Thread-safe migration progress tracking."""

import threading
import time
from typing import Any, Dict, Optional


class ProgressTracker:
    """Tracks migration progress with thread-safe updates."""

    def __init__(self, total_rows: int = 0) -> None:
        self._lock = threading.Lock()
        self.total_rows = total_rows
        self.current_rows = 0
        self.current_table: Optional[str] = None
        self.tables_completed = 0
        self.total_tables = 0
        self.start_time = time.time()

    def set_total_tables(self, count: int) -> None:
        with self._lock:
            self.total_tables = count

    def set_current_table(self, table_name: str, total_rows: int) -> None:
        with self._lock:
            self.current_table = table_name
            self.total_rows = total_rows
            self.current_rows = 0

    def update(self, rows_processed: int) -> float:
        with self._lock:
            self.current_rows += rows_processed
            if self.total_rows <= 0:
                return 0.0
            return round((self.current_rows / self.total_rows) * 100, 2)

    def complete_table(self) -> None:
        with self._lock:
            self.tables_completed += 1

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            elapsed = time.time() - self.start_time
            table_progress = 0.0
            if self.total_rows > 0:
                table_progress = round(
                    (self.current_rows / self.total_rows) * 100, 2
                )
            overall = 0.0
            if self.total_tables > 0:
                overall = round(
                    ((self.tables_completed + table_progress / 100) / self.total_tables) * 100,
                    2,
                )
            return {
                "current_table": self.current_table,
                "rows_processed": self.current_rows,
                "total_rows": self.total_rows,
                "table_progress": table_progress,
                "tables_completed": self.tables_completed,
                "total_tables": self.total_tables,
                "overall_progress": overall,
                "elapsed_seconds": round(elapsed, 1),
            }
