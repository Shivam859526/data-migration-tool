"""Table selection and migration options screen."""

from typing import List, Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.schema_engine import SchemaEngine
from sqlalchemy.engine import Engine


class TableSelectionScreen(QWidget):
    """Select tables to migrate and configure options."""

    tables_selected = pyqtSignal(list, dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.source_engine: Optional[Engine] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Table Selection</h2>"))

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter tables...")
        self.search_input.textChanged.connect(self._filter_tables)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.deselect_all_btn = QPushButton("Deselect All")
        self.refresh_btn = QPushButton("Refresh")
        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        self.refresh_btn.clicked.connect(self._load_tables)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.deselect_all_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table_list = QListWidget()
        layout.addWidget(self.table_list)

        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Batch Size:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(100, 100000)
        self.batch_size_spin.setValue(50000)
        self.batch_size_spin.setSingleStep(5000)
        options_layout.addWidget(self.batch_size_spin)

        self.skip_existing_cb = QCheckBox("Skip existing tables")
        self.skip_existing_cb.setChecked(True)
        options_layout.addWidget(self.skip_existing_cb)

        self.validate_cb = QCheckBox("Validate after migration")
        self.validate_cb.setChecked(True)
        options_layout.addWidget(self.validate_cb)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        self.continue_btn = QPushButton("Continue to Migration")
        self.continue_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        self.continue_btn.clicked.connect(self._on_continue)
        layout.addWidget(self.continue_btn)

    def set_source_engine(self, engine: Engine) -> None:
        self.source_engine = engine
        self._load_tables()

    def _load_tables(self) -> None:
        self.table_list.clear()
        if not self.source_engine:
            return

        tables = SchemaEngine.get_tables(self.source_engine)
        for table in sorted(tables):
            item = QListWidgetItem(table)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.table_list.addItem(item)

    def _filter_tables(self, text: str) -> None:
        text = text.lower()
        for i in range(self.table_list.count()):
            item = self.table_list.item(i)
            item.setHidden(text not in item.text().lower())

    def _select_all(self) -> None:
        for i in range(self.table_list.count()):
            item = self.table_list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def _deselect_all(self) -> None:
        for i in range(self.table_list.count()):
            item = self.table_list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Unchecked)

    def _get_selected_tables(self) -> List[str]:
        selected = []
        for i in range(self.table_list.count()):
            item = self.table_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected

    def _on_continue(self) -> None:
        tables = self._get_selected_tables()
        if not tables:
            return

        options = {
            "batch_size": self.batch_size_spin.value(),
            "skip_existing": self.skip_existing_cb.isChecked(),
            "validate": self.validate_cb.isChecked(),
        }
        self.tables_selected.emit(tables, options)
