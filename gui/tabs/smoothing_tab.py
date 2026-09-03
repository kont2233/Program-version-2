"""Interactive smoothing controls and preview."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFormLayout, QHBoxLayout, QListWidget, QPushButton,
    QSpinBox, QSplitter, QStackedWidget, QToolBar, QToolButton, QVBoxLayout,
    QWidget,
)

from gui.widgets.spectra_canvas import SpectraCanvas
from gui.widgets.spectra_manager import SpectraManagerWidget
from models.config_manager import ConfigManager
from models.spectrum import RamanSpectrum
from treatments.smoothing import gaussian_smooth, moving_average, smooth


class SmoothingTab(QWidget):
    """Configure, preview, and apply smoothing methods."""

    NAME = "Smoothing"
    METHODS = ("Savitzky-Golay", "Moving Average", "Gaussian")

    def __init__(self, manager=None, canvas=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.canvas = canvas
        self.cfg = ConfigManager()
        self._controls: Dict[str, Dict[str, QWidget]] = {}
        self._methods = (smooth, moving_average, gaussian_smooth)
        self._build_ui()
        self.method_list.setCurrentRow(0)
        if self.canvas is not None:
            self.canvas.selectedLineChanged.connect(self._update_preview)
        if self.manager is not None:
            self.manager.spectrum_selected.connect(self._show_selected_spectrum)

    def _build_ui(self):
        root = QVBoxLayout(self)
        settings = QWidget()
        splitter = QSplitter(Qt.Vertical)
        if self.canvas is not None:
            splitter.addWidget(self.canvas)
        splitter.addWidget(settings)
        splitter.setSizes([600, 300])
        root.addWidget(splitter)
        layout = QVBoxLayout(settings)

        toolbar = QToolBar("Smoothing actions", settings)
        toolbar.setIconSize(QSize(18, 18))
        self._action(toolbar, "Apply to all", self.apply_to_all, "apply_icon.png")
        self._action(toolbar, "Apply to selected", self.apply_to_selected, "Apply_selected_icon.png")
        self._action(toolbar, "Apply to checked", self.apply_to_checked, "Apply_selected_icon.png")
        self._action(toolbar, "Save settings", self.save_settings, "save_icon.png")
        layout.addWidget(toolbar)

        controls = QSplitter(Qt.Horizontal)
        self.method_list = QListWidget()
        self.method_list.addItems(self.METHODS)
        self.method_list.setMaximumWidth(190)
        self.method_list.currentRowChanged.connect(self._method_changed)
        controls.addWidget(self.method_list)
        self.parameter_stack = QStackedWidget()
        self._create_page("Savitzky-Golay", (("window_length", "Window length", 3, 101, 2, 11), ("polyorder", "Polynomial order", 0, 15, 1, 3)))
        self._create_page("Moving Average", (("window", "Window", 3, 101, 2, 5),))
        self._create_page("Gaussian", (("sigma", "Sigma", 0.1, 100.0, 0.1, 2.0),))
        controls.addWidget(self.parameter_stack)
        layout.addWidget(controls)

    def _action(self, toolbar, text, callback, icon):
        button = QPushButton(text)
        button.setIcon(QIcon(f"resources/icons/{icon}"))
        button.clicked.connect(callback)
        toolbar.addWidget(button)

    def _create_page(self, method, fields):
        page = QWidget()
        form = QFormLayout(page)
        controls = {}
        for name, label, minimum, maximum, step, fallback in fields:
            control = QDoubleSpinBox() if name == "sigma" else QSpinBox()
            control.setRange(minimum, maximum)
            control.setSingleStep(step)
            if name == "sigma":
                control.setDecimals(3)
            default = self.cfg.get_default_value([self.NAME, method, name], fallback)
            control.setValue(default)
            control.valueChanged.connect(self._arguments_changed)
            reset = QToolButton()
            reset.setText("Reset")
            reset.setToolTip(f"Restore default {label}")
            reset.clicked.connect(lambda checked=False, m=method, n=name, c=control, f=fallback: c.setValue(self.cfg.get_default_value([self.NAME, m, n], f)))
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(control)
            row_layout.addWidget(reset)
            form.addRow(label, row)
            controls[name] = control
        self._controls[method] = controls
        self.parameter_stack.addWidget(page)

    @property
    def method(self):
        return self.METHODS[self.method_list.currentRow()]

    def _method_changed(self, index):
        if index < 0:
            return
        self.parameter_stack.setCurrentIndex(index)
        self._persist_arguments()
        self._update_preview(self.manager.current_spectrum() if self.manager else None)

    def _arguments(self):
        return {name: control.value() for name, control in self._controls[self.method].items()}

    def _persist_arguments(self):
        if self.method_list.currentRow() >= 0 and self.method in self._controls:
            self.cfg.set_value([self.NAME, self.method], self._arguments())

    def _arguments_changed(self, value: Any):
        self._persist_arguments()
        self._update_preview(self.manager.current_spectrum() if self.manager else None)

    def _show_selected_spectrum(self, spec: RamanSpectrum | None):
        if self.canvas is None:
            return
        if spec is None:
            self.canvas.deselect()
        else:
            self.canvas.draw_selected(spec)

    def _update_preview(self, spec: RamanSpectrum | None):
        if self.canvas is None:
            return
        self.canvas.remove_preview()
        if spec is None:
            return
        try:
            result = self._methods[self.method_list.currentRow()](spec.current, **self._arguments())[0]
        except (TypeError, ValueError):
            return
        self.canvas.draw_preview(f"{spec.name}: {self.method} preview", result)

    def apply_to_all(self):
        self._persist_arguments()
        if self.manager is not None:
            self.manager._apply_to_all(self.method, self._methods[self.method_list.currentRow()], **self._arguments())

    def apply_to_selected(self):
        self._persist_arguments()
        if self.manager is not None and self.manager.current_spectrum() is not None:
            self.manager._apply_treatment(self.manager.current_spectrum(), self.method, self._methods[self.method_list.currentRow()], **self._arguments())

    def apply_to_checked(self):
        self._persist_arguments()
        if self.manager is not None:
            self.manager._apply_to_checked(self.method, self._methods[self.method_list.currentRow()], **self._arguments())

    def save_settings(self):
        self._persist_arguments()
        self.cfg.exit_saves()
