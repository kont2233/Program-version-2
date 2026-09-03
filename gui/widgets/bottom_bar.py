"""
Bottom Bar Widget

Implements the status bar with QLabel, QProgressBar, and error icon.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtGui import QPixmap

class BottomBar(QWidget):
    """Bottom bar with status, progress, and error icon."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        self.setContentsMargins(5, 5, 5, 5)
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setFixedWidth(100)
        self.progress_bar.setValue(0)
        self.error_icon = QLabel()
        self.error_icon.setPixmap(QPixmap())  # Placeholder for error icon
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.error_icon)
