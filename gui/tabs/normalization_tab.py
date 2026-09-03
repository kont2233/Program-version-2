"""Interactive Raman intensity normalization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QToolBar, QToolButton, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from models.config_manager import ConfigManager
from treatments.normalization import normalize


class _NormalizationCanvas(FigureCanvas):
    """Interactive plot used to select high, low, and peak regions."""

    def __init__(self, owner):
        self.figure = Figure(figsize=(7, 5))
        super().__init__(self.figure)
        self.owner = owner
        self.axes = self.figure.add_subplot(111)
        self._start: float | None = None
        self._dragging = False
        self.mpl_connect("button_press_event", self._press)
        self.mpl_connect("motion_notify_event", self._move)
        self.mpl_connect("button_release_event", self._release)

    def _press(self, event):
        if event.inaxes is self.axes and event.button == 1:
            self._start = event.xdata
            self._dragging = True

    def _move(self, event):
        if self._dragging and event.inaxes is self.axes:
            self.owner._draw_region_preview(self._start, event.xdata)

    def _release(self, event):
        if not self._dragging or event.inaxes is not self.axes or event.xdata is None:
            self._dragging = False
            return
        start, end = sorted((self._start, event.xdata))
        low_region = bool(event.key and "control" in event.key.lower())
        if self.owner.method == "Normalize to Peak":
            self.owner._set_region("peak", start, end)
        elif low_region:
            self.owner._set_region("low", start, end)
        else:
            self.owner._set_region("high", start, end)
        self._start = None
        self._dragging = False
        self.owner._update_preview()


class NormalizationTab(QWidget):
    """Normalize intensity using whole-spectrum, region, or peak references."""

    NAME = "Normalization"
    METHODS = ("0 to 1", "Normalize to Highest", "Normalize to Peak")
    REGION_FILE = Path("config/normalization_regions.json")

    def __init__(self, manager=None, canvas=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.cfg = ConfigManager()
        self.regions: dict[str, list[float] | None] = {"high": None, "low": None, "peak": None}
        self._build_ui()
        if manager:
            manager.spectrum_selected.connect(lambda spec: self._update_preview())

    def _build_ui(self):
        root = QVBoxLayout(self)
        split = QSplitter(Qt.Vertical)
        self.plot = _NormalizationCanvas(self)
        split.addWidget(self.plot)
        settings = QWidget()
        layout = QVBoxLayout(settings)
        split.addWidget(settings)
        split.setSizes([600, 300])
        root.addWidget(split)

        toolbar = QToolBar("Normalization actions")
        layout.addWidget(toolbar)
        for text, callback, icon in (("Apply to all", self.apply_to_all, "apply_icon.png"), ("Apply to selected", self.apply_to_selected, "Apply_selected_icon.png"), ("Apply to checked", self.apply_to_checked, "Apply_selected_icon.png"), ("Save settings", self.save_settings, "save_icon.png")):
            button = QPushButton(text)
            button.setIcon(QIcon(f"resources/icons/{icon}"))
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        save_region = QPushButton("Save regions")
        save_region.clicked.connect(self.save_regions)
        toolbar.addWidget(save_region)
        load_region = QPushButton("Load regions")
        load_region.clicked.connect(self.load_regions)
        toolbar.addWidget(load_region)

        self.method_combo = QComboBox()
        self.method_combo.addItems(self.METHODS)
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        layout.addWidget(self.method_combo)
        form = QFormLayout()
        layout.addLayout(form)
        self.controls: dict[str, QDoubleSpinBox] = {}
        for name, label in (("high_start", "High region start"), ("high_end", "High region end"), ("low_start", "Low region start"), ("low_end", "Low region end"), ("peak_start", "Peak region start"), ("peak_end", "Peak region end"), ("tolerance", "Peak tolerance")):
            self._add_control(form, name, label, 0.5 if name == "tolerance" else 0.0)
        self.shape = QComboBox()
        self.shape.addItems(("Gaussian", "Lorentzian"))
        self.shape.currentTextChanged.connect(self._arguments_changed)
        form.addRow("Peak shape", self.shape)
        self.status = QLabel("Select a region on the plot or enter values below.")
        layout.addWidget(self.status)
        self._update_enabled()

    def _add_control(self, form, name, label, fallback):
        control = QDoubleSpinBox()
        control.setRange(-100000.0, 100000.0)
        control.setDecimals(4)
        control.setValue(self.cfg.get_default_value([self.NAME, name], fallback))
        control.valueChanged.connect(self._arguments_changed)
        reset = QToolButton()
        reset.setText("Reset")
        reset.clicked.connect(lambda: control.setValue(self.cfg.get_default_value([self.NAME, name], fallback)))
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(control)
        row_layout.addWidget(reset)
        form.addRow(label, row)
        self.controls[name] = control

    @property
    def method(self):
        return self.method_combo.currentText()

    def _method_changed(self, index):
        self._update_enabled()
        self._persist()
        self._update_preview()

    def _update_enabled(self):
        highest = self.method == "Normalize to Highest"
        peak = self.method == "Normalize to Peak"
        for name in ("high_start", "high_end", "low_start", "low_end"):
            self.controls[name].setEnabled(highest)
        for name in ("peak_start", "peak_end"):
            self.controls[name].setEnabled(peak)
        self.controls["tolerance"].setEnabled(peak)
        self.shape.setEnabled(peak)

    def _value(self, name):
        value = self.controls[name].value()
        return None if value == 0 else value

    def _arguments(self):
        if self.method == "0 to 1":
            return {"method": "zero_one"}
        if self.method == "Normalize to Highest":
            high = self.regions["high"]
            low = self.regions["low"]
            return {"method": "highest", "min_shift": high[0] if high else self._value("high_start"), "max_shift": high[1] if high else self._value("high_end"), "low_min_shift": low[0] if low else self._value("low_start"), "low_max_shift": low[1] if low else self._value("low_end")}
        peak = self.regions["peak"]
        return {"method": "peak", "peak_shift": None, "peak_min_shift": peak[0] if peak else self._value("peak_start"), "peak_max_shift": peak[1] if peak else self._value("peak_end"), "tolerance": self.controls["tolerance"].value(), "peak_shape": self.shape.currentText()}

    def _set_region(self, name, start, end):
        self.regions[name] = [float(start), float(end)]
        if name == "high":
            self.controls["high_start"].setValue(float(start)); self.controls["high_end"].setValue(float(end))
        elif name == "low":
            self.controls["low_start"].setValue(float(start)); self.controls["low_end"].setValue(float(end))
        else:
            self.controls["peak_start"].setValue(float(start)); self.controls["peak_end"].setValue(float(end))

    def _draw_region_preview(self, start, end):
        self._update_preview()
        if start is not None and end is not None:
            self.plot.axes.axvspan(min(start, end), max(start, end), color="tab:blue", alpha=0.15)
            self.plot.draw_idle()

    def _arguments_changed(self, *args):
        self._persist(); self._update_preview()

    def _persist(self):
        self.cfg.set_value([self.NAME, self.method], self._arguments())

    def _update_preview(self):
        self.plot.axes.clear()
        spec = self.manager.current_spectrum() if self.manager else None
        if spec is None:
            self.plot.draw_idle(); return
        data = spec.current
        try:
            args = self._arguments()
            result = normalize(data, **args)[0]
            self.plot.axes.plot(data[:, 0], data[:, 1], label="Original")
            self.plot.axes.plot(result[:, 0], result[:, 1], label="Normalized", color="tab:green")
            self.plot.axes.set_title(self.method)
            if self.method == "Normalize to Peak":
                peak_data = data
                if args["peak_min_shift"] is not None:
                    peak_data = peak_data[peak_data[:, 0] >= args["peak_min_shift"]]
                if args["peak_max_shift"] is not None:
                    peak_data = peak_data[peak_data[:, 0] <= args["peak_max_shift"]]
                if len(peak_data) == 0:
                    raise ValueError("The peak region contains no data.")
                peak_index = int(np.argmax(peak_data[:, 1]))
                peak = float(peak_data[peak_index, 0])
                self.plot.axes.axvline(peak, color="red", linestyle="--", label="Reference peak")
                width = max(float(np.ptp(peak_data[:, 0])) / 6.0, 1e-6)
                peak_height = float(peak_data[peak_index, 1])
                fit_x = np.linspace(peak_data[0, 0], peak_data[-1, 0], 300)
                if self.shape.currentText() == "Lorentzian":
                    fit_y = peak_height / (1.0 + ((fit_x - peak) / width) ** 2)
                else:
                    fit_y = peak_height * np.exp(-0.5 * ((fit_x - peak) / width) ** 2)
                self.plot.axes.plot(fit_x, fit_y, color="tab:red", label=f"{self.shape.currentText()} fit")
                self.status.setText(f"Peak reference: {peak:.4f}")
            for name, color in (("high", "tab:blue"), ("low", "tab:orange"), ("peak", "tab:red")):
                if self.regions[name] is not None:
                    self.plot.axes.axvspan(*self.regions[name], color=color, alpha=0.12)
            self.plot.axes.legend()
        except (ValueError, IndexError):
            self.status.setText("Adjust the selected region or parameters.")
        self.plot.draw_idle()

    def save_regions(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save normalization regions", str(self.REGION_FILE), "JSON files (*.json)")
        if path: Path(path).write_text(json.dumps(self.regions, indent=2), encoding="utf-8")

    def load_regions(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load normalization regions", str(self.REGION_FILE), "JSON files (*.json)")
        if path:
            self.regions = json.loads(Path(path).read_text(encoding="utf-8")); self._update_preview()

    def _apply(self, caller):
        self._persist(); caller("Normalization", normalize, **self._arguments())

    def apply_to_all(self):
        if self.manager: self._apply(self.manager._apply_to_all)
    def apply_to_checked(self):
        if self.manager: self._apply(self.manager._apply_to_checked)
    def apply_to_selected(self):
        self._persist(); spec = self.manager.current_spectrum() if self.manager else None
        if spec: self.manager._apply_treatment(spec, "Normalization", normalize, **self._arguments())
    def save_settings(self): self._persist(); self.cfg.exit_saves()
