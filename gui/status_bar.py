"""
Status Bar Implementation

This module implements a QStatusBar for the ECPypsi application. The status bar:
- Has a maximum height of 20px.
- Aligns its content (status message, progress bar, and error icon) to the right.
"""

from PySide6.QtWidgets import QStatusBar, QLabel, QProgressBar, QHBoxLayout, QWidget
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class StatusBar(QStatusBar):
    """Custom QStatusBar for the ECPypsi application."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set the maximum height of the status bar
        self.setMaximumHeight(20)

        # Create a container widget to hold the status bar content
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 10, 0)  # Add padding to the right
        layout.setSpacing(5)  # Spacing between elements

        # Status label
        self.status_label = QLabel("No process running")
        self.status_label.setMinimumWidth(400)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Align text to the left and center vertically
        layout.addWidget(self.status_label, stretch=1)  # Stretch ensures it takes up available space

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumHeight(15)  # Slightly smaller than the bar height
        self.progress_bar.setTextVisible(False)  # Hide the percentage text
        layout.addWidget(self.progress_bar, stretch=2)  # Stretch ensures it takes up more space

        # icon(s)
        self.i_error = QPixmap("resources/icons/error_icon.png")
        self.i_ready = QPixmap("resources/icons/ready_icon.png")
        self.i_progress = QPixmap("resources/icons/progress_icon.png")
        self.icon = QLabel()
        self.icon.setPixmap(self.i_ready)
        self.icon.setFixedSize(16, 16)  # Set a fixed size for the icon
        layout.addWidget(self.icon)

        # Align all content to the right
        layout.setAlignment(Qt.AlignRight)

        # Add the container widget to the status bar
        self.addWidget(container)

    def set_status(self, message: str):
        """
        Update the status message in the status bar.
        """
        self.status_label.setText(message)

    def set_progress(self, value: int):
        """
        Update the progress bar value.
        """
        self.progress_bar.setValue(value)

    def show_icon(self, pixmap: QPixmap):
        """
        Display an error icon in the status bar.

        Parameters:
        - pixmap (QPixmap): The pixmap to display as the error icon.
        """
        self.icon.setPixmap(pixmap)

    def clear_icon(self):
        """
        Clear the error icon from the status bar.
        """
        self.icon.clear()

    def show_error_icon(self):
        self.icon.setPixmap(self.i_error)
    def show_ready_icon(self):
        self.icon.setPixmap(self.i_ready)
    def show_progress_icon(self):
        self.icon.setPixmap(self.i_progress)

