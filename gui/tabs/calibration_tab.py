"""Manual and reference-based Raman x-axis calibration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import find_peaks
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QListWidget, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QToolBar, QToolButton, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from gui.widgets.spectra_manager import SpectraManagerWidget
from models.config_manager import ConfigManager
from models.spectrum import RamanSpectrum
from treatments.calibration import calibrate


class _ReferenceDropWidget(QLabel):
    """Accept a reference spectrum dropped from the file manager."""

    def __init__(self, callback, parent=None):
        super().__init__("Drop a reference spectrum here or use Load file")
        self.callback = callback
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(48)
        self.setStyleSheet("border: 1px dashed #888; padding: 8px;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.callback(urls[0].toLocalFile())
            event.acceptProposedAction()


class CalibrationCanvas(FigureCanvas):
    """Reference/calibration plot with draggable manual calibration."""

    def __init__(self, owner):
        self.figure = Figure(figsize=(6, 4))
        super().__init__(self.figure)
        self.owner = owner
        self.axes = self.figure.add_subplot(111)
        self._drag_x = None
        self.mpl_connect("button_press_event", self._press)
        self.mpl_connect("motion_notify_event", self._move)
        self.mpl_connect("button_release_event", self._release)
        self.mpl_connect("button_press_event", self._context)

    def _press(self, event):
        if event.button == 1 and event.inaxes is self.axes:
            self._drag_x = event.xdata

    def _move(self, event):
        if self._drag_x is None or event.xdata is None or event.inaxes is not self.axes:
            return
        delta = event.xdata - self._drag_x
        self._drag_x = event.xdata
        self.owner.intercept.setValue(self.owner.intercept.value() + delta)

    def _release(self, event):
        self._drag_x = None

    def _context(self, event):
        if event.button != 3 or event.inaxes is not self.axes:
            return
        if self.owner.detected_peaks:
            nearest = min(self.owner.detected_peaks, key=lambda x: abs(x - event.xdata))
            if abs(nearest - event.xdata) <= self.owner.peak_tolerance.value():
                self.owner.detected_peaks.remove(nearest)
                self.owner._refresh_reference()
                self.owner._update_plot()

    def contextMenuEvent(self, event):
        menu = self.owner._plot_menu()
        menu.exec(event.globalPos())


class CalibrationTab(QWidget):
    """Calibrate Raman shift axes manually or against a reference standard."""

    NAME = "Calibration"
    METHODS = ("Manual", "Reference")
    STANDARD_FILE = Path(__file__).resolve().parents[2] / "config" / "calibration_standards.json"

    def __init__(self, manager: SpectraManagerWidget | None = None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.cfg = ConfigManager()
        self.standards = self._load_standards()
        self.detected_peaks: list[float] = []
        self.reference_data: np.ndarray | None = None
        self._auto_select_standard = True
        self._build_ui()
        if self.manager is not None:
            self.manager.spectrum_selected.connect(self._on_spectrum_selected)

    def _load_standards(self):
        try:
            with self.STANDARD_FILE.open(encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, json.JSONDecodeError):
            return {}

    def _build_ui(self):
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical)
        upper = QWidget()
        upper_layout = QHBoxLayout(upper)
        self.plot = CalibrationCanvas(self)
        upper_layout.addWidget(self.plot, 2)
        self.equation = QLabel("No calibration calculated")
        self.equation.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        upper_layout.addWidget(self.equation, 1)
        splitter.addWidget(upper)
        settings = QWidget()
        settings_layout = QVBoxLayout(settings)
        toolbar = QToolBar("Calibration actions", settings)
        self._action(toolbar, "Apply to all", self.apply_to_all, "apply_icon.png")
        self._action(toolbar, "Apply to selected", self.apply_to_selected, "Apply_selected_icon.png")
        self._action(toolbar, "Apply to checked", self.apply_to_checked, "Apply_selected_icon.png")
        self._action(toolbar, "Save settings", self.save_settings, "save_icon.png")
        settings_layout.addWidget(toolbar)
        self.method_combo = QComboBox()
        self.method_combo.addItems(self.METHODS)
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        settings_layout.addWidget(self.method_combo)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._manual_page())
        self.stack.addWidget(self._reference_page())
        settings_layout.addWidget(self.stack)
        splitter.addWidget(settings)
        splitter.setSizes([600, 300])
        root.addWidget(splitter)

    def _action(self, toolbar, text, callback, icon):
        button = QPushButton(text)
        button.setIcon(QIcon(f"resources/icons/{icon}"))
        button.clicked.connect(callback)
        toolbar.addWidget(button)

    def _manual_page(self):
        page = QWidget()
        form = QFormLayout(page)
        self.slope = self._number("a", 1.0, -100.0, 100.0, 0.0001)
        self.intercept = self._number("b", 0.0, -10000.0, 10000.0, 0.01)
        form.addRow("a (scale)", self._with_default(self.slope, [self.NAME, "Manual", "slope"], 1.0))
        form.addRow("b (offset)", self._with_default(self.intercept, [self.NAME, "Manual", "intercept"], 0.0))
        self.slope.valueChanged.connect(self._arguments_changed)
        self.intercept.valueChanged.connect(self._arguments_changed)
        return page

    def _reference_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        drop = _ReferenceDropWidget(self.load_reference)
        layout.addWidget(drop)
        load = QPushButton("Load reference file")
        load.clicked.connect(self._choose_reference)
        layout.addWidget(load)
        form = QFormLayout()
        self.prominence = self._number("prominence", 0.05, 0.0, 1e9, 0.05)
        self.distance = QSpinBoxWithDefault(1, 10000, 5)
        self.peak_tolerance = self._number("tolerance", 0.0, 100.0, 0.5, 5.0)
        form.addRow("Prominence", self._with_default(self.prominence, [self.NAME, "Reference", "prominence"], 0.05))
        form.addRow("Minimum distance", self._with_default(self.distance, [self.NAME, "Reference", "distance"], 5))
        form.addRow("Peak tolerance", self._with_default(self.peak_tolerance, [self.NAME, "Reference", "tolerance"], 5.0))
        layout.addLayout(form)
        self.standard_combo = QComboBox()
        self.standard_combo.addItems(self.standards.keys())
        self.standard_combo.currentTextChanged.connect(self._standard_changed)
        layout.addWidget(self.standard_combo)
        self.source_label = QLabel("Source: none")
        layout.addWidget(self.source_label)
        self.peaks_table = QTableWidget(0, 2)
        self.peaks_table.setHorizontalHeaderLabels(["Detected", "Theoretical"])
        layout.addWidget(self.peaks_table)
        return page

    def _number(self, name, value, minimum, maximum, step):
        control = QDoubleSpinBox()
        control.setObjectName(name)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(4)
        control.setValue(value)
        control.valueChanged.connect(self._arguments_changed)
        return control

    def _with_default(self, control, path, fallback):
        default = self.cfg.get_default_value(path, fallback)
        control.setValue(default)
        button = QToolButton()
        button.setText("Reset")
        button.setToolTip("Restore default value")
        button.clicked.connect(lambda: control.setValue(self.cfg.get_default_value(path, fallback)))
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(control)
        layout.addWidget(button)
        return row

    def _method_changed(self, index):
        self.stack.setCurrentIndex(index)
        self._persist()
        self._update_plot()

    def _standard_changed(self, name):
        self._auto_select_standard = False
        self._refresh_reference()

    def _arguments_changed(self, value):
        self._persist()
        self._update_plot()

    def _persist(self):
        if self.method_combo.currentIndex() == 0:
            self.cfg.set_value([self.NAME, "Manual"], {"slope": self.slope.value(), "intercept": self.intercept.value()})
        else:
            self.cfg.set_value([self.NAME, "Reference"], {"prominence": self.prominence.value(), "distance": self.distance.value(), "tolerance": self.peak_tolerance.value()})

    @property
    def method(self):
        return self.method_combo.currentText()

    def _on_spectrum_selected(self, spec):
        if spec is not None:
            self._update_plot(spec.current)

    def _update_plot(self, data=None):
        if data is None and self.manager is not None and self.manager.current_spectrum() is not None:
            data = self.manager.current_spectrum().current
        self.plot.axes.clear()
        if data is not None:
            result = calibrate(data, self.slope.value(), self.intercept.value())[0]
            self.plot.axes.plot(data[:, 0], data[:, 1], label="Spectrum")
            self.plot.axes.plot(result[:, 0], result[:, 1], label="Calibrated", alpha=0.7)
        if self.reference_data is not None:
            self.plot.axes.plot(self.reference_data[:, 0], self.reference_data[:, 1], label="Reference", alpha=0.7)
        if self.detected_peaks:
            self.plot.axes.scatter(self.detected_peaks, [self._reference_intensity(x) for x in self.detected_peaks], color="red", zorder=4)
        self.plot.axes.legend(loc="best")
        self.plot.axes.set_xlabel("Raman shift (cm-1)")
        self.plot.axes.set_ylabel("Intensity")
        self.plot.draw_idle()
        r_value = self._fit_r_value()
        self.equation.setText(f"x' = {self.slope.value():.6g} x + {self.intercept.value():.6g}\nR = {r_value:.5f}")

    def _choose_reference(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load calibration reference", filter="Text files (*.txt *.csv);;All files (*)")
        if path:
            self.load_reference(path)

    def load_reference(self, path):
        try:
            try:
                self.reference_data = np.loadtxt(path, delimiter=",")
            except ValueError:
                self.reference_data = np.loadtxt(path, delimiter="\t")
            if self.reference_data.ndim != 2 or self.reference_data.shape[1] < 2:
                raise ValueError("Reference must contain two numeric columns")
            self.reference_data = self.reference_data[:, :2]
            self._auto_select_standard = True
            self._refresh_reference()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Reference load failed", str(exc))

    def _refresh_reference(self):
        if self.reference_data is None:
            return
        peaks, _ = find_peaks(self.reference_data[:, 1], prominence=self.prominence.value(), distance=int(self.distance.value()))
        self.detected_peaks = list(self.reference_data[peaks, 0])
        selected = self._best_standard() if self._auto_select_standard else self.standard_combo.currentText()
        if self._auto_select_standard:
            self.standard_combo.blockSignals(True)
            self.standard_combo.setCurrentText(selected)
            self.standard_combo.blockSignals(False)
        if selected in self.standards:
            theoretical = self.standards[selected]["peaks"]
            if len(self.detected_peaks) >= 2:
                slope, intercept = np.polyfit(self.detected_peaks[:len(theoretical)], theoretical[:len(self.detected_peaks)], 1)
                self.slope.setValue(float(slope))
                self.intercept.setValue(float(intercept))
            self.source_label.setText(f"Source: {selected} | DOI: {self.standards[selected]['doi']}")
        self.peaks_table.setRowCount(min(len(self.detected_peaks), len(self.standards.get(selected, {}).get("peaks", []))))
        for row in range(self.peaks_table.rowCount()):
            self.peaks_table.setItem(row, 0, QTableWidgetItem(f"{self.detected_peaks[row]:.4f}"))
            self.peaks_table.setItem(row, 1, QTableWidgetItem(f"{self.standards[selected]['peaks'][row]:.4f}"))
        self._update_plot()

    def _best_standard(self):
        if not self.detected_peaks:
            return self.standard_combo.currentText()
        def score(name):
            theoretical = np.asarray(self.standards[name].get("peaks", []), dtype=float)
            count = min(len(self.detected_peaks), len(theoretical))
            if count < 2:
                return float("inf")
            slope, intercept = np.polyfit(self.detected_peaks[:count], theoretical[:count], 1)
            residual = np.mean(np.abs((slope * np.asarray(self.detected_peaks[:count]) + intercept) - theoretical[:count]))
            return residual + abs(len(self.detected_peaks) - len(theoretical)) * self.peak_tolerance.value()
        return min(self.standards, key=score, default=self.standard_combo.currentText())

    def _fit_r_value(self):
        if len(self.detected_peaks) < 2:
            return 0.0
        theoretical = self.standards.get(self.standard_combo.currentText(), {}).get("peaks", [])
        count = min(len(self.detected_peaks), len(theoretical))
        if count < 2:
            return 0.0
        return float(np.corrcoef(self.detected_peaks[:count], theoretical[:count])[0, 1])

    def _reference_intensity(self, x):
        if self.reference_data is None:
            return 0
        return float(np.interp(x, self.reference_data[:, 0], self.reference_data[:, 1]))

    def _plot_menu(self):
        menu = QMenu(self)
        menu.addAction("Save As txt", self._save_txt)
        menu.addAction("Save As jpg", self._save_jpg)
        return menu

    def _save_txt(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save calibration", filter="Text files (*.txt)")
        if path:
            Path(path).write_text(self.equation.text() + "\n", encoding="utf-8")

    def _save_jpg(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save calibration plot", filter="JPEG files (*.jpg)")
        if path:
            self.plot.figure.savefig(path, format="jpg", dpi=200)

    def _arguments(self):
        if self.method == "Manual":
            return {"slope": self.slope.value(), "intercept": self.intercept.value()}
        return {"slope": self.slope.value(), "intercept": self.intercept.value()}

    def apply_to_all(self):
        self._persist()
        if self.manager:
            self.manager._apply_to_all("Calibration", calibrate, **self._arguments())

    def apply_to_selected(self):
        self._persist()
        if self.manager and self.manager.current_spectrum():
            self.manager._apply_treatment(self.manager.current_spectrum(), "Calibration", calibrate, **self._arguments())

    def apply_to_checked(self):
        self._persist()
        if self.manager:
            self.manager._apply_to_checked("Calibration", calibrate, **self._arguments())

    def save_settings(self):
        self._persist()
        self.cfg.exit_saves()


class QSpinBoxWithDefault(QDoubleSpinBox):
    """Integer-valued spin box with a stable numeric API."""

    def __init__(self, minimum, maximum, value):
        super().__init__()
        self.setDecimals(0)
        self.setRange(minimum, maximum)
        self.setSingleStep(1)
        self.setValue(value)
