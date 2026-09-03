"""Modal dialog for import configuration: delimiter and processed-file location.

Replaces the "Files" / "Import" / "Processing" panel that used to sit at the
bottom of the Data tab. The old ".txt"/".tvb" file-type checkboxes and the
"Whole Folder" checkbox are intentionally NOT carried over: they only ever
controlled the old folder-scanning importer, which no longer exists now that
importing is done exclusively via File > Open (a plain multi-file picker with
no folder-scanning concept, and whose dialog filter is already hardcoded to
"*.txt *.csv"). Re-adding those checkboxes here would relocate dead UI, not
fix anything.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QHBoxLayout,
    QDialogButtonBox,
    QFileDialog,
    QWidget,
)

from models.config_manager import ConfigManager

CONFIG_KEY = "Import-Settings"


class ImportSettingsDialog(QDialog):
    """Edit and persist import settings (see utils/import_settings.py)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Settings")
        self.cfg = ConfigManager()
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.delimiter_dropdown = QComboBox()
        self.delimiter_dropdown.addItems(["Tab", "Comma", "Semicolon", "Other"])
        self.delimiter_dropdown.currentTextChanged.connect(self._toggle_custom_delim)
        form.addRow("Delimiter:", self.delimiter_dropdown)

        self.custom_delim_input = QLineEdit()
        self.custom_delim_input.setPlaceholderText("Enter delimiter")
        form.addRow("Custom delimiter:", self.custom_delim_input)

        self.use_source_folder_cb = QCheckBox("Use source folder for processed files")
        self.use_source_folder_cb.toggled.connect(self._toggle_processing_path)
        form.addRow(self.use_source_folder_cb)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        self.proc_path_input = QLineEdit()
        self.proc_path_btn = QPushButton("Browse…")
        self.proc_path_btn.clicked.connect(self._select_processing_path)
        path_row.addWidget(self.proc_path_input)
        path_row.addWidget(self.proc_path_btn)
        path_container = QWidget()
        path_container.setLayout(path_row)
        form.addRow("Processing path:", path_container)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_custom_delim(self, text: str) -> None:
        self.custom_delim_input.setEnabled(text == "Other")

    def _toggle_processing_path(self, use_source_checked: bool) -> None:
        self.proc_path_input.setEnabled(not use_source_checked)
        self.proc_path_btn.setEnabled(not use_source_checked)

    def _select_processing_path(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Processing Path")
        if folder:
            self.proc_path_input.setText(folder)

    def _load_settings(self) -> None:
        settings = self.cfg.get_value([CONFIG_KEY]) or {}
        delim = settings.get("Delimiter", "Comma")
        index = self.delimiter_dropdown.findText(delim)
        self.delimiter_dropdown.setCurrentIndex(index if index >= 0 else 1)
        self.custom_delim_input.setText(settings.get("CustomDelimiter", ""))
        use_source = bool(settings.get("UseSourceFolder", True))
        self.use_source_folder_cb.setChecked(use_source)
        self.proc_path_input.setText(settings.get("ProcessingPath", ""))
        self._toggle_custom_delim(self.delimiter_dropdown.currentText())
        self._toggle_processing_path(use_source)

    def _on_accept(self) -> None:
        self.cfg.set_value(
            [CONFIG_KEY],
            {
                "Delimiter": self.delimiter_dropdown.currentText(),
                "CustomDelimiter": self.custom_delim_input.text(),
                "UseSourceFolder": self.use_source_folder_cb.isChecked(),
                "ProcessingPath": self.proc_path_input.text(),
            },
        )
        self.accept()
        