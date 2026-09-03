from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSizePolicy,
)
from PySide6.QtGui import QPixmap, QIcon

class IconButton(QPushButton):
    """Button with label and icon."""

    def __init__(self, label: str, icon_path: str, parent=None):
        super().__init__()
        #btn = QPushButton(label)
        self.setText(label)
        self.setIcon(QIcon(icon_path))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)