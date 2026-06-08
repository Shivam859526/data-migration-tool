"""Main application window with screen navigation."""

import sys

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
)

from ui.connection_screen import ConnectionScreen
from ui.migration_screen import MigrationScreen
from ui.report_screen import ReportScreen
from ui.table_selection_screen import TableSelectionScreen
from utils.file_manager import FileManager
from utils.logger import Logger


class MainWindow(QMainWindow):
    """Top-level window hosting all migration screens."""

    SCREEN_CONNECTION = 0
    SCREEN_TABLES = 1
    SCREEN_MIGRATION = 2
    SCREEN_REPORT = 3

    def __init__(self) -> None:
        super().__init__()
        Logger.setup_logger()
        FileManager.create_directories()

        self.setWindowTitle("Database Migration Tool — PostgreSQL → MySQL")
        self.setMinimumSize(900, 650)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.connection_screen = ConnectionScreen()
        self.table_screen = TableSelectionScreen()
        self.migration_screen = MigrationScreen()
        self.report_screen = ReportScreen()

        self.stack.addWidget(self.connection_screen)
        self.stack.addWidget(self.table_screen)
        self.stack.addWidget(self.migration_screen)
        self.stack.addWidget(self.report_screen)

        self.connection_screen.connected.connect(self._on_connected)
        self.table_screen.tables_selected.connect(self._on_tables_selected)
        self.migration_screen.migration_done.connect(self._on_migration_done)
        self.report_screen.back_btn.clicked.connect(self._go_connection)

        self.statusBar().showMessage("Configure database connections to begin")

        self.source_engine = None
        self.target_engine = None

    def _go(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def _go_connection(self) -> None:
        self._go(self.SCREEN_CONNECTION)
        self.statusBar().showMessage("Configure database connections")

    def _on_connected(self, source_engine, target_engine) -> None:
        self.source_engine = source_engine
        self.target_engine = target_engine
        self.table_screen.set_source_engine(source_engine)
        self._go(self.SCREEN_TABLES)
        self.statusBar().showMessage("Select tables to migrate")

    def _on_tables_selected(self, tables, options) -> None:
        self.migration_screen.configure(
            self.source_engine, self.target_engine, tables, options
        )
        self._go(self.SCREEN_MIGRATION)
        self.statusBar().showMessage(f"Ready to migrate {len(tables)} table(s)")

    def _on_migration_done(self, report) -> None:
        self.report_screen.set_report(report)
        self._go(self.SCREEN_REPORT)
        self.statusBar().showMessage("Migration complete — view report")


def run_app() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
