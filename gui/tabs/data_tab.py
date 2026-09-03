"""DataTab: full-size spectra viewer with Overlay / Stacked modes.

Importing spectra is handled exclusively via File -> Open
(see gui/menu_functions.py::MenuBar_File_Open). This tab contains no file
browsing or import UI - it hosts the application's shared SpectraCanvas
(the same canvas the "Spectra / Treatments" tree's eye-icon toggles already
draw into) and lets the user choose how currently-visible spectra are laid
out.

Waterfall mode was dropped: it only ever added a small per-line X shift on
top of the same Y stacking Stacked mode already does, and in practice the
two looked close enough that keeping both just added a redundant control.
Everything below only offers Overlay and Stacked.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QDoubleSpinBox,
    QButtonGroup,
    QCheckBox,
)

from gui.widgets.spectra_manager import SpectraManagerWidget
from gui.widgets.spectra_canvas import SpectraCanvas
from models.config_manager import ConfigManager


class DataTab(QWidget):
    """Hosts the shared SpectraCanvas plus Overlay/Stacked controls."""

    statusChanged = Signal(str)
    name = "Data"
    CONFIG_KEY = "Data-Tab"

    def __init__(self, spectra_manager: SpectraManagerWidget, canvas: SpectraCanvas, parent=None):
        super().__init__(parent)
        self.spectra_manager = spectra_manager
        self.canvas = canvas
        self.cfg = ConfigManager()
        self._build_ui()
        self._connect_signals()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("View:"))

        self.btn_overlay = QPushButton("Overlay")
        self.btn_stacked = QPushButton("Stacked")
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for button in (self.btn_overlay, self.btn_stacked):
            button.setCheckable(True)
            self.mode_group.addButton(button)
            toolbar.addWidget(button)
        self.btn_overlay.setChecked(True)

        toolbar.addSpacing(16)
        toolbar.addWidget(QLabel("Y offset:"))
        self.y_offset_spin = QDoubleSpinBox()
        self.y_offset_spin.setRange(0.0, 1_000_000_000.0)
        self.y_offset_spin.setDecimals(2)
        self.y_offset_spin.setSingleStep(100.0)
        self.y_offset_spin.setEnabled(False)
        toolbar.addWidget(self.y_offset_spin)

        self.reset_offset_btn = QPushButton("Auto")
        self.reset_offset_btn.setToolTip("Recompute automatic Y offset")
        self.reset_offset_btn.setEnabled(False)
        toolbar.addWidget(self.reset_offset_btn)

        self.normalize_check = QCheckBox("Normalize each")
        self.normalize_check.setToolTip(
            "Off: each spectrum keeps its true relative intensity when stacked "
            "(a weak spectrum stays visually weak next to a strong one).\n"
            "On: every spectrum is independently scaled to the same height "
            "first, so weaker spectra's own features stay visible too - at "
            "the cost of no longer showing which spectrum was actually stronger."
        )
        self.normalize_check.setEnabled(False)
        toolbar.addWidget(self.normalize_check)

        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        layout.addWidget(self.canvas, stretch=1)

    def _connect_signals(self) -> None:
        self.btn_overlay.clicked.connect(lambda: self._set_mode("overlay"))
        self.btn_stacked.clicked.connect(lambda: self._set_mode("stacked"))
        self.y_offset_spin.valueChanged.connect(self._y_offset_changed)
        self.reset_offset_btn.clicked.connect(self._reset_offset)
        self.normalize_check.toggled.connect(self._normalize_changed)

    # ------------------------------------------------------------------- #
    # View-mode / offset handling
    # ------------------------------------------------------------------- #
    def _set_mode(self, mode: str) -> None:
        self.canvas.set_view_mode(mode)
        self._sync_controls_enabled(mode)
        self._sync_spinbox_from_canvas()
        self._save_settings()
        self.statusChanged.emit(f"View mode: {mode.title()}")

    def _y_offset_changed(self, value: float) -> None:
        self.canvas.set_y_offset(value, auto=False)
        self._save_settings()

    def _reset_offset(self) -> None:
        self.canvas.recompute_auto_offset()
        self._sync_spinbox_from_canvas()
        self._save_settings()

    def _normalize_changed(self, checked: bool) -> None:
        self.canvas.set_stack_normalize(checked)
        self._sync_spinbox_from_canvas()
        self._save_settings()

    def _sync_controls_enabled(self, mode: str) -> None:
        self.y_offset_spin.setEnabled(mode != "overlay")
        self.reset_offset_btn.setEnabled(mode != "overlay")
        self.normalize_check.setEnabled(mode != "overlay")

    def _sync_spinbox_from_canvas(self) -> None:
        self.y_offset_spin.blockSignals(True)
        self.y_offset_spin.setValue(self.canvas.get_y_offset())
        self.y_offset_spin.blockSignals(False)

    # ------------------------------------------------------------------- #
    # Persistence
    # ------------------------------------------------------------------- #
    def _save_settings(self) -> None:
        self.cfg.set_value(
            [self.CONFIG_KEY],
            {
                "ViewMode": self.canvas.get_view_mode(),
                "YOffset": self.canvas.get_y_offset(),
                "YOffsetAuto": self.canvas.get_y_offset_auto(),
                "StackNormalize": self.canvas.get_stack_normalize(),
            },
        )

    def _load_settings(self) -> None:
        settings = self.cfg.get_value([self.CONFIG_KEY]) or {}
        mode = settings.get("ViewMode", "overlay")
        if mode == "waterfall":
            # Old config from before Waterfall mode was removed - treat it
            # the same as Stacked rather than raising in set_view_mode.
            mode = "stacked"
        y_offset = settings.get("YOffset", 0.0)
        y_auto = settings.get("YOffsetAuto", True)
        normalize = settings.get("StackNormalize", False)

        mode_button = {
            "overlay": self.btn_overlay,
            "stacked": self.btn_stacked,
        }.get(mode, self.btn_overlay)
        mode_button.setChecked(True)

        self.normalize_check.blockSignals(True)
        self.normalize_check.setChecked(normalize)
        self.normalize_check.blockSignals(False)

        self.canvas.set_view_mode(mode)
        self.canvas.set_stack_normalize(normalize)
        self.canvas.set_y_offset(y_offset, auto=y_auto)
        self._sync_controls_enabled(mode)
        self._sync_spinbox_from_canvas()