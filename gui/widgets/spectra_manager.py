"""Spectrum collection tree and visibility/selection coordinator."""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any, Dict, List, Tuple

import numpy as np
from PySide6.QtCore import QPoint, Qt, QSize, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QMessageBox,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.widgets.spectra_canvas import SpectraCanvas
from models.config_manager import ConfigManager
from models.spectrum import RamanSpectrum

treatment_type = Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]


class _SpectraTree(QTreeWidget):
    """Tree that lets the manager handle the view-all header action."""

    def __init__(self, manager: "SpectraManagerWidget"):
        super().__init__(manager)
        self.manager = manager

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.itemAt(event.position().toPoint()) is None:
            self.manager.clear_selection()
        super().mousePressEvent(event)


class SpectraManagerWidget(QWidget):
    """Manage loaded spectra, treatment history, selection, and visibility."""

    spectrum_selected = Signal(object)
    dataset_selected = Signal(object, str)
    spectrum_item_checked_changed = Signal(object, bool)
    treatment_item_checked_changed = Signal(object, bool)

    _SPEC = Qt.UserRole
    _DATASET = Qt.UserRole + 1
    _KIND = Qt.UserRole + 2

    def __init__(self, canvas: SpectraCanvas, parent: QWidget | None = None):
        super().__init__(parent)
        self.canvas = canvas
        self.cfg = ConfigManager()
        self._spectra: List[RamanSpectrum] = []
        self._active_spectrum: RamanSpectrum | None = None
        self._active_dataset = "raw"
        self._updating_tree = False
        self._view_on = self._make_view_icon(True)
        self._view_off = self._make_view_icon(False)

        self.toolbar = self._init_toolbar()
        self.tree = _SpectraTree(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Spectra / Treatments", ""])
        self.tree.headerItem().setToolTip(1, "Show or hide all spectra")
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tree.header().setMinimumSectionSize(0)
        self.tree.header().setStyleSheet("QHeaderView::section { min-width: 0px; }")
        self.tree.header().resizeSection(1, 32)
        self.tree.header().sectionClicked.connect(self._on_header_clicked)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.canvas.spectrum_deloaded.connect(self._on_canvas_deloaded)

        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.tree)

    @staticmethod
    def _make_view_icon(enabled: bool) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor("#2d8cff" if enabled else "#9aa0a6")
        painter.setPen(color)
        painter.setBrush(color if enabled else Qt.NoBrush)
        painter.drawEllipse(2, 5, 14, 8)
        painter.setBrush(QColor("white") if enabled else color)
        painter.drawEllipse(7, 7, 4, 4)
        painter.end()
        return QIcon(pixmap)

    def _init_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Spectra manager", self)
        toolbar.setIconSize(QSize(18, 18))
        actions = (
            ("deselect.png", "Deselect all", self.deselect_all),
            ("select_all.png", "Select all", self.select_all),
            ("view_enabled.png", "Show all", self._show_all_checked),
        )
        for filename, tooltip, callback in actions:
            action = QAction(QIcon(f"resources/icons/{filename}"), "", self)
            action.setToolTip(tooltip)
            action.triggered.connect(callback)
            toolbar.addAction(action)
        return toolbar

    def add_spectrum(self, spec: RamanSpectrum) -> None:
        """Register or replace a spectrum and rebuild its tree branch."""
        existing = self._find_spectrum(spec)
        if existing is not None:
            index = self._spectra.index(existing)
            self._spectra[index] = spec
            self._remove_top_item(existing)
        else:
            self._spectra.append(spec)
        self.save_spectra_dataset(spec)
        self._add_top_item(spec, viewed=False)

    def update_spectrum(self, spec: RamanSpectrum) -> None:
        top = self._top_item(spec)
        if top is None:
            self.add_spectrum(spec)
            return
        checked = top.checkState(0)
        viewed = top.data(1, self._KIND) == "viewed"
        self._remove_top_item(spec)
        self._add_top_item(spec, checked, viewed)

    def clear(self) -> None:
        self.tree.clear()
        self._spectra.clear()
        self._active_spectrum = None

    def _add_top_item(self, spec: RamanSpectrum, checked=Qt.Checked, viewed=True):
        top = QTreeWidgetItem(self.tree)
        top.setText(0, pathlib.Path(spec.raw_path).name)
        top.setToolTip(0, str(spec.raw_path))
        top.setData(0, self._SPEC, spec)
        top.setData(1, self._SPEC, spec)
        top.setData(1, self._KIND, "viewed" if viewed else "hidden")
        top.setFlags(top.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        top.setCheckState(0, checked)
        top.setIcon(1, self._view_on if viewed else self._view_off)
        self._populate_children(top, spec)
        top.setExpanded(True)

    def _populate_children(self, top: QTreeWidgetItem, spec: RamanSpectrum) -> None:
        for record in spec.history:
            step = record.get("step_name", "")
            if step == "raw":
                continue
            treatment = self._add_dataset_item(top, step, step, record.get("description", ""))
            if step.lower().startswith("baseline"):
                for key in spec.datasets:
                    if "baseline" in key.lower() and key != step:
                        self._add_dataset_item(treatment, "Baseline", key)
            if step.lower().startswith("peak"):
                for key in spec.datasets:
                    if key != step and key.lower().startswith(("cumulative", "peak_", "peak")):
                        self._add_dataset_item(treatment, key.replace("_", " ").title(), key)

    def _add_dataset_item(self, parent, label: str, dataset: str, tooltip: str = ""):
        item = QTreeWidgetItem(parent)
        item.setText(0, label)
        item.setToolTip(0, tooltip)
        item.setData(0, self._SPEC, self._spectrum_for_item(parent))
        item.setData(0, self._DATASET, dataset)
        item.setData(1, self._KIND, "hidden")
        item.setIcon(1, self._view_off)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return item

    def _spectrum_for_item(self, item):
        while item.parent() is not None:
            item = item.parent()
        return item.data(0, self._SPEC)

    def _find_spectrum(self, spec):
        return next((candidate for candidate in self._spectra if candidate.raw_path == spec.raw_path), None)

    def _top_item(self, spec):
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.data(0, self._SPEC) is spec:
                return item
        return None

    def _remove_top_item(self, spec):
        top = self._top_item(spec)
        if top is not None:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(top))

    def _on_item_changed(self, item, column):
        if self._updating_tree or column != 0 or item.parent() is not None:
            return
        checked = item.checkState(0) == Qt.Checked
        self.spectrum_item_checked_changed.emit(item, checked)

    def _on_header_clicked(self, column: int) -> None:
        if column == 1:
            self.set_all_viewed(not self.all_viewed())

    def _on_canvas_deloaded(self, spec: RamanSpectrum) -> None:
        """Reflect lines removed directly through the canvas in the tree."""
        top = self._top_item(spec)
        if top is not None:
            top.setData(1, self._KIND, "hidden")
            top.setIcon(1, self._view_off)

    def _on_item_clicked(self, item, column):
        spec = self._spectrum_for_item(item)
        if column == 1:
            self._select_item(item, spec)
            self._toggle_view(item, spec)
            return
        self._select_item(item, spec)

    def _select_item(self, item, spec):
        self._active_spectrum = spec
        self.tree.setCurrentItem(item, 0)
        self.canvas.remove_preview()
        dataset = item.data(0, self._DATASET)
        selected_dataset = dataset or "raw"
        self._active_dataset = selected_dataset
        self.canvas.draw_dataset(spec, selected_dataset)
        self.spectrum_selected.emit(spec)
        self.dataset_selected.emit(spec, selected_dataset)

    def clear_selection(self):
        self._active_spectrum = None
        self._active_dataset = "raw"
        self.tree.clearSelection()
        self.canvas.deselect()
        self.spectrum_selected.emit(None)
        self.dataset_selected.emit(None, "raw")

    def _toggle_view(self, item, spec):
        visible = item.data(1, self._KIND) == "viewed"
        if visible:
            dataset = item.data(0, self._DATASET)
            if dataset:
                self.canvas.remove_dataset(spec, dataset)
            else:
                self.canvas.remove_spectrum(spec)
        else:
            dataset = item.data(0, self._DATASET)
            if dataset:
                self.canvas.draw_dataset(spec, dataset)
            else:
                self.canvas.draw_selected(spec)
        item.setData(1, self._KIND, "hidden" if visible else "viewed")
        item.setIcon(1, self._view_off if visible else self._view_on)

    def all_viewed(self):
        return all(self.tree.topLevelItem(i).data(1, self._KIND) == "viewed" for i in range(self.tree.topLevelItemCount()))

    def set_all_viewed(self, viewed: bool):
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            if (top.data(1, self._KIND) == "viewed") != viewed:
                self._toggle_view(top, top.data(0, self._SPEC))
        self.tree.headerItem().setIcon(1, self._view_on if viewed else self._view_off)

    def select_all(self):
        self._set_all_checked(Qt.Checked)

    def deselect_all(self):
        self._set_all_checked(Qt.Unchecked)

    def _set_all_checked(self, state):
        self._updating_tree = True
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setCheckState(0, state)
        self._updating_tree = False

    def get_checked_spectra(self) -> List[RamanSpectrum]:
        return [
            self.tree.topLevelItem(index).data(0, self._SPEC)
            for index in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(index).checkState(0) == Qt.Checked
        ]

    def current_spectrum(self) -> RamanSpectrum | None:
        return self._active_spectrum

    def current_dataset(self) -> str:
        return self._active_dataset

    def _show_all_checked(self):
        for spec in self.get_checked_spectra():
            self.canvas.draw_selected(spec)

    def _apply_to_checked(self, step_name, func, **kwargs):
        self.cfg.set_value([step_name, func.__name__], kwargs)
        for spec in self.get_checked_spectra():
            self._apply_treatment(spec, step_name, func, **kwargs)

    def _apply_to_all(self, step_name, func, **kwargs):
        self.cfg.set_value([step_name, func.__name__], kwargs)
        for spec in list(self._spectra):
            self._apply_treatment(spec, step_name, func, **kwargs)

    def _apply_treatment(self, spec, step_name, func, **kwargs):
        try:
            result: treatment_type = func(spec.current, **kwargs)
            spec.add_step(step_name, *result)
            self.save_spectra_dataset(spec)
            self.update_spectrum(spec)
        except Exception as exc:
            QMessageBox.warning(self, f"{step_name.title()} failed", f"File {spec.path.name}:\n{exc}")

    def save_spectra_dataset(self, spec):
        try:
            data = spec.get_full_dataset(["step_name + method_name", "column_header", "column_names + units", "parameters", "description"])
            output = pathlib.Path(spec.path)
            output.parent.mkdir(parents=True, exist_ok=True)
            np.savetxt(output, data, fmt="%s", delimiter=",", encoding="utf-8")
        except Exception as exc:
            print(f"Failed to save {spec.path}: {exc}")

    def _show_context_menu(self, position: QPoint):
        item = self.tree.itemAt(position)
        if item is None:
            return
        spec = self._spectrum_for_item(item)
        menu = QMenu(self)
        menu.addAction("Select", lambda: self._select_item(item, spec))
        menu.addAction("View", lambda: self._toggle_view(item, spec))
        menu.addAction("Fully disable", lambda: self._disable_spectrum(spec))
        menu.addAction("Deload", lambda: self._deload_spectrum(spec))
        if item.parent() is not None:
            menu.addAction("Remove treatment", lambda: self._remove_treatment(spec, item))
        menu.addAction("Open in explorer", lambda: os.startfile(spec.path.parent))
        menu.addAction("Show history", lambda: self._show_history(spec))
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _disable_spectrum(self, spec):
        top = self._top_item(spec)
        if top is not None and top.data(1, self._KIND) == "viewed":
            self._toggle_view(top, spec)
        if self._active_spectrum is spec:
            self._active_spectrum = None
            self.canvas.deselect()
        top = self._top_item(spec)
        if top is not None:
            self._updating_tree = True
            top.setCheckState(0, Qt.Unchecked)
            self._updating_tree = False

    def _deload_spectrum(self, spec):
        self.canvas.remove_spectrum(spec)
        self._remove_top_item(spec)
        if spec in self._spectra:
            self._spectra.remove(spec)
        if self._active_spectrum is spec:
            self._active_spectrum = None

    def _remove_treatment(self, spec, item):
        dataset = item.data(0, self._DATASET) or item.text(0)
        spec.datasets.pop(dataset, None)
        spec.history = [record for record in spec.history if record.get("step_name") != dataset]
        self.update_spectrum(spec)

    def _show_history(self, spec):
        QMessageBox.information(self, "Spectrum history", json.dumps(spec.history, indent=2, default=str))
