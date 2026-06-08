"""Migration report display and export screen."""

import os
import subprocess
import sys
from typing import Any, Dict, Optional

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ReportScreen(QWidget):
    """Displays migration summary and allows report export."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._report: Optional[Dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Migration Report</h2>"))

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        layout.addWidget(self.summary_text)

        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export Report")
        self.open_btn = QPushButton("Open Report Folder")
        self.back_btn = QPushButton("New Migration")

        self.export_btn.clicked.connect(self._export_report)
        self.open_btn.clicked.connect(self._open_folder)

        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.back_btn)
        layout.addLayout(btn_layout)

    def set_report(self, report: Dict[str, Any]) -> None:
        self._report = report
        self._display_summary()

    def _display_summary(self) -> None:
        if not self._report:
            self.summary_text.setPlainText("No report available.")
            return

        lines = [
            f"Job ID:       {self._report.get('job_id', '—')}",
            f"Status:       {self._report.get('status', '—')}",
            f"Start Time:   {self._report.get('start_time', '—')}",
            f"End Time:     {self._report.get('end_time', '—')}",
            f"Duration:     {self._report.get('duration_seconds', 0):.1f}s",
            f"Rows Migrated: {self._report.get('total_rows_migrated', 0)}",
            f"Failures:     {len(self._report.get('failures', []))}",
            "",
            "— Tables —",
        ]

        for entry in self._report.get("tables_migrated", []):
            lines.append(
                f"  {entry.get('table')}: {entry.get('rows_migrated')} rows "
                f"[{entry.get('status')}]"
            )

        validation = self._report.get("validation_results", [])
        if validation:
            lines.append("")
            lines.append("— Validation —")
            for vr in validation:
                lines.append(
                    f"  {vr.get('table')}: {vr.get('source_rows')} → "
                    f"{vr.get('target_rows')} [{vr.get('status')}]"
                )

        paths = self._report.get("report_paths", {})
        if paths:
            lines.append("")
            lines.append("— Report Files —")
            for fmt, path in paths.items():
                lines.append(f"  {fmt}: {path}")

        self.summary_text.setPlainText("\n".join(lines))

    def _export_report(self) -> None:
        if not self._report:
            QMessageBox.information(self, "Info", "No report to export")
            return
        paths = self._report.get("report_paths", {})
        if paths:
            QMessageBox.information(
                self, "Exported", "\n".join(f"{k}: {v}" for k, v in paths.items())
            )
        else:
            QMessageBox.information(self, "Info", "Report already exported during migration")

    def _open_folder(self) -> None:
        folder = os.path.abspath("reports")
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
