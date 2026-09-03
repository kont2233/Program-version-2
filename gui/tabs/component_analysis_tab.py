"""
Component Analysis Tab

Implements PCA and NMF controls.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QSpinBox, QPushButton

class ComponentAnalysisTab(QWidget):
    """Tab for component analysis (PCA, NMF)."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.label = QLabel("Component Analysis Method:")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["PCA", "NMF"])
        self.n_components_spin = QSpinBox()
        self.n_components_spin.setRange(1, 20)
        self.n_components_spin.setValue(2)
        self.apply_button = QPushButton("Apply Analysis")
        layout.addWidget(self.label)
        layout.addWidget(self.method_combo)
        layout.addWidget(self.n_components_spin)
        layout.addWidget(self.apply_button)
