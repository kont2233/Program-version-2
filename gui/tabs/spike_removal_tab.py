"""Interactive spike-removal controls and preview."""

from __future__ import annotations

from typing import Any, Dict
import numpy as np
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QPushButton, QDoubleSpinBox, QSpinBox, QSplitter,
    QPlainTextEdit, QStackedWidget, QTableWidget, QTableWidgetItem, QToolBar,
    QToolButton, QVBoxLayout, QWidget, QHeaderView,
)

from gui.widgets.spectra_canvas import SpectraCanvas
from gui.widgets.spectra_manager import SpectraManagerWidget
from models.config_manager import ConfigManager
from models.spectrum import RamanSpectrum
from treatments.spike_removal import (
    bridge_span,
    whitaker_hayes_despike,
    whitaker_hayes_scores,
)

from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector


class SpikeSelectionDialog(QDialog):
    """Full-size zoomable dialog for selecting one or more x-axis spans."""

    def __init__(self, data, title: str, selection_color: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1100, 700)
        self.data = data
        self.selection_color = selection_color
        self.spans = []
        self.figure = Figure(figsize=(12, 7))
        self.axis = self.figure.add_subplot(111)
        self.axis.plot(data[:, 0], data[:, 1], color="tab:blue", linewidth=0.9)
        self.axis.set_xlabel("Raman shift (cm-1)")
        self.axis.set_ylabel("Intensity")
        self.axis.grid(True, which="both", linestyle=":", linewidth=0.5)
        self.canvas = FigureCanvas(self.figure)
        self.selector = SpanSelector(
            self.axis,
            self._select_span,
            "horizontal",
            useblit=False,
            props={"facecolor": selection_color, "alpha": 0.3},
        )
        layout = QVBoxLayout(self)
        layout.addWidget(NavigationToolbar(self.canvas, self))
        layout.addWidget(self.canvas)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        clear_button = buttons.addButton("Clear selections", QDialogButtonBox.ResetRole)
        clear_button.clicked.connect(self._clear_selections)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_span(self, start: float, end: float) -> None:
        span = (min(start, end), max(start, end))
        if span[0] == span[1]:
            return
        self.spans.append(span)
        self.axis.axvspan(*span, color=self.selection_color, alpha=0.22)
        self.canvas.draw_idle()

    def _clear_selections(self) -> None:
        self.spans.clear()
        self.axis.clear()
        self.axis.plot(self.data[:, 0], self.data[:, 1], color="tab:blue", linewidth=0.9)
        self.axis.set_xlabel("Raman shift (cm-1)")
        self.axis.set_ylabel("Intensity")
        self.axis.grid(True, which="both", linestyle=":", linewidth=0.5)
        self.canvas.draw_idle()


