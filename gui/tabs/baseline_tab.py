"""Baseline estimation, preview, and editable custom baselines."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QListWidget, QPushButton, QSpinBox, QSplitter, QToolBar, QToolButton,
    QStackedWidget, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.interpolate import interp1d, UnivariateSpline
from scipy.signal import find_peaks

from models.config_manager import ConfigManager
from treatments.baseline import baseline_correct, constant_baseline, custom_baseline, polynomial_baseline, snip_baseline


class _BaselineCanvas(FigureCanvas):
    """Plot the source/baseline and corrected spectrum with editable anchors."""
    def __init__(self, owner):
        self.figure = Figure(figsize=(7, 6))
        super().__init__(self.figure)
        self.owner = owner
        self.upper = self.figure.add_subplot(211)
        self.lower = self.figure.add_subplot(212, sharex=self.upper)
        self._drag_index: int | None = None
        self.mpl_connect("button_press_event", self._press)
        self.mpl_connect("motion_notify_event", self._move)
        self.mpl_connect("button_release_event", self._release)

    def _press(self, event):
        if event.inaxes is not self.upper or event.xdata is None or event.ydata is None:
            return
        if event.button == 1:
            if self.owner.method == "Constant" and self.owner.constant_mode() == "Custom":
                self.owner.custom_value.setValue(event.ydata)
                return
            if self.owner.method == "Custom" and self.owner.points:
                distances = [abs(x - event.xdata) for x, _ in self.owner.points]
                index = int(np.argmin(distances))
                if distances[index] <= self.owner._point_tolerance():
                    self._drag_index = index
        elif event.button == 3 and self.owner.method == "Custom":
            distances = [abs(x - event.xdata) for x, _ in self.owner.points]
            if distances and min(distances) <= self.owner._point_tolerance():
                self.owner.points.pop(int(np.argmin(distances)))
            else:
                self.owner.points.append([float(event.xdata), float(event.ydata)])
            self.owner.points.sort(key=lambda point: point[0])
            self.owner._refresh_points()
            self.owner._update_preview()

    def _move(self, event):
        if self._drag_index is None or event.inaxes is not self.upper:
            return
        self.owner.points[self._drag_index] = [float(event.xdata), float(event.ydata)]
        self.owner._refresh_points()
        self.owner._update_preview()

    def _release(self, event):
        self._drag_index = None


class BaselineTab(QWidget):
    """Estimate and subtract baselines with automatic, constant, or custom methods."""
    NAME = "Baseline"
    METHODS = ("Automatic", "Constant", "Custom")
    POINTS_FILE = Path("config/custom_baseline_points.json")

    def __init__(self, manager=None, canvas=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.cfg = ConfigManager()
        self.points: list[list[float]] = []
        self.canvas = _BaselineCanvas(self)
        self._controls: dict[str, dict[str, QWidget]] = {}
        self._build_ui()
        self.method_list.setCurrentRow(0)
        if manager:
            manager.spectrum_selected.connect(lambda spec: self._update_preview())

    def _build_ui(self):
        root = QVBoxLayout(self)
        view_split = QSplitter(Qt.Vertical)
        view_split.addWidget(self.canvas)
        settings = QWidget()
        view_split.addWidget(settings)
        view_split.setSizes([600, 350])
        root.addWidget(view_split)
        layout = QVBoxLayout(settings)
        toolbar = QToolBar("Baseline actions")
        layout.addWidget(toolbar)
        for text, callback, icon in (("Apply to all", self.apply_to_all, "apply_icon.png"), ("Apply to selected", self.apply_to_selected, "Apply_selected_icon.png"), ("Apply to checked", self.apply_to_checked, "Apply_selected_icon.png"), ("Save settings", self.save_settings, "save_icon.png")):
            button = QPushButton(text)
            button.setIcon(QIcon(f"resources/icons/{icon}"))
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        self.residuals = QCheckBox("Residuals")
        self.residuals.toggled.connect(self._update_preview)
        toolbar.addWidget(self.residuals)
        controls = QSplitter(Qt.Horizontal)
        self.method_list = QListWidget()
        self.method_list.addItems(self.METHODS)
        self.method_list.setMaximumWidth(150)
        self.method_list.currentRowChanged.connect(self._method_changed)
        controls.addWidget(self.method_list)
        self.stack = QStackedWidget()
        self._create_page("Automatic", [("algorithm", "Algorithm", ("ALS", "SNIP", "Polynomial")), ("lam", "Lambda", 1.0, 1e9, 1000.0, 1e5), ("p", "Asymmetry p", 0.0001, 0.9999, 0.001, 0.01), ("niter", "Iterations", 1, 100, 1, 10), ("degree", "Polynomial degree", 0, 12, 1, 2)])
        self._create_page("Constant", [("mode", "Baseline", ("Min", "Max", "Mean", "Median", "Custom")), ("value", "Custom value", -1e9, 1e9, 0.1, 0.0)])
        self._create_page("Custom", [("points_count", "Points to find", 2, 100, 1, 10), ("connection", "Connection", ("Linear", "Spline", "BSpline")), ("fit_points", "Fit points to spectrum", ("Off", "On"))])
        controls.addWidget(self.stack)
        layout.addWidget(controls)
        self._update_enabled_controls()

    def _create_page(self, method, fields):
        page = QWidget()
        form = QFormLayout(page)
        controls = {}
        for field in fields:
            name, label = field[:2]
            if isinstance(field[2], tuple):
                control = QComboBox()
                control.addItems(field[2])
            else:
                control = QDoubleSpinBox() if isinstance(field[2], float) else QSpinBox()
                control.setRange(field[2], field[3])
                control.setSingleStep(field[4])
                control.setValue(self.cfg.get_default_value([self.NAME, method, name], field[5]))
            reset = QToolButton()
            reset.setText("Reset")
            reset.clicked.connect(lambda checked=False, m=method, n=name, c=control, f=field[-1]: self._reset_control(m, n, c, f))
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(control)
            row_layout.addWidget(reset)
            form.addRow(label, row)
            controls[name] = control
            if isinstance(control, QComboBox):
                control.currentTextChanged.connect(self._arguments_changed)
            else:
                control.valueChanged.connect(self._arguments_changed)
        self._controls[method] = controls
        if method == "Custom":
            actions = QHBoxLayout()
            find = QPushButton("Find points")
            find.clicked.connect(self.find_custom_points)
            save = QPushButton("Save custom baseline")
            save.clicked.connect(self.save_custom_baseline)
            load = QPushButton("Load custom baseline")
            load.clicked.connect(self.load_custom_baseline)
            actions.addWidget(find)
            actions.addWidget(save)
            actions.addWidget(load)
            form.addRow(actions)
        self.stack.addWidget(page)

    def _reset_control(self, method, name, control, fallback):
        value = self.cfg.get_default_value([self.NAME, method, name], fallback)
        control.setCurrentText(value) if isinstance(control, QComboBox) else control.setValue(value)

    @property
    def method(self):
        return self.METHODS[self.method_list.currentRow()]

    def _method_changed(self, index):
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        self._update_enabled_controls()
        self._persist()
        self._update_preview()

    def _update_enabled_controls(self):
        automatic = self._controls.get("Automatic", {})
        algorithm = automatic.get("algorithm")
        if algorithm:
            polynomial = algorithm.currentText() == "Polynomial"
            automatic["lam"].setEnabled(not polynomial)
            automatic["p"].setEnabled(not polynomial)
            automatic["niter"].setEnabled(not polynomial)
            automatic["degree"].setEnabled(polynomial)
        constant = self._controls.get("Constant", {})
        if constant:
            constant["value"].setEnabled(constant["mode"].currentText() == "Custom")

    def _arguments_changed(self, *args):
        self._update_enabled_controls()
        self._persist()
        self._update_preview()

    def _args(self):
        controls = self._controls[self.method]
        return {name: control.currentText() if isinstance(control, QComboBox) else control.value() for name, control in controls.items()}

    def _persist(self):
        if self.method_list.currentRow() >= 0:
            self.cfg.set_value([self.NAME, self.method], self._args())

    def _data(self):
        spec = self.manager.current_spectrum() if self.manager else None
        return None if spec is None else spec.current

    def constant_mode(self):
        return self._controls["Constant"]["mode"].currentText()

    def _point_tolerance(self):
        data = self._data()
        return float(np.ptp(data[:, 0]) * 0.02) if data is not None else 5.0

    def _custom_args(self):
        args = self._args()
        args["points"] = self.points
        args["fit_points"] = args["fit_points"] == "On"
        args.pop("points_count", None)
        return args

    def _calculate(self, data):
        if self.method == "Automatic":
            args = self._args()
            algorithm = args.pop("algorithm")
            if algorithm == "ALS":
                return baseline_correct(data, **args)
            if algorithm == "SNIP":
                return snip_baseline(data, iterations=args["niter"])
            return polynomial_baseline(data, degree=args["degree"])
        if self.method == "Constant":
            return constant_baseline(data, **self._args())
        return custom_baseline(data, **self._custom_args())

    def _update_preview(self, *args):
        data = self._data()
        self.canvas.upper.clear()
        self.canvas.lower.clear()
        if data is None:
            self.canvas.draw_idle()
            return
        try:
            result = self._calculate(data)
            corrected = result[0]
            baseline = data[:, 1] - corrected[:, 1]
            self.canvas.upper.plot(data[:, 0], data[:, 1], label="Spectrum")
            self.canvas.upper.plot(data[:, 0], baseline, label="Baseline", color="tab:orange")
            self.canvas.lower.plot(corrected[:, 0], corrected[:, 1], label="Corrected", color="tab:green")
            if self.method == "Custom":
                self.canvas.upper.scatter([p[0] for p in self.points], [p[1] for p in self.points], color="red", zorder=4)
            if self.residuals.isChecked():
                self.canvas.lower.plot(data[:, 0], corrected[:, 1], color="tab:red", alpha=0.35, label="Residuals")
            self.canvas.upper.legend(); self.canvas.lower.legend()
            self.canvas.upper.set_title("Spectrum and baseline"); self.canvas.lower.set_title("Baseline-corrected spectrum")
        except (ValueError, TypeError):
            pass
        self.canvas.draw_idle()

    def _refresh_points(self):
        self._persist()
        self._update_preview()

    def find_custom_points(self):
        data = self._data()
        if data is None:
            return
        count = int(self._controls["Custom"]["points_count"].value())
        indexes = np.linspace(0, len(data) - 1, count, dtype=int)
        self.points = [[float(data[i, 0]), float(data[i, 1])] for i in indexes]
        self._refresh_points()

    def save_custom_baseline(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save custom baseline", str(self.POINTS_FILE), "JSON files (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.points, indent=2), encoding="utf-8")

    def load_custom_baseline(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load custom baseline", str(self.POINTS_FILE), "JSON files (*.json)")
        if path:
            self.points = json.loads(Path(path).read_text(encoding="utf-8")); self._refresh_points()

    def _apply(self, caller):
        self._persist()
        if self.method == "Custom":
            function_args = self._custom_args(); function = custom_baseline
        else:
            function_args = self._args(); function = self._calculate_function(function_args)
        caller("Baseline", function, **function_args)

    def _calculate_function(self, args):
        if self.method == "Constant": return constant_baseline
        algorithm = args.pop("algorithm")
        return {"ALS": baseline_correct, "SNIP": snip_baseline, "Polynomial": polynomial_baseline}[algorithm]

    def apply_to_all(self):
        if self.manager: self._apply(self.manager._apply_to_all)
    def apply_to_checked(self):
        if self.manager: self._apply(self.manager._apply_to_checked)
    def apply_to_selected(self):
        self._persist(); spec = self.manager.current_spectrum() if self.manager else None
        if spec:
            args = self._custom_args() if self.method == "Custom" else self._args(); function = custom_baseline if self.method == "Custom" else self._calculate_function(args); self.manager._apply_treatment(spec, "Baseline", function, **args)
    def save_settings(self): self._persist(); self.cfg.exit_saves()
