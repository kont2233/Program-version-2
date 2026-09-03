"""
Spectra Explorer Widget

Implements the left panel QTreeView for spectra and their processing history.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QPushButton, QHBoxLayout, QFileSystemModel
from PySide6.QtCore import QDir

class SpectraExplorer(QWidget):
    """Widget for exploring and managing spectra."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # TreeView for spectra
        self.tree_view = QTreeView()
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.currentPath())
        self.tree_view.setModel(self.model)
        self.tree_view.setRootIndex(self.model.index(QDir.currentPath()))
        layout.addWidget(self.tree_view)

        # Button bar
        button_layout = QHBoxLayout()
        self.show_all_button = QPushButton("Show All")
        self.deselect_all_button = QPushButton("Deselect All")
        button_layout.addWidget(self.show_all_button)
        button_layout.addWidget(self.deselect_all_button)
        layout.addLayout(button_layout)

    def load_folder(self, folder_path):
        """Load spectra from a folder."""
        self.model.setRootPath(folder_path)
        self.tree_view.setRootIndex(self.model.index(folder_path))

    def save_all(self, folder_path):
        """Save all spectra to a folder (placeholder)."""
        # Implement saving logic as needed
        pass
