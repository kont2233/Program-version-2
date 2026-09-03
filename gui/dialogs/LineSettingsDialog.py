from __future__ import annotations

import typing as _t

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QWidget,
)

class LineSettingsDialog(QDialog):
    """
    A small pop‑up dialog that appears just below the button that created it.
    It lets the user edit a Matplotlib line’s appearance and returns a dictionary
    with the chosen settings when the user clicks **OK**/**Save**.

    Parameters
    ----------
    parent : QWidget | None
        The widget that owns the dialog (usually the main window).
    reference_widget : QWidget
        The widget (e.g., a QPushButton) under which the dialog should appear.
    initial_settings : dict | None
        Optional dictionary with the same keys that :func:`apply_line_settings`
        expects. If omitted a sensible default is used.

    Signals
    -------
    settingsChanged(dict)
        Emitted each time a UI element is altered – useful for live‑preview.
    """

    # Emitted with the whole settings dict whenever any widget changes
    settingsChanged = Signal(dict)

    # Human-readable combo-box labels <-> the Matplotlib linestyle codes
    # apply_line_settings()/Line2D.set_linestyle() actually expect. Also
    # accepts Matplotlib's long-form names ("solid", "dashed", ...), which
    # Line2D.get_linestyle() can return depending on how a line was styled,
    # so incoming settings normalize through _STYLE_MAP_REV before display.
    _STYLE_MAP: dict[str, str] = {
        "Solid (\u2014)": "-",
        "Dashed (- -)": "--",
        "Dash-dot (-\u00b7-)": "-.",
        "Dotted (\u00b7\u00b7\u00b7)": ":",
        "None (hidden)": "None",
    }
    _STYLE_MAP_REV: dict[str, str] = {
        "-": "Solid (\u2014)", "solid": "Solid (\u2014)",
        "--": "Dashed (- -)", "dashed": "Dashed (- -)",
        "-.": "Dash-dot (-\u00b7-)", "dashdot": "Dash-dot (-\u00b7-)",
        ":": "Dotted (\u00b7\u00b7\u00b7)", "dotted": "Dotted (\u00b7\u00b7\u00b7)",
        "None": "None (hidden)", "none": "None (hidden)",
    }

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        reference_widget: QWidget,
        initial_settings: dict | None = None,
    ) -> None:
        #super().__init__(parent, flags=Qt.Window | Qt.FramelessWindowHint)
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)          # free memory automatically

        # --------------------------------------------------------------
        # Store a copy of the initial settings (or defaults)
        # --------------------------------------------------------------
        self._settings: dict = {
            "color": [0,0,0,0],
            "linewidth": 2,
            "alpha": 1.0,
            "linestyle": "-",
            "zorder": "above",      # "above" or "below"
            "enabled": True,
        }
        if initial_settings:
            if not isinstance (initial_settings["color"], QColor):
                # to_rgba() (see get_settings_from_line in spectra_canvas.py)
                # returns floats in 0-1. QColor(r, g, b, a) expects INTEGERS
                # in 0-255, so passing the raw floats silently truncated
                # every channel to 0 or 1 - in particular alpha almost
                # always became ~1/255, making the line effectively
                # invisible the instant this dialog re-applied "color"
                # (which _emit_settings_changed does on every edit, even
                # ones that only touched linewidth/linestyle/etc). Use the
                # float constructor instead, which expects exactly this
                # 0-1 range.
                rgba = initial_settings["color"]
                initial_settings["color"] = QColor.fromRgbF(rgba[0], rgba[1], rgba[2], rgba[3])
            self._settings.update(initial_settings)

        # --------------------------------------------------------------
        # UI creation
        # --------------------------------------------------------------
        self._create_ui()
        self._populate_from_settings()

        # Position the dialog just under the reference widget
        self._position_below(reference_widget)

        # Connect OK / Cancel handling
        self.button_box.accepted.connect(self.accept)   # will close & return settings
        self.button_box.rejected.connect(self.reject)

    # ------------------------------------------------------------------
    # UI layout
    # ------------------------------------------------------------------
    def _create_ui(self) -> None:
        """Create all widgets and lay them out."""
        layout = QGridLayout(self)
        layout.setColumnStretch(1, 1)   # make column 1 expand

        # ---- Color ----------------------------------------------------
        self.color_label = QLabel("Color:")
        self.color_display = QPushButton()
        self.color_display.setFixedSize(24, 24)
        self.color_display.setFlat(True)
        self.color_display.clicked.connect(self._choose_color)
        layout.addWidget(self.color_label, 0, 0)
        layout.addWidget(self.color_display, 0, 1)

        # ---- Line width -----------------------------------------------
        self.width_label = QLabel("Line width:")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 20)
        self.width_spin.valueChanged.connect(self._emit_settings_changed)
        layout.addWidget(self.width_label, 1, 0)
        layout.addWidget(self.width_spin, 1, 1)

        # ---- Alpha (transparency) --------------------------------------
        self.alpha_label = QLabel("Alpha:")
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 100)          # map to 0.0‑1.0
        self.alpha_slider.valueChanged.connect(self._emit_settings_changed)
        layout.addWidget(self.alpha_label, 2, 0)
        layout.addWidget(self.alpha_slider, 2, 1)

        # ---- Line style ------------------------------------------------
        # A raw "-" is nearly invisible as a combo-box item (it looks like
        # blank/nothing next to "--"), which made it look like there was
        # only one real choice. Human-readable labels fix that; _STYLE_MAP
        # / _STYLE_MAP_REV translate to/from the Matplotlib codes.
        self.style_label = QLabel("Line style:")
        self.style_combo = QComboBox()
        self.style_combo.addItems(list(self._STYLE_MAP.keys()))
        self.style_combo.currentTextChanged.connect(self._emit_settings_changed)
        layout.addWidget(self.style_label, 3, 0)
        layout.addWidget(self.style_combo, 3, 1)

        # ---- Z‑order ---------------------------------------------------
        self.zorder_label = QLabel("Z‑order:")
        self.zorder_combo = QComboBox()
        self.zorder_combo.addItems(["Above all", "Below all"])
        self.zorder_combo.currentTextChanged.connect(self._emit_settings_changed)
        layout.addWidget(self.zorder_label, 4, 0)
        layout.addWidget(self.zorder_combo, 4, 1)

        # ---- Enabled ---------------------------------------------------
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.stateChanged.connect(self._emit_settings_changed)
        layout.addWidget(self.enabled_check, 5, 0, 1, 2)

        # ---- OK / Cancel -----------------------------------------------
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            orientation=Qt.Horizontal,
        )
        layout.addWidget(self.button_box, 6, 0, 1, 2)

    # ------------------------------------------------------------------
    # Positioning helper
    # ------------------------------------------------------------------
    def _position_below(self, reference_widget: QWidget) -> None:
        """
        Place the dialog just under ``reference_widget`` (taking screen geometry
        into account).  The dialog is shown **without** stealing focus from the
        main window.
        """
        # Global (screen) coordinates of the reference widget
        ref_pos: QPoint = reference_widget.mapToGlobal(QPoint(0, reference_widget.height()))
        self.move(ref_pos)

    # ------------------------------------------------------------------
    # Populate UI from the internal settings dict
    # ------------------------------------------------------------------
    def _populate_from_settings(self) -> None:
        """Set every widget to the value stored in ``self._settings``."""
        # colour
        self._set_color_display(self._settings["color"])

        # linewidth
        self.width_spin.setValue(int(self._settings["linewidth"]))

        # alpha
        self.alpha_slider.setValue(int(self._settings["alpha"] * 100))

        # line style
        self.style_combo.setCurrentText(
            self._STYLE_MAP_REV.get(self._settings["linestyle"], "Solid (\u2014)")
        )

        # z‑order
        self.zorder_combo.setCurrentText(
            "Above all" if self._settings["zorder"] == "above" else "Below all"
        )

        # enabled
        self.enabled_check.setChecked(bool(self._settings["enabled"]))

    # ------------------------------------------------------------------
    # UI callbacks
    # ------------------------------------------------------------------
    def _choose_color(self) -> None:
        """Open a QColorDialog and update the colour square."""
        init = self._settings["color"]
        color = QColorDialog.getColor(initial=init, parent=self, title="Select line colour")
        if color.isValid():
            self._settings["color"] = color
            self._set_color_display(color)
            self._emit_settings_changed()

    def _set_color_display(self, color: QColor) -> None:
        """Paint the small square with the given colour."""
        pal = self.color_display.palette()
        pal.setColor(QPalette.Button, color)
        self.color_display.setPalette(pal)
        self.color_display.setAutoFillBackground(True)

    def _emit_settings_changed(self) -> None:
        """
        Retrieve current widget values, update ``self._settings`` and
        emit ``settingsChanged`` with the complete dict.
        """
        # --- colour (already stored when colour chooser runs) ---
        # linewidth
        self._settings["linewidth"] = self.width_spin.value()
        # alpha
        self._settings["alpha"] = self.alpha_slider.value() / 100.0
        # line style
        self._settings["linestyle"] = self._STYLE_MAP.get(self.style_combo.currentText(), "-")
        # z-order
        self._settings["zorder"] = (
            "above" if self.zorder_combo.currentText() == "Above all" else "below"
        )
        # enabled
        self._settings["enabled"] = self.enabled_check.isChecked()

        # Emit a *copy* so the receiver cannot accidentally mutate our internal dict
        self.settingsChanged.emit(self._settings.copy())

    # ------------------------------------------------------------------
    # Public API – retrieve the settings after the dialog closes
    # ------------------------------------------------------------------
    def get_settings(self) -> dict:
        """
        Return a **deep copy** of the settings dict.  Call this after the dialog
        has been accepted (OK/Save) – if the dialog was rejected the dict will
        contain the last values the user selected.

        Returns
        -------
        dict
            Keys: ``color`` (QColor), ``linewidth`` (int), ``alpha`` (float),
            ``linestyle`` (str), ``zorder`` (str, ``'above'``/``'below'``),
            ``enabled`` (bool)
        """
        # Ensure we have the latest values (in case OK was pressed without a widget change)
        self._emit_settings_changed()
        return self._settings.copy()