class SpikeComparisonView(QWidget):
    """Side-by-side raw and despiked spectrum preview."""

    spanSelected = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(10, 4))
        self.axes = self.figure.subplots(1, 2)
        self.canvas = FigureCanvas(self.figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(NavigationToolbar(self.canvas, self))
        layout.addWidget(self.canvas)
        self.selected_range = None
        self.span_selector = SpanSelector(
            self.axes[0],
            self._span_selected,
            "horizontal",
            useblit=False,
            props={"facecolor": "tab:red", "alpha": 0.25},
        )

    def _span_selected(self, start: float, end: float) -> None:
        self.selected_range = (min(start, end), max(start, end))
        self.spanSelected.emit(*self.selected_range)
        self.canvas.draw_idle()

    def clear(self) -> None:
        self.selected_range = None
        for axis in self.axes:
            axis.clear()
            axis.set_axis_off()
        self.canvas.draw_idle()

    def show_comparison(
        self, raw, processed, name: str, raw_title: str = "Selected input",
        protected_ranges=None,
    ) -> None:
        for axis, data, title in zip(
            self.axes, (raw, processed), (raw_title, "Processed preview")
        ):
            axis.clear()
            axis.plot(data[:, 0], data[:, 1], linewidth=0.8)
            axis.set_title(title)
            axis.set_xlabel("Raman shift (cm-1)")
            axis.set_ylabel("Intensity")
            axis.grid(True, which="both", linestyle=":", linewidth=0.5)
            if self.selected_range is not None:
                axis.axvspan(*self.selected_range, color="tab:red", alpha=0.2)
            for protected_range in protected_ranges or []:
                axis.axvspan(*protected_range, color="tab:green", alpha=0.18)
        self.figure.suptitle(name)
        self.figure.tight_layout()
        self.canvas.draw_idle()


class SpikeRemovalTab(QWidget):
    """Configure, preview, and apply spike-removal methods."""

    NAME = "Spike Removal"
    METHODS = ("Whitaker-Hayes",)

    def __init__(self, manager=None, canvas=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.canvas = canvas
        self.cfg = ConfigManager()
        self.protected_spans = []
        self._controls: Dict[str, Dict[str, QWidget]] = {}
        self._methods = (whitaker_hayes_despike,)
        self._build_ui()
        self._select_method(0)
        if self.manager is not None:
            self.manager.dataset_selected.connect(self._show_selected_dataset)

    def _show_selected_spectrum(self, spec: RamanSpectrum | None) -> None:
        self._show_selected_dataset(spec, "raw")

    def _show_selected_dataset(self, spec: RamanSpectrum | None, dataset: str) -> None:
        same_selection = (
            spec is getattr(self, "_selected_spec", None)
            and dataset == getattr(self, "_selected_dataset", None)
        )
        self.comparison_view.clear()
        if not same_selection:
            self.protected_spans = []
        if spec is None:
            self._update_preview(None)
            return
        self._selected_spec = spec
        self._set_dataset_combo(spec, dataset)
        source = spec.current if dataset == "current" else spec.get_step_data(dataset)
        self._update_preview(spec, source, dataset)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        settings = QWidget()
        splitter = QSplitter(Qt.Vertical)
        self.comparison_view = SpikeComparisonView()
        splitter.addWidget(self.comparison_view)
        splitter.addWidget(settings)
        splitter.setSizes([560, 340])
        root.addWidget(splitter)
        settings_layout = QVBoxLayout(settings)

        toolbar = QToolBar("Spike removal actions", settings)
        toolbar.setIconSize(QSize(18, 18))
        self._add_action(toolbar, "Apply to all", self.apply_to_all, "apply_icon.png")
        self._add_action(toolbar, "Apply to selected", self.apply_to_selected, "Apply_selected_icon.png")
        self._add_action(toolbar, "Apply to checked", self.apply_to_checked, "Apply_selected_icon.png")
        self._add_action(toolbar, "Save settings", self.save_settings, "save_icon.png")
        settings_layout.addWidget(toolbar)

        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Spectrum to despike:"))
        self.dataset_combo = QComboBox()
        self.dataset_combo.currentIndexChanged.connect(self._dataset_changed)
        source_layout.addWidget(self.dataset_combo)
        mark_button = QPushButton("Mark protected areas")
        mark_button.clicked.connect(self.mark_protected_areas)
        source_layout.addWidget(mark_button)
        manual_button = QPushButton("Manual despiking")
        manual_button.clicked.connect(self.manual_despiking)
        source_layout.addWidget(manual_button)
        settings_layout.addLayout(source_layout)

        controls_splitter = QSplitter(Qt.Horizontal)
        self.method_list = QListWidget()
        self.method_list.addItems(self.METHODS)
        self.method_list.setMaximumWidth(190)
        self.method_list.currentRowChanged.connect(self._select_method)
        controls_splitter.addWidget(self.method_list)

        self.parameter_stack = QStackedWidget()
        self._create_method_page(
            "Whitaker-Hayes",
            (
                ("threshold", "Z-score threshold", 0.1, 100.0, 0.1, 7.0),
                ("window", "Correction window", 1, 101, 2, 5),
            ),
        )
        controls_splitter.addWidget(self.parameter_stack)
        settings_layout.addWidget(controls_splitter)

        explanation = QPlainTextEdit()
        explanation.setReadOnly(True)
        explanation.setMaximumHeight(115)
        explanation.setPlainText(
            "Whitaker-Hayes despiking\n"
            "The algorithm evaluates the first-difference signal rather than raw intensity. "
            "A genuine Raman band rises and falls across several samples, while a cosmic-ray "
            "spike produces an abrupt jump. Points whose modified z-score exceeds the threshold "
            "are grouped into spans. Each flagged point is replaced by the mean of unprotected, "
            "unflagged neighbours inside the correction window.\n\n"
            "Protected areas are excluded from detection. Automatic corrections and manual "
            "bridges are recorded in the event table with their wavenumber range, raw values, "
            "corrected values, origin, and status."
        )
        settings_layout.addWidget(explanation)

        self.diagnostics_label = QLabel("Select a spectrum to view diagnostics.")
        self.diagnostics_label.setWordWrap(True)
        settings_layout.addWidget(self.diagnostics_label)

        self.events_table = QTableWidget(0, 5)
        self.events_table.setHorizontalHeaderLabels(
            ["Event", "Origin", "Wavenumber range", "Points", "Status"]
        )
        self.events_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        settings_layout.addWidget(self.events_table)

    def _add_action(self, toolbar, text: str, callback, icon_name: str) -> None:
        button = QPushButton(text)
        button.setIcon(QIcon(f"resources/icons/{icon_name}"))
        button.clicked.connect(callback)
        toolbar.addWidget(button)

    def _create_method_page(self, method: str, fields) -> None:
        page = QWidget()
        form = QFormLayout(page)
        controls: Dict[str, QWidget] = {}
        for name, label, minimum, maximum, step, fallback in fields:
            if name == "window":
                control = QSpinBox()
                control.setRange(int(minimum), int(maximum))
                control.setSingleStep(int(step))
            else:
                control = QDoubleSpinBox()
                control.setRange(minimum, maximum)
                control.setSingleStep(step)
                control.setDecimals(2)
            control.setValue(self.cfg.get_default_value([self.NAME, method, name], fallback))
            control.valueChanged.connect(self._arguments_changed)
            default_button = QToolButton()
            default_button.setText("↺")
            default_button.setToolTip(f"Restore default {label}")
            default_button.clicked.connect(lambda checked=False, m=method, n=name, c=control: self._restore_default(m, n, c))
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(control)
            row_layout.addWidget(default_button)
            form.addRow(QLabel(label), row)
            controls[name] = control
        self._controls[method] = controls
        self.parameter_stack.addWidget(page)

    @property
    def method(self) -> str:
        return self.METHODS[self.method_list.currentRow()]

    def _select_method(self, index: int) -> None:
        if index < 0:
            return
        self.parameter_stack.setCurrentIndex(index)
        if self.method in self._controls:
            self._persist_arguments()
        self._refresh_current_preview()

    def _restore_default(self, method: str, name: str, control: QWidget) -> None:
        value = self.cfg.get_default_value([self.NAME, method, name])
        if value is not None:
            control.setValue(value)

    def _arguments_changed(self, value: Any) -> None:
        self._persist_arguments()
        self._refresh_current_preview()

    def _refresh_current_preview(self) -> None:
        spec = self.manager.current_spectrum() if self.manager else None
        source = getattr(self, "_selected_source", None)
        dataset = getattr(self, "_selected_dataset", "raw")
        self._update_preview(spec, source, dataset)

    def _arguments(self) -> Dict[str, Any]:
        return {name: control.value() for name, control in self._controls[self.method].items()}

    def _persist_arguments(self) -> None:
        if self.method_list.currentRow() >= 0 and self.method in self._controls:
            self.cfg.set_value([self.NAME, self.method], self._arguments())

    def _update_preview(self, spec: RamanSpectrum | None, source=None, dataset: str = "raw") -> None:
        if spec is None:
            self.comparison_view.clear()
            self.diagnostics_label.setText("Select a spectrum to view diagnostics.")
            self.events_table.setRowCount(0)
            return
        try:
            source = spec.current if source is None else source
            self._selected_source = source
            self._selected_dataset = dataset
            protect_mask = self._protect_mask(source)
            result = self._methods[self.method_list.currentRow()](
                source, protect_mask=protect_mask, **self._arguments()
            )
            self._render_result(spec, source, result, dataset)
        except (TypeError, ValueError):
            self.comparison_view.clear()
            self.events_table.setRowCount(0)
            return

    def _render_result(self, spec: RamanSpectrum, source, result, dataset: str = "raw") -> None:
        processed, parameters = result[0], result[5]
        title = "Raw spectrum" if dataset == "raw" else f"Selected: {dataset}"
        self.comparison_view.show_comparison(
            source, processed, spec.name, title, self.protected_spans
        )
        protect_mask = self._protect_mask(source)
        scores = whitaker_hayes_scores(source, protect_mask=protect_mask)
        spike_log = parameters.get("spike_log", [])
        max_score = float(max(abs(scores))) if scores.size else 0.0
        corrected_points = sum(
            event["index_end"] - event["index_start"] + 1
            for event in spike_log
        )
        self.diagnostics_label.setText(
            f"Threshold: {parameters.get('threshold', 0):.2f} | "
            f"Maximum absolute score: {max_score:.2f} | "
            f"Corrected points: {corrected_points} | "
            f"Corrected spans: {len(spike_log)}"
        )
        self._populate_events(spike_log)

    def _protect_mask(self, source):
        if not self.protected_spans:
            return None
        mask = np.zeros(len(source), dtype=bool)
        for start, end in self.protected_spans:
            mask |= (source[:, 0] >= start) & (source[:, 0] <= end)
        return mask

    def _populate_events(self, events) -> None:
        self.events_table.setRowCount(len(events))
        for row, event in enumerate(events):
            values = (
                event["event_id"],
                event["origin"],
                f"{event['wavenumber_start']:.2f} - {event['wavenumber_end']:.2f}",
                str(event["index_end"] - event["index_start"] + 1),
                event["status"],
            )
            for column, value in enumerate(values):
                self.events_table.setItem(row, column, QTableWidgetItem(value))

    def clear_protection(self) -> None:
        self.protected_spans = []
        self._refresh_current_preview()

    def _set_dataset_combo(self, spec: RamanSpectrum, selected: str) -> None:
        self.dataset_combo.blockSignals(True)
        self.dataset_combo.clear()
        for dataset in spec.datasets:
            self.dataset_combo.addItem("Raw" if dataset == "raw" else dataset, dataset)
        index = self.dataset_combo.findData(selected)
        self.dataset_combo.setCurrentIndex(max(index, 0))
        self.dataset_combo.blockSignals(False)

    def _dataset_changed(self, index: int) -> None:
        if index < 0 or self.manager is None:
            return
        spec = self.manager.current_spectrum()
        if spec is None:
            return
        dataset = self.dataset_combo.itemData(index)
        self.protected_spans = []
        self._update_preview(spec, spec.get_step_data(dataset), dataset)

    def _selected_source_data(self):
        return getattr(self, "_selected_source", None)

    def mark_protected_areas(self) -> None:
        """Open a full-size selector for one or more protected areas."""
        source = self._selected_source_data()
        spec = self.manager.current_spectrum() if self.manager is not None else None
        if spec is None or source is None:
            return
        dialog = SpikeSelectionDialog(source, "Mark protected areas", "tab:green", self)
        dialog.showMaximized()
        if dialog.exec() == QDialog.Accepted:
            self.protected_spans = dialog.spans
            self._refresh_current_preview()

    def manual_despiking(self) -> None:
        """Open a full-size selector over the automatically despiked result."""
        if self.manager is None:
            return
        spec = self.manager.current_spectrum()
        if spec is None:
            return
        source = self._selected_source_data()
        if source is None:
            return
        automatic = self._methods[self.method_list.currentRow()](
            source, protect_mask=self._protect_mask(source), **self._arguments()
        )
        dialog = SpikeSelectionDialog(automatic[0], "Manual despiking", "tab:red", self)
        dialog.showMaximized()
        if dialog.exec() != QDialog.Accepted or not dialog.spans:
            return
        try:
            corrected = automatic[0]
            events = list(automatic[5].get("spike_log", []))
            for start, end in dialog.spans:
                result = bridge_span(corrected, start, end)
                corrected = result[0]
                events.extend(result[5].get("spike_log", []))
            parameters = dict(automatic[5])
            parameters["spike_log"] = events
            final_result = (
                corrected, "Whitaker-Hayes + Manual", automatic[2], automatic[3],
                automatic[4], parameters,
                f"Automatic despiking followed by {len(dialog.spans)} manual correction(s).",
            )
            spec.add_step("Despiked", *final_result, merge_keys=["spike_log"])
            self.manager.save_spectra_dataset(spec)
            self.manager.update_spectrum(spec)
            self._render_result(spec, source, final_result, self._selected_dataset)
        except (TypeError, ValueError) as exc:
            self.diagnostics_label.setText(f"Manual correction failed: {exc}")

    def bridge_selected_span(self) -> None:
        """Compatibility entry point for callers using the former action."""
        self.manual_despiking()

    def refresh_from_manager(self):
        """Refresh the preview from the dataset currently selected in the manager."""
        spec = self.manager.current_spectrum() if self.manager is not None else None
        dataset = getattr(
            self, "_selected_dataset",
            self.manager.current_dataset() if self.manager is not None else "raw",
        )
        if spec is not None and dataset not in spec.datasets and dataset != "current":
            dataset = "raw"
        self._show_selected_dataset(spec, dataset)

    def apply_to_all(self) -> None:
        self._persist_arguments()
        if self.manager is not None:
            self.manager._apply_to_all("Despiked", self._methods[self.method_list.currentRow()], **self._arguments())
            self._refresh_current_preview()

    def apply_to_selected(self) -> None:
        self._persist_arguments()
        if self.manager is not None and self.manager.current_spectrum() is not None:
            spec = self.manager.current_spectrum()
            self.manager._apply_treatment(spec, "Despiked", self._methods[self.method_list.currentRow()], **self._arguments())
            self._refresh_current_preview()

    def apply_to_checked(self) -> None:
        self._persist_arguments()
        if self.manager is not None:
            self.manager._apply_to_checked("Despiked", self._methods[self.method_list.currentRow()], **self._arguments())
            self._refresh_current_preview()

    def save_settings(self) -> None:
        self._persist_arguments()
        self.cfg.exit_saves()