"""
Menu Functions for ECPypsi

Defines menu bar creation and all menu action handlers.
"""
from PySide6.QtCore import Qt, QDir
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QToolButton,
    QWidget,
)
from models.config_manager import ConfigManager
from models.spectrum import RamanSpectrum
from utils.import_settings import get_selected_delimiter, get_new_path
from gui.dialogs.ImportSettingsDialog import ImportSettingsDialog

def create_menu_bar(parent):
    """Create the menu bar with all actions."""
    menu_bar = QWidget(parent)
    menu_bar.setObjectName("applicationMenuBar")
    menu_bar.setStyleSheet(
        "QWidget#applicationMenuBar { border: none; background: transparent; }"
        "QPushButton { border: none; padding: 2px 8px; background: transparent; }"
        "QPushButton:hover { background: #e6e6e6; }"
        "QPushButton:pressed { background: #d6d6d6; }"
    )
    menu_layout = QHBoxLayout(menu_bar)
    menu_layout.setContentsMargins(6, 0, 6, 0)
    menu_layout.setSpacing(2)

    def add_menu(title: str) -> QMenu:
        menu = QMenu(menu_bar)
        button = QToolButton(menu_bar)
        button.setText(title)
        button.setMenu(menu)
        button.setPopupMode(QToolButton.InstantPopup)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.NoFocus)
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        button.setMaximumHeight(28)
        menu_layout.addWidget(button)
        return menu

    cfg: ConfigManager = ConfigManager()

    # File menu
    file_menu = add_menu("File")
    open_action = QAction("Open", parent)
    open_action.triggered.connect(lambda: MenuBar_File_Open(parent))
    file_menu.addAction(open_action)

    save_action = QAction("Save", parent)
    save_action.triggered.connect(lambda: MenuBar_File_Save(parent))
    file_menu.addAction(save_action)

    script_import_action = QAction("Script Import", parent)
    script_import_action.triggered.connect(lambda: MenuBar_File_ScriptImport(parent))
    file_menu.addAction(script_import_action)

    exit_action = QAction("Exit", parent)
    exit_action.triggered.connect(lambda: MenuBar_File_Exit(parent))
    file_menu.addAction(exit_action)

    # Settings menu
    settings_menu = add_menu("Settings")
    import_settings_action = QAction("Import Settings", parent)
    import_settings_action.triggered.connect(lambda: MenuBar_Settings_ImportSettings(parent))
    settings_menu.addAction(import_settings_action)

    color_scheme_action = QAction("Color Scheme", parent)
    color_scheme_action.triggered.connect(lambda: MenuBar_Settings_ColorScheme(parent, cfg))
    settings_menu.addAction(color_scheme_action)

    export_action = QAction("Export", parent)
    export_action.triggered.connect(lambda: MenuBar_Settings_Export(parent, cfg))
    settings_menu.addAction(export_action)

    advanced_action = QAction("Advanced", parent)
    advanced_action.triggered.connect(lambda: MenuBar_Settings_Advanced(parent, cfg))
    settings_menu.addAction(advanced_action)

    # Help menu
    help_menu = add_menu("Help")
    documentation_action = QAction("Documentation", parent)
    documentation_action.triggered.connect(lambda: MenuBar_Help_Documentation(parent))
    help_menu.addAction(documentation_action)

    log_action = QAction("Log", parent)
    log_action.triggered.connect(lambda: MenuBar_Help_Log(parent))
    help_menu.addAction(log_action)

    report_issue_action = QAction("Report Issue", parent)
    report_issue_action.triggered.connect(lambda: MenuBar_Help_ReportIssue(parent))
    help_menu.addAction(report_issue_action)

    menu_layout.addStretch(1)
    return menu_bar

def MenuBar_File_Open(parent):
    """Open one or more raw spectrum files."""
    file_paths, _ = QFileDialog.getOpenFileNames(
        parent,
        "Open spectra",
        "",
        "Spectrum files (*.txt *.csv);;All files (*)",
    )
    if not file_paths:
        return

    delimiter = get_selected_delimiter()
    failures = []
    for file_path in file_paths:
        try:
            spectrum = RamanSpectrum(
                file_path,
                get_new_path(file_path),
                delimiter=delimiter,
            )
            parent.spectra_manager.add_spectrum(spectrum)
        except Exception as exc:
            failures.append(f"{file_path}: {exc}")

    if failures:
        QMessageBox.warning(
            parent,
            "Some spectra could not be opened",
            "\n".join(failures),
        )

def MenuBar_File_Save(parent):
    """Save processed spectra."""
    folder = QFileDialog.getExistingDirectory(parent, "Select Save Folder")
    if folder:
        parent.spectra_explorer.save_all(folder)


def MenuBar_File_ScriptImport(parent):
    """Import processing script (placeholder)."""
    QMessageBox.information(parent, "Script Import", "Script import not implemented yet.")

def MenuBar_File_Exit(parent):
    """Exit application."""
    parent.close()

def MenuBar_Settings_ImportSettings(parent):
    """Open the Import Settings dialog (delimiter, processed-file location)."""
    dialog = ImportSettingsDialog(parent)
    dialog.exec()

def MenuBar_Settings_ColorScheme(parent):
    """Change color scheme (placeholder)."""
    QMessageBox.information(parent, "Color Scheme", "Color scheme switching not implemented yet.")

def MenuBar_Settings_Export(parent):
    """Export spectra (placeholder)."""
    QMessageBox.information(parent, "Export", "Export not implemented yet.")
    dlg = QDialog(parent)
    dlg.setWindowTitle("Truncate - set shift limits")
    layout = QFormLayout(dlg)
    
    min_edit = QLineEdit("100")
    max_edit = QLineEdit("2000")
    layout.addRow("Min shift (cm⁻¹):", min_edit)
    layout.addRow("Max shift (cm⁻¹):", max_edit)
    
    btns = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel
    )
    layout.addWidget(btns)
    
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    
    if dlg.exec() == QDialog.Accepted:
        try:
            min_shift = float(min_edit.text())
            max_shift = float(max_edit.text())
            
        except ValueError:
            QMessageBox.warning(
                "Invalid input"
            )
def MenuBar_File_SaveAllSettings(parent, cfg: ConfigManager):
    file_path = ""
    cfg.change_config(file_path)

def MenuBar_Settings_Advanced(parent):
    """Advanced settings (placeholder)."""
    QMessageBox.information(parent, "Advanced Settings", "Advanced settings not implemented yet.")

def MenuBar_Help_Documentation(parent):
    """Show documentation."""
    QMessageBox.information(parent, "Documentation", "See README.md for documentation.")

def MenuBar_Help_Log(parent):
    """Show log (placeholder)."""
    QMessageBox.information(parent, "Log", "Log viewing not implemented yet.")

def MenuBar_Help_ReportIssue(parent):
    """Report an issue (placeholder)."""
    QMessageBox.information(parent, "Report Issue", "Please report issues on the project's GitHub page.")