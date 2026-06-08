"""Database connection configuration screen."""

from typing import Any, Dict, Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.connection_manager import ConnectionManager
from sqlalchemy.engine import Engine


class ConnectionScreen(QWidget):
    """Source and target database connection form."""

    connected = pyqtSignal(object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.source_engine: Optional[Engine] = None
        self.target_engine: Optional[Engine] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Database Connections</h2>"))

        self.source_fields = self._create_db_group("PostgreSQL Source", layout)
        self.target_fields = self._create_db_group("MySQL Target", layout)

        btn_layout = QHBoxLayout()
        self.test_source_btn = QPushButton("Test Source")
        self.test_target_btn = QPushButton("Test Target")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setStyleSheet("font-weight: bold; padding: 8px;")

        self.test_source_btn.clicked.connect(lambda: self._test_connection("source"))
        self.test_target_btn.clicked.connect(lambda: self._test_connection("target"))
        self.connect_btn.clicked.connect(self._connect)

        btn_layout.addWidget(self.test_source_btn)
        btn_layout.addWidget(self.test_target_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.connect_btn)
        layout.addLayout(btn_layout)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _create_db_group(self, title: str, parent_layout: QVBoxLayout) -> Dict[str, QLineEdit]:
        group = QGroupBox(title)
        form = QFormLayout(group)
        fields: Dict[str, QLineEdit] = {}

        defaults = {
            "host": "localhost",
            "port": "5432" if "PostgreSQL" in title else "3306",
            "database": "migration_demo",
            "username": "postgres" if "PostgreSQL" in title else "root",
            "password": "",
        }

        for key, default in defaults.items():
            field = QLineEdit(default)
            if key == "password":
                field.setEchoMode(QLineEdit.Password)
            form.addRow(key.capitalize(), field)
            fields[key] = field

        parent_layout.addWidget(group)
        return fields

    def _get_config(self, fields: Dict[str, QLineEdit]) -> Dict[str, Any]:
        return {
            "host": fields["host"].text().strip(),
            "port": int(fields["port"].text().strip()),
            "database": fields["database"].text().strip(),
            "username": fields["username"].text().strip(),
            "password": fields["password"].text(),
        }

    def _test_connection(self, which: str) -> None:
        fields = self.source_fields if which == "source" else self.target_fields
        config = self._get_config(fields)

        try:
            if which == "source":
                engine = ConnectionManager.get_postgres_engine(config)
            else:
                engine = ConnectionManager.get_mysql_engine(config)

            if ConnectionManager.test_connection(engine):
                QMessageBox.information(self, "Success", f"{which.title()} connection OK")
            else:
                QMessageBox.warning(self, "Failed", f"{which.title()} connection failed")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _connect(self) -> None:
        try:
            source_config = self._get_config(self.source_fields)
            target_config = self._get_config(self.target_fields)

            self.source_engine = ConnectionManager.get_postgres_engine(source_config)
            self.target_engine = ConnectionManager.get_mysql_engine(target_config)

            source_ok = ConnectionManager.test_connection(self.source_engine)
            target_ok = ConnectionManager.test_connection(self.target_engine)

            if not source_ok or not target_ok:
                QMessageBox.warning(self, "Failed", "One or both connections failed")
                return

            self.status_label.setText("Connected to both databases")
            self.connected.emit(self.source_engine, self.target_engine)

        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
