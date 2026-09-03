"""Interactive Raman peak detection and multi-shape fitting."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QToolBar, QToolButton, QVBoxLayout, QWidget, QMenu,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.signal import find_peaks

from models.config_manager import ConfigManager
from treatments.peak_fitting import component_values, fit_peaks, gaussian, lorentzian, voigt


class _PeakCanvas(FigureCanvas):
    """Matplotlib canvas for peak markers, dragging, and context actions."""
    def __init__(self, owner):
        self.figure = Figure(figsize=(8, 6))
        super().__init__(self.figure)
        self.owner = owner
        self.axes = self.figure.add_subplot(211)
        self.residual_axes = self.figure.add_subplot(212, sharex=self.axes)
        self._drag_index: int | None = None
        self._drag_mode: str | None = None
        self.mpl_connect("button_press_event", self._press)
        self.mpl_connect("motion_notify_event", self._move)
        self.mpl_connect("button_release_event", self._release)

    def _nearest(self, x, y):
        if x is None or y is None or not self.owner.peaks:
            return None, None
        distances = [abs(float(peak[1]) - x) for peak in self.owner.peaks]
        index = int(np.argmin(distances))
        return index, distances[index]

    def _press(self, event):
        if event.inaxes is not self.axes or event.xdata is None:
            return
        index, distance = self._nearest(event.xdata, event.ydata)
        if event.button == 3:
            self.owner.open_peak_menu(index if distance is not None and distance <= self.owner._x_tolerance() else None, event)
            return
        if event.button == 1:
            if index is not None and distance <= self.owner._x_tolerance():
                self._drag_index = index
                self._drag_mode = "center" if event.key != "shift" else "height"
            else:
                self.owner.add_peak_at(event.xdata, event.ydata)

    def _move(self, event):
        if self._drag_index is None or event.inaxes is not self.axes:
            return
        peak = self.owner.peaks[self._drag_index]
        if self._drag_mode == "center" and event.xdata is not None:
            peak[1] = float(event.xdata)
        if event.ydata is not None:
            peak[0] = float(event.ydata) if self._drag_mode == "height" else peak[0]
        self.owner._refresh_table()
        self.owner._update_preview()

    def _release(self, event):
        self._drag_index = None
        self._drag_mode = None


class PeakFittingTab(QWidget):
    """Detect, edit, fit, and persist Raman peaks."""
    NAME = "Peak Fitting"
    SETTINGS_FILE = Path("config/peak_fitting_points.json")
    SHAPE_FILE = Path("config/peak_shapes.json")

    def __init__(self, manager=None, canvas=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.cfg = ConfigManager()
        self.peaks: list[list] = []
        self._build_ui()
        if manager:
            manager.spectrum_selected.connect(lambda spec: self._update_preview())

    def _build_ui(self):
        root = QVBoxLayout(self)
        split = QSplitter(Qt.Vertical)
        self.plot = _PeakCanvas(self)
        split.addWidget(self.plot)
        settings = QWidget()
        split.addWidget(settings)
        split.setSizes([600, 350])
        root.addWidget(split)
        layout = QVBoxLayout(settings)
        bar = QToolBar("Peak fitting actions")
        layout.addWidget(bar)
        actions = (("Find peaks", self.find_peaks, "select.png"), ("Iterate one step", self.iterate_once, "apply_icon.png"), ("Iterate to convergence", self.iterate_convergence, "apply_icon.png"), ("Reset peak fits", self.reset_peaks, "revert_icon.png"), ("Apply to all", self.apply_to_all, "apply_icon.png"), ("Apply to selected", self.apply_to_selected, "Apply_selected_icon.png"), ("Apply to checked", self.apply_to_checked, "Apply_selected_icon.png"), ("Save peak fit", self.save_settings, "save_icon.png"), ("Load peak fit", self.load_settings, "load_icon.png"))
        for text, callback, icon in actions:
            button = QPushButton(text)
            button.setIcon(QIcon(f"resources/icons/{icon}"))
            button.clicked.connect(callback)
            bar.addWidget(button)
        self.show_residuals = QCheckBox("Residuals")
        self.show_residuals.toggled.connect(self._update_preview)
        bar.addWidget(self.show_residuals)
        self.show_gof = QCheckBox("Goodness of fit")
        self.show_gof.toggled.connect(self._update_preview)
        bar.addWidget(self.show_gof)

        form = QFormLayout()
        layout.addLayout(form)
        self.prominence = self._number("prominence", 0.05, 0, 1e9, 0.05)
        self.distance = self._number("distance", 5, 1, 10000, 1)
        self.max_peaks = self._number("max_peaks", 5, 1, 100, 1)
        form.addRow("Prominence", self._with_default(self.prominence, "prominence", 0.05))
        form.addRow("Minimum distance", self._with_default(self.distance, "distance", 5))
        form.addRow("Maximum peaks", self._with_default(self.max_peaks, "max_peaks", 5))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Height", "Center", "Width", "Shape", "Lower limit", "Upper limit"])
        self.table.itemChanged.connect(self._table_changed)
        layout.addWidget(self.table)

    def _number(self, name, value, minimum, maximum, step):
        control = QDoubleSpinBox()
        control.setObjectName(name)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setValue(self.cfg.get_default_value([self.NAME, "Detection", name], value))
        control.valueChanged.connect(self._arguments_changed)
        return control

    def _with_default(self, control, name, fallback):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(control)
        reset = QToolButton()
        reset.setText("Reset")
        reset.clicked.connect(lambda: control.setValue(self.cfg.get_default_value([self.NAME, "Detection", name], fallback)))
        layout.addWidget(reset)
        return row

    def _data(self):
        spec = self.manager.current_spectrum() if self.manager else None
        return None if spec is None else spec.current

    def _x_tolerance(self):
        data = self._data()
        return float(np.ptp(data[:, 0]) * 0.025) if data is not None else 5.0

    def _arguments_changed(self, *args):
        self._persist_detection()
        self._update_preview()

    def _persist_detection(self):
        self.cfg.set_value([self.NAME, "Detection"], {"prominence": self.prominence.value(), "distance": int(self.distance.value()), "max_peaks": int(self.max_peaks.value())})

    def find_peaks(self):
        data = self._data()
        if data is None:
            return
        indexes, _ = find_peaks(data[:, 1], prominence=self.prominence.value(), distance=int(self.distance.value()))
        indexes = indexes[np.argsort(data[indexes, 1])[-int(self.max_peaks.value()):]]
        spacing = float(np.median(np.diff(data[:, 0]))) if len(data) > 1 else 1.0
        self.peaks = [[float(data[i, 1]), float(data[i, 0]), max(spacing * 3, 1.0), "Gaussian", None, None] for i in sorted(indexes)]
        self._refresh_table()
        self._update_preview()

    def add_peak_at(self, center, height):
        self.peaks.append([float(height), float(center), max(self._x_tolerance() / 3, 1.0), "Gaussian", None, None])
        self.peaks.sort(key=lambda peak: peak[1])
        self._refresh_table()
        self._update_preview()

    def open_peak_menu(self, index, event):
        menu = QMenu(self)
        if index is None:
            menu.addAction("Add peak", lambda: self.add_peak_at(event.xdata, event.ydata))
        else:
            menu.addAction("Remove peak", lambda: self._remove_peak(index))
            shape_menu = menu.addMenu("Select shape")
            for shape in ("Gaussian", "Lorentzian", "Voigt"):
                shape_menu.addAction(shape, lambda checked=False, i=index, s=shape: self._set_shape(i, s))
            menu.addAction("Set limits", lambda: self._set_limits(index))
        menu.exec(self.plot.mapToGlobal(self.plot.rect().center()))

    def _remove_peak(self, index):
        self.peaks.pop(index); self._refresh_table(); self._update_preview()

    def _set_shape(self, index, shape):
        self.peaks[index][3] = shape; self._refresh_table(); self._update_preview()

    def _set_limits(self, index):
        lower, ok = QInputDialog.getDouble(self, "Lower limit", "Lower center limit", self.peaks[index][4] or self.peaks[index][1] - self._x_tolerance(), -1e9, 1e9, 4)
        if ok:
            upper, ok = QInputDialog.getDouble(self, "Upper limit", "Upper center limit", self.peaks[index][5] or self.peaks[index][1] + self._x_tolerance(), -1e9, 1e9, 4)
            if ok:
                self.peaks[index][4:6] = [lower, upper]; self._refresh_table()

    def _refresh_table(self):
        self.table.blockSignals(True); self.table.setRowCount(len(self.peaks))
        for row, peak in enumerate(self.peaks):
            for column, value in enumerate(peak):
                self.table.setItem(row, column, QTableWidgetItem("" if value is None else str(value)))
        self.table.blockSignals(False)

    def _table_changed(self, item):
        try:
            value = item.text()
            self.peaks[item.row()][item.column()] = value if item.column() == 3 else (None if value == "" else float(value))
            self._update_preview()
        except ValueError:
            return

    def _update_preview(self):
        self.plot.axes.clear(); self.plot.residual_axes.clear()
        data = self._data()
        if data is None:
            self.plot.draw_idle(); return
        x, y = data[:, 0], data[:, 1]
        self.plot.axes.plot(x, y, label="Spectrum", color="black")
        cumulative = np.zeros_like(x)
        for peak in self.peaks:
            values = component_values(x, peak)
            cumulative += values
            self.plot.axes.plot(x, values, linestyle="--", alpha=0.75, label=peak[3])
            self.plot.axes.scatter([peak[1]], [peak[0]], color="red", zorder=5)
        if self.peaks:
            self.plot.axes.plot(x, cumulative, color="tab:orange", linewidth=2, label="Cumulative fit")
            if self.show_residuals.isChecked():
                self.plot.residual_axes.plot(x, y - cumulative, color="tab:red", label="Residuals")
                self.plot.residual_axes.set_ylabel("Residual")
            if self.show_gof.isChecked():
                ss_res = float(np.sum((y - cumulative) ** 2)); ss_tot = float(np.sum((y - np.mean(y)) ** 2))
                self.plot.residual_axes.text(0.02, 0.9, f"R2 = {1 - ss_res / ss_tot if ss_tot else 0:.5f}", transform=self.plot.residual_axes.transAxes)
        self.plot.axes.legend(loc="best")
        self.plot.axes.set_ylabel("Intensity"); self.plot.axes.set_xlabel("Raman shift (cm-1)")
        self.plot.residual_axes.set_xlabel("Raman shift (cm-1)")
        self.plot.draw_idle()

    def _apply(self, caller):
        self._persist_detection()
        guesses = [(peak[0], peak[1], peak[2]) for peak in self.peaks]
        shapes = [peak[3] for peak in self.peaks]
        if guesses:
            caller("Peak Fitting", fit_peaks, peak_guesses=guesses, shapes=shapes, bounds=self._bounds())

    def _bounds(self):
        lower = []
        upper = []
        for height, center, width, shape, center_min, center_max in self.peaks:
            lower.extend([-np.inf, center_min if center_min is not None else -np.inf, 1e-12])
            upper.extend([np.inf, center_max if center_max is not None else np.inf, np.inf])
        return lower, upper

    def apply_to_all(self):
        if self.manager: self._apply(self.manager._apply_to_all)
    def apply_to_checked(self):
        if self.manager: self._apply(self.manager._apply_to_checked)
    def apply_to_selected(self):
        self._persist_detection(); spec = self.manager.current_spectrum() if self.manager else None
        if spec and self.peaks:
            self.manager._apply_treatment(spec, "Peak Fitting", fit_peaks, peak_guesses=[(p[0], p[1], p[2]) for p in self.peaks], shapes=[p[3] for p in self.peaks], bounds=self._bounds())
    def iterate_once(self):
        data = self._data()
        if data is not None and self.peaks:
            fitted = fit_peaks(data, [(p[0], p[1], p[2]) for p in self.peaks], shapes=[p[3] for p in self.peaks])[5]["peaks"]
            self.peaks = [list(peak) + [None, None] if len(peak) == 4 else list(peak) for peak in fitted]
            self._refresh_table(); self._update_preview()
    def iterate_convergence(self):
        for _ in range(5): self.iterate_once()
    def reset_peaks(self): self.peaks = []; self._refresh_table(); self._update_preview()
    def save_settings(self):
        self._persist_detection(); path, _ = QFileDialog.getSaveFileName(self, "Save peak fit settings", str(self.SETTINGS_FILE), "JSON files (*.json)")
        if path: Path(path).write_text(json.dumps(self.peaks, indent=2), encoding="utf-8")
    def load_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load peak fit settings", str(self.SETTINGS_FILE), "JSON files (*.json)")
        if path: self.peaks = json.loads(Path(path).read_text(encoding="utf-8")); self._refresh_table(); self._update_preview()
