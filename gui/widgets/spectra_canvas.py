import os
import sys
import subprocess
from datetime import datetime
import csv
from PySide6.QtWidgets import (
    QToolBar,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QFileDialog,
    QColorDialog,
    QPlainTextEdit,
    QDialog,
    QDialogButtonBox,
    QWidget,
)
from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt, QPoint, Signal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backend_bases import MouseButton
from matplotlib.colors import to_rgba
from typing import Optional, Dict, Any, Callable, List
import numpy as np
import matplotlib.pyplot as plt

from models.spectrum import RamanSpectrum
from gui.widgets.IconButton import IconButton
from gui.status_bar import StatusBar
from models.config_manager import ConfigManager
from gui.dialogs.LineSettingsDialog import LineSettingsDialog
from gui.dialogs.LegendSettingsDialog import LegendSettingsDialog


class SpectraCanvas(QWidget):
    """Widget for displaying spectra using matplotlib."""

    selectedLineChanged = Signal(RamanSpectrum)
    spectrum_deloaded = Signal(RamanSpectrum)
    NAME = "Spectra-Canvas"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._active_line: Optional[plt.Line2D] = None
        self.preview: plt.Line2D = None
        self.cfg: ConfigManager = ConfigManager()
        self.prev_settings: Dict[str, Any] = self.cfg.get_value(path=[self.NAME, "prev_settings"])
        self.line_spectra: Dict[plt.Line2D, RamanSpectrum] = {}
        self._view_mode: str = "overlay"   # "overlay" | "stacked"
        self._y_offset: float = 0.0
        self._y_offset_auto: bool = True
        self._stack_normalize: bool = False  # False: true relative intensities: True: each line scaled to its own unit height
        self._line_original: Dict[plt.Line2D, tuple] = {}  # line -> (orig_x, orig_y) ndarrays
        self._ylabel_text: str = "Intensity (a.u.)"  # remembered across stacked/overlay switches
        # Autoscale is normally re-applied every time a line is added/removed
        # (see _reflow). Once the user manually zooms, that would silently
        # snap their view back to "fit everything" on the next unrelated
        # change (toggling a spectrum's visibility, etc) - which is why
        # Zoom In/Out used to look like they "didn't work". This flag is set
        # by _zoom() and cleared by the explicit Rescale/Reset buttons.
        self._autoscale_locked_by_user: bool = False
        self._legend_visible: bool = True
        self._legend_font_size: int = 10
        self._legend_title: str = ""
        self.status: StatusBar | None = parent.findChild(StatusBar) if parent is not None else None
        self._build_ui()
        self.menu = QMenu()
        self._build_context_menu()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QToolBar()
        toolbar.height = 20
        layout.addWidget(toolbar)

        self.btn_rescale_x = IconButton("Rescale X", "resources/icons/rescale_x.png")
        self.btn_rescale_x.setToolTip(
            "Fit the X axis to all currently plotted data (Matplotlib's default "
            "~5% margin). Keeps the current Y range and clears any manual zoom."
        )
        self.btn_rescale_y = IconButton("Rescale Y", "resources/icons/rescale_y.png")
        self.btn_rescale_y.setToolTip(
            "Fit the Y axis to all currently plotted data (~5% margin). "
            "Keeps the current X range and clears any manual zoom."
        )
        self.btn_rescale_xy = IconButton("Rescale XY", "resources/icons/rescale_xy.png")
        self.btn_rescale_xy.setToolTip(
            "Fit both axes to all currently plotted data (~5% margin) and "
            "clear any manual zoom."
        )
        self.btn_reset = IconButton("Reset View", "resources/icons/reset_view.png")
        self.btn_reset.setToolTip("Same as Rescale XY: fit both axes to all visible data.")
        self.btn_zoom_in = IconButton("Zoom In", "resources/icons/zoom_in.png")
        self.btn_zoom_in.setToolTip("Zoom in 20% around the centre of the current view.")
        self.btn_zoom_out = IconButton("Zoom Out", "resources/icons/zoom_out.png")
        self.btn_zoom_out.setToolTip("Zoom out 25% around the centre of the current view.")
        self.btn_line_style = IconButton("Line Style", "resources/icons/preview_settings.png")
        self.btn_line_style.setToolTip(
            "Edit colour, width, style, transparency and z-order of the "
            "currently selected line. Click a line in the plot first."
        )
        self.btn_flip_x = IconButton("Flip X", "resources/icons/flip_x.png")
        self.btn_flip_x.setToolTip("Invert the X axis direction.")
        self.btn_save_image = IconButton("Save Image", "resources/icons/save_icon.png")
        self.btn_save_image.setToolTip("Export the plot exactly as shown to PNG/JPEG/PDF/SVG.")
        self.btn_axis_labels = IconButton("Axis Labels", "resources/icons/explorer.png")
        self.btn_axis_labels.setToolTip("Edit the plot title and X/Y axis label text.")
        self.btn_legend = IconButton("Legend", "resources/icons/select.png")
        self.btn_legend.setToolTip(
            "Show/hide the legend, resize its text, give it a title, or "
            "rename individual entries. Drag it with the mouse to reposition."
        )
        for btn in (
            self.btn_rescale_x,
            self.btn_rescale_y,
            self.btn_rescale_xy,
            self.btn_reset,
            self.btn_zoom_in,
            self.btn_zoom_out,
            self.btn_line_style,
            self.btn_flip_x,
            self.btn_save_image,
            self.btn_axis_labels,
            self.btn_legend,
        ):
            toolbar.addWidget(btn)

        self.fig = plt.figure(figsize=(5, 4))
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Raman Shift (cm$^{-1}$)")
        self.ax.set_ylabel("Intensity (a.u.)")
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        if not hasattr(self.ax, "_dblclick_line_cid"):
                        cid = self.ax.figure.canvas.mpl_connect("pick_event", self._on_pick)
                        self.ax._dblclick_line_cid = cid   # type: ignore[attr-defined]
                        self.ax.figure.canvas.mpl_connect("button_press_event", self._on_right_click)
                        self.ax.figure.canvas.mpl_connect("button_press_event", self._on_canvas_click)
    def _build_context_menu(self):
        menu = self.menu
        menu.addAction("Select colour…", self._select_colour)
        menu.addSeparator()
        menu.addAction("Select", self._select)
        menu.addAction("Deselect", self._deselect)
        menu.addAction("Deload (remove)", self._deload)
        menu.addSeparator()
        menu.addAction("Apply treatment", self._apply_treatment)
        menu.addSeparator()
        menu.addAction("Save as…", self._save_as)
        menu.addAction("Open in Explorer", self._open_in_explorer)
        menu.addSeparator()
        menu.addAction("Show history", self._show_history)

    def _connect_signals(self) -> None:
        self.btn_rescale_x.clicked.connect(self.rescale_x)
        self.btn_rescale_y.clicked.connect(self.rescale_y)
        self.btn_rescale_xy.clicked.connect(self.rescale_xy)
        self.btn_reset.clicked.connect(self.reset_view)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_line_style.clicked.connect(self.edit_line_style)
        self.btn_flip_x.clicked.connect(self.flip_x)
        self.btn_save_image.clicked.connect(self.save_image)
        self.btn_axis_labels.clicked.connect(self.edit_axis_labels)
        self.btn_legend.clicked.connect(self.edit_legend)

    def _on_pick(self, event):
        line = event.artist
        mouse_evt = event.mouseevent
        if line is None or mouse_evt is None:
            self.deselect()
            return
        else:
            self.select_line(line)
        if getattr(mouse_evt, "dblclick", False):
            if hasattr(line, "get_color"):
                current_color = line.get_color()
            else:
                current_color = "#1f77b4"
            new_color = pick_colour(initial=current_color)
            line.set_color(new_color)
            if new_color:
                line.set_color(new_color)
                self.canvas.draw_idle()
                self._status(f"Changed colour for {line.get_label()} to {new_color}")
            line.figure.canvas.draw_idle()

    def _on_right_click(self, mouse_event: Any) -> None:
            if mouse_event.button != MouseButton.RIGHT:
                return

            lns = self.ax.get_lines()
            for ln in lns:
                contains, _ = ln.contains(mouse_event)
                if contains:
                    self._active_line = ln
                    self.status.set_status(f"Line: {ln.get_label()}")
                    break
            else:
                return

            widget = self  # type: ignore[attr-defined]
            global_x = widget.mapToGlobal(QPoint(0, 0)).x()
            global_y = widget.mapToGlobal(QPoint(0, 0)).y()
            click_x = int(global_x + mouse_event.x)
            click_y = int(global_y + mouse_event.y)

            self.menu.popup(QPoint(click_x, click_y))

    def _on_canvas_click(self, mouse_event: Any) -> None:
        """Clear selection when a normal click lands away from every line."""
        if mouse_event.button != MouseButton.LEFT:
            return
        for line in self.ax.get_lines():
            contains, _ = line.contains(mouse_event)
            if contains:
                return
        self.deselect()

    def select_line(self, line):
            if line is None:
                self.deselect()
                return
            if self._active_line != line:
                self.remove_preview()
            self._active_line = line
            self.selectedLineChanged.emit(self.get_spectra_from_line(line))
            self.highlight_line(self._active_line)
            print(f"selected Line is {self.get_spectra_from_line(line)._name}")

    def highlight_line(self, line):
        """Highlight a specific line in the plot."""
        for l in self.ax.get_lines():
            if l == line:
                l.set_linewidth(2.0)
                l.set_alpha(1.0)
            else:
                l.set_linewidth(1)
                l.set_alpha(0.5)
        apply_line_settings(self.preview, self.prev_settings)
        self.canvas.draw_idle()

    def deselect(self) -> None:
        self.remove_preview()
        self._active_line = None
        self.no_highlight()

    def no_highlight(self):
        for l in self.ax.get_lines():
                l.set_linewidth(1)
                l.set_alpha(1.0)
        self.canvas.draw_idle()

    # --------------------------------------------------------------------------- #
    # View-mode / offset API (Overlay / Stacked)
    # --------------------------------------------------------------------------- #
    def set_view_mode(self, mode: str) -> None:
        """Switch display mode. mode is one of 'overlay', 'stacked'."""
        if mode not in ("overlay", "stacked"):
            raise ValueError(f"Unknown view mode: {mode!r}")
        self._view_mode = mode
        self._reflow()

    def set_y_offset(self, value: float, auto: bool = False) -> None:
        """Set the per-line vertical offset used in stacked mode.

        auto=True marks this value as automatically computed (it will be
        recomputed by _reflow() every time the set of visible lines changes,
        for as long as the mode stays 'stacked'); auto=False marks it as a
        user override that persists until recompute_auto_offset() is called
        again.
        """
        self._y_offset = value
        self._y_offset_auto = auto
        self._reflow()

    def recompute_auto_offset(self) -> float:
        """Recompute and apply the automatic Y offset from currently visible lines."""
        self._y_offset = self._auto_offset()
        self._y_offset_auto = True
        self._reflow()
        return self._y_offset

    def set_stack_normalize(self, normalize: bool) -> None:
        """Choose how Stacked mode scales each line before offsetting it.

        normalize=False (default): each line keeps its true relative
        intensity - a weak spectrum stays visually weak next to a strong
        one, exactly like Overlay mode, just shifted apart vertically.
        normalize=True: each line is independently rescaled to the same
        unit height first, so a weak spectrum's own peaks are just as
        visible as a strong spectrum's - useful when comparing shapes
        across spectra whose absolute intensities differ a lot, at the
        cost of no longer showing which spectrum was actually stronger.
        """
        self._stack_normalize = normalize
        if self._y_offset_auto:
            self._y_offset = self._auto_offset()
        self._reflow()

    def get_view_mode(self) -> str:
        return self._view_mode

    def get_y_offset(self) -> float:
        return self._y_offset

    def get_y_offset_auto(self) -> bool:
        return self._y_offset_auto

    def get_stack_normalize(self) -> bool:
        return self._stack_normalize

    def _stack_lines(self) -> list:
        return [ln for ln in self.ax.get_lines() if ln is not self.preview]

    def _line_amplitude(self, ln: plt.Line2D) -> float:
        _, oy = self._line_original[ln]
        return float(np.nanmax(oy) - np.nanmin(oy))

    def _auto_offset(self) -> float:
        """Suggest a Y offset from the amplitude of currently visible lines.

        In normalized mode every line is rescaled to a unit amplitude
        before offsetting (see _reflow), so a fixed step comfortably above
        1.0 is all that's needed regardless of the spectra's real units.
        """
        if self._stack_normalize:
            return 1.2
        stack_lines = self._stack_lines()
        y_spans = [
            self._line_amplitude(ln) for ln in stack_lines if ln in self._line_original
        ]
        return 1.15 * max(y_spans) if y_spans else 0.0

    def _reflow(self) -> None:
        """Reapply the current view mode's offset to every plotted line.

        Must be called any time a line is added, removed, or the mode/offset
        changes, so stacked spacing stays correct - e.g. re-tightens
        automatically when a line is hidden via the tree's eye icon, and
        re-spreads automatically when a new line is added while already in
        stacked mode (this is why the offset is recomputed here rather than
        only when the mode is first switched into: otherwise adding or
        removing a spectrum while already stacked left the old spacing in
        place and made the Y axis look wrong relative to the newly-visible
        set of lines).
        """
        stack_lines = self._stack_lines()
        if self._view_mode == "stacked" and self._y_offset_auto:
            self._y_offset = self._auto_offset()
        for index, ln in enumerate(stack_lines):
            if ln not in self._line_original:
                continue
            ox, oy = self._line_original[ln]
            if self._view_mode == "overlay":
                ln.set_xdata(ox)
                ln.set_ydata(oy)
            else:
                if self._stack_normalize:
                    amp = self._line_amplitude(ln)
                    y_data = (oy - np.nanmin(oy)) / amp if amp > 0 else oy - np.nanmin(oy)
                else:
                    y_data = oy
                ln.set_xdata(ox)
                ln.set_ydata(y_data + index * self._y_offset)
        # In stacked mode the Y axis no longer represents any single
        # spectrum's real intensity (each line carries its own additive
        # offset, and possibly its own rescaling), so the tick labels are
        # misleading if left as-is. Hide them and relabel the axis instead
        # of showing numbers that don't correspond to actual data.
        if self._view_mode == "stacked":
            label = "Intensity (normalized, offset)" if self._stack_normalize else "Intensity (offset, a.u.)"
            self.ax.set_ylabel(label)
            self.ax.tick_params(axis="y", length=0, labelleft=False)
        else:
            self.ax.set_ylabel(self._ylabel_text)
            self.ax.tick_params(axis="y", length=3.5, labelleft=True)
        # A manual zoom (Zoom In/Out) turns autoscale off on purpose; don't
        # let a structural change like adding/removing a line silently
        # snap the view back to "fit everything" and undo it. The explicit
        # Rescale/Reset buttons clear this lock themselves.
        if not self._autoscale_locked_by_user:
            self.ax.relim()
            self.ax.autoscale_view()
        self.canvas.draw_idle()

    # --------------------------------------------------------------------------- #
    # API Tools
    # --------------------------------------------------------------------------- #
    def clear_plot(self) -> None:
        """Clear the current plot."""
        self.ax.cla()
        self.line_spectra.clear()
        self._line_original.clear()
        self._active_line = None
        self.preview = None
        self.canvas.draw_idle()

    def remove_spectrum(self, spec: RamanSpectrum) -> None:
         l = self.is_spectrum_plotted(spec)
         if l is not None:
             self.remove_line(l)
             self.spectrum_deloaded.emit(spec)

    def remove_line(self, l: plt.Line2D) -> None:
        if l is not None:
            idx = l.axes.get_lines().index(l)
            l.remove()
            self._update_legend()
            if l in self.line_spectra: self.line_spectra.pop(l)
            self._line_original.pop(l, None)
            self._reflow()

    def is_spectrum_plotted(self, spec: RamanSpectrum) -> Optional[plt.Line2D]:
        for l in self.line_spectra:
            if self.line_spectra[l] == spec:
                print(f"Spectrum already plottet")
                return l
        return None

    def _find_dataset_line(self, spec: RamanSpectrum, label: str) -> Optional[plt.Line2D]:
        """Return the already-plotted line for (spec, label), if any."""
        for line, owner in self.line_spectra.items():
            if owner is spec and line.get_label() == label:
                return line
        return None

    def get_spectra_from_line(self, line: plt.Line2D) -> RamanSpectrum:
        spec = self.line_spectra[line]
        return spec

    def draw_selected(self, spec: RamanSpectrum) -> None:
        l = self.is_spectrum_plotted(spec)
        if l is not None:
            self.select_line(l)
        else:
            self.draw_spectra(spec, True)

    def draw_dataset(self, spec: RamanSpectrum, dataset: str) -> None:
        """Draw a stored treatment dataset as a view-only line.

        No-ops if this exact (spec, dataset) pair is already plotted.
        """
        label = f"{spec.name}: {dataset}"
        if self._find_dataset_line(spec, label) is not None:
            return
        data = spec.get_step_data(dataset)
        line = self.ax.plot(
            data[:, 0], data[:, 1], label=label, picker=5, linestyle="--"
        )[-1]
        self.line_spectra[line] = spec
        self._line_original[line] = (data[:, 0].copy(), data[:, 1].copy())
        self._update_legend()
        self._reflow()

    def remove_dataset(self, spec: RamanSpectrum, dataset: str) -> None:
        """Remove a specific stored treatment line without removing the spectrum."""
        prefix = f"{spec.name}: {dataset}"
        for line in list(self.line_spectra):
            if self.line_spectra[line] is spec and line.get_label() == prefix:
                self.remove_line(line)

    def draw_spectra(self, spec: RamanSpectrum, select: bool = False, **kwargs) -> None:
        """Draw the current spectrum from a RamanSpectrum object."""
        data = spec.current
        l = self.ax.plot(
             data[:, 0],
             data[:, 1],
             label=spec.name,
             picker=5,
             )[-1]
        self.line_spectra[l] = spec
        self._line_original[l] = (data[:, 0].copy(), data[:, 1].copy())
        if select:
            self.select_line(l)
        self._update_legend()
        self.ax.grid(True, which="both", ls=":", lw=0.5)
        self._reflow()

    def draw_preview(self, name: str, data: np.ndarray) -> None:
         if isinstance(data, np.ndarray):
            self.remove_preview()
            l = self.ax.plot(
                data[:, 0],
                data[:, 1],
                label=name,
                )[-1]
            self.preview = l
            apply_line_settings(self.preview, self.prev_settings)
            self._update_legend()
            self.canvas.draw_idle()
    def remove_preview(self) -> None:
        if not self.preview is None:
            self.preview.remove()
            self.preview = None
            self._update_legend()
            self.canvas.draw_idle()

    def refresh_plot(self) -> None:
        self.ax.relim()
        self.ax.autoscale_view()
        self._update_legend()
        self.canvas.draw_idle()

    def get_lines(self) -> list:
        """Return a list of all lines currently plotted."""
        return self.ax.get_lines()

    def _status(self, message: str) -> str:
        self.status.set_status(message)
        """Display a message in the status bar."""

    # --------------------------------------------------------------------------- #
    # Legend
    # --------------------------------------------------------------------------- #
    def _update_legend(self) -> None:
        """(Re)create the legend from current line labels and settings.

        set_draggable(True, use_blit=True) lets the user grab the legend
        box with the mouse and drop it anywhere on the plot. use_blit=True
        matters: it defaults to False, which redraws the *entire* figure on
        every mouse-move event while dragging - visibly laggy with a full
        spectrum plotted underneath. Blitting only redraws the legend box
        itself during the drag, which is what actually fixes that.
        """
        if not self._legend_visible:
            existing = self.ax.get_legend()
            if existing is not None:
                existing.remove()
            return
        legend = self.ax.legend(
            title=self._legend_title or None,
            fontsize=self._legend_font_size,
        )
        if legend is not None:
            legend.set_draggable(True, use_blit=True)
            if legend.get_title() is not None:
                legend.get_title().set_fontsize(self._legend_font_size)

#
#Context Menu Actions
#

    def _select_colour(self):
        line = self._active_line
        if hasattr(line, "get_color"):
            current_color = line.get_color()
        else:
            current_color = "#1f77b4"
        new_color = pick_colour(initial=current_color)
        line.set_color(new_color)
        if new_color:
            line.set_color(new_color)
            self.canvas.draw_idle()
            self._status(f"Changed colour for {line.get_label()} to {new_color}")


    def _select(self):
        l = self._active_line
        self.select_line(l)
        _log("Line selected (linewidth → 3)")

    def _deselect(self):
        self.deselect()
        _log("Line deselected (linewidth → 1)")

    def _deload(self):
        l = self._active_line
        """Remove the line from the axes."""
        spec = self.line_spectra.get(l)
        self.remove_line(l)
        self.remove_preview()
        self._active_line = None
        if spec is not None:
            self.spectrum_deloaded.emit(spec)
        _log("Line removed from plot (deload)")

    def _apply_treatment(self):
        l = self._active_line
        try:
            self.select_line(l)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(
                None, "Error", f"Failed to apply treatment:\n{exc}"
            )

    def _save_as(self):
        l = self._active_line
        """Prompt for a filename and store the line data as CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save specific data as …",
            filter="txt files (*.txt);;CSV files (*.csv);;All files (*)",
            defaultSuffix="txt",
        )
        if not file_path:
            return

        try:
            spec: RamanSpectrum = self.get_spectra_from_line(l)
            if not spec is None:
                print(f"Spectrum found and current saved")
            else:
                print(f"Spectrum not found")
                return
        except Exception:
            return

        data = spec.current
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["x", "y"])
            for xv, yv in zip(data[:, 0], data[:, 1]):
                writer.writerow([xv, yv])

        _log(f"Saved line data to {file_path}")

    def _open_in_explorer(self):
        spec: RamanSpectrum = self.get_spectra_from_line(self._active_line)
        if not spec is None:
            print(f"Spectrum found and open folder")
            folder = os.path.dirname(spec._path)
            try:
                _open_folder(folder)
                _log(f"Opened Explorer at {folder}")
            except Exception as exc:  # pragma: no cover
                QMessageBox.critical(
                    None, "Error", f"Failed to open Explorer:\n{exc}"
                )

    def _show_history(self) -> None:
        spec: RamanSpectrum = self.get_spectra_from_line(self._active_line)
        """Display a read‑only dialog with the action history."""
        dlg = QDialog()
        dlg.setWindowTitle("Spectrum history")
        dlg.resize(600, 400)

        layout = QVBoxLayout(dlg)

        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText("\n".join(spec.history))
        layout.addWidget(text_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok, parent=dlg
        )
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)

        dlg.exec()
        _log("Displayed action history")

#
#Toolbar
#

    def rescale_x(self):
        self._autoscale_locked_by_user = False
        self.ax.set_autoscalex_on(True)
        self.ax.relim()
        self.ax.autoscale_view(scalex=True, scaley=False)
        self.canvas.draw_idle()

    def rescale_y(self):
        self._autoscale_locked_by_user = False
        self.ax.set_autoscaley_on(True)
        self.ax.relim()
        self.ax.autoscale_view(scalex=False, scaley=True)
        self.canvas.draw_idle()

    def rescale_xy(self):
        self._autoscale_locked_by_user = False
        self.ax.set_autoscalex_on(True)
        self.ax.set_autoscaley_on(True)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    def reset_view(self):
        """Reset to the original limits of the currently plotted data."""
        self.rescale_xy()

    def zoom_in(self):
        self._zoom(0.8)

    def zoom_out(self):
        self._zoom(1.25)

    def _zoom(self, factor: float) -> None:
        """Scale the current view in/out by `factor`, keeping it centred.

        Turns autoscale off so this manual view survives the next line
        add/remove (see _reflow's _autoscale_locked_by_user check) - use
        Rescale/Reset to explicitly go back to auto-fit.
        """
        self._autoscale_locked_by_user = True
        self.ax.set_autoscalex_on(False)
        self.ax.set_autoscaley_on(False)
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        xmid = (xlim[0] + xlim[1]) / 2
        ymid = (ylim[0] + ylim[1]) / 2
        xhalf = (xlim[1] - xlim[0]) / 2 * factor
        yhalf = (ylim[1] - ylim[0]) / 2 * factor
        self.ax.set_xlim(xmid - xhalf, xmid + xhalf)
        self.ax.set_ylim(ymid - yhalf, ymid + yhalf)
        self.canvas.draw_idle()

    def edit_line_style(self):
        """
        Open the line-style dialog for the currently *selected* line
        (self._active_line - the line last clicked/picked in the plot),
        not the treatment-preview line. The previous "Preview" button tried
        to edit self.preview and fell back to a bare `False` when no
        treatment preview existed, which crashed get_settings_from_line().
        Selecting a line first (click it, or double-click for just the
        colour) and then pressing this button is the intended workflow for
        changing colour, width, alpha, line style, and z-order.
        """
        line = self._active_line if self._active_line is not None else self.preview
        if line is None:
            QMessageBox.information(
                self, "No line selected", "Click a line in the plot first, then use this button to edit its style."
            )
            return
        init_dict = get_settings_from_line(line)

        dlg = LineSettingsDialog(
            parent=self,
            reference_widget=self.btn_line_style,
            initial_settings=init_dict,
        )
        dlg.settingsChanged.connect(lambda s: apply_line_settings(line, s))
        if dlg.exec() == QDialog.Accepted:
            final_settings = get_settings_from_line(line)
            self.cfg.set_value([self.NAME, "prev_settings"], final_settings)
            self.canvas.draw_idle()

    def flip_x(self):
        """Invert the X axis direction (common for Raman shift, high->low)."""
        self.ax.invert_xaxis()
        self.canvas.draw_idle()

    def save_image(self):
        """Export the current figure exactly as displayed (png/jpg/pdf/svg)."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save plot image",
            "",
            "PNG image (*.png);;JPEG image (*.jpg);;PDF (*.pdf);;SVG (*.svg)",
        )
        if not file_path:
            return
        try:
            self.fig.savefig(file_path, dpi=300, bbox_inches="tight")
            self._status(f"Saved plot image to {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save image:\n{exc}")

    def edit_legend(self):
        """Open the legend settings dialog: visibility, font size, title,
        and per-line entry text. Position/dragging is handled separately
        by simply grabbing the legend with the mouse (see _update_legend).
        """
        lines = self._stack_lines()
        dlg = LegendSettingsDialog(
            self,
            lines=lines,
            visible=self._legend_visible,
            font_size=self._legend_font_size,
            title=self._legend_title,
        )
        if dlg.exec() == QDialog.Accepted:
            for line, new_label in dlg.new_labels().items():
                line.set_label(new_label)
            self._legend_visible = dlg.is_visible()
            self._legend_font_size = dlg.font_size()
            self._legend_title = dlg.title()
            self._update_legend()
            self.canvas.draw_idle()

    def edit_axis_labels(self):
        """Let the user set the plot title and X/Y axis label text."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Axis labels")
        from PySide6.QtWidgets import QFormLayout, QLineEdit
        layout = QFormLayout(dlg)
        title_edit = QLineEdit(self.ax.get_title())
        x_edit = QLineEdit(self.ax.get_xlabel())
        y_edit = QLineEdit(self._ylabel_text)
        layout.addRow("Title:", title_edit)
        layout.addRow("X axis:", x_edit)
        layout.addRow("Y axis:", y_edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec() == QDialog.Accepted:
            self.ax.set_title(title_edit.text())
            self.ax.set_xlabel(x_edit.text())
            self._ylabel_text = y_edit.text()
            if self._view_mode != "stacked":
                self.ax.set_ylabel(self._ylabel_text)
            self.canvas.draw_idle()

# --------------------------------------------------------------------------- #
# Helper – colour picker dialog that returns a hex string
# --------------------------------------------------------------------------- #
    def _random_color() -> str:
        """Return a random colour in hex format."""
        import random
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))


def pick_colour(initial: str = "#1f77b4") -> str | None:
    """Ask the user for a colour; returns a hex string or None if cancelled."""
    Qinitial = mpl_color_to_qcolor(initial)
    colour = QColorDialog.getColor(
        Qinitial, None, "Select line colour"
    )
    return colour.name() if colour.isValid() else None

def mpl_color_to_qcolor(mpl_color) -> QColor | None:
    if mpl_color is None:
        return None
    r, g, b, a = to_rgba(mpl_color)
    if a == 0:
        return None
    return QColor.fromRgbF(r, g, b, a)

def _qtcolor_to_rgba(color: QColor) -> tuple[float, float, float, float]:
    if not isinstance(color, QColor):
        raise TypeError("color must be a QColor instance")
    return (
        color.redF(),
        color.greenF(),
        color.blueF(),
        color.alphaF(),
    )
def _rgba_to_QColor(rgba: tuple[float, float, float, float]) -> QColor:
    return QColor(rgba[0], rgba[1], rgba[2], rgba[3])

def _open_folder(path: str) -> None:
    folder = os.path.abspath(path)
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"The folder {folder!r} does not exist.")
    if sys.platform.startswith("darwin"):
        subprocess.run(["open", folder])
    elif sys.platform.startswith("win"):
        os.startfile(folder)  # type: ignore[arg-type]
    else:
        subprocess.run(["xdg-open", folder])

def _log(action: str) -> None:
        log = []
        timestamp = datetime.now().strftime(f"%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {action}"
        log.append(entry)
        try:
            with open("", "a", encoding="utf-8") as f:
                f.write(entry + "\n")
        except Exception:  # pragma: no cover
            pass
def apply_line_settings(line: plt.Line2D, settings: dict) -> None:
    if not isinstance(line, plt.Line2D):
        print(f"line is not a Line2D it's {type(line)}")
        return

    def _get(key: str, default=Any):
        if key not in settings:
            raise KeyError(f"Missing required key '{key}' in settings dictionary")
        return settings[key]

    rgba: tuple[float,float,float,float] = _get("color")
    if isinstance(rgba, QColor):
        rgba = _qtcolor_to_rgba(rgba)

    line.set_color(rgba)
    line.set_linewidth(_get("linewidth"))
    line.set_alpha(_get("alpha"))
    line.set_linestyle(_get("linestyle"))
    line.set_visible(_get("enabled"))

    z = 10 if _get("zorder") == "above" else -10
    line.set_zorder(z)
    line.axes.figure.canvas.draw_idle()

def get_settings_from_line(line: plt.Line2D) -> Dict[str, Any]:
    d={
        "color": to_rgba(line.get_color()),
        "linewidth": int(line.get_linewidth()),
        "alpha": float(line.get_alpha()),
        "linestyle": line.get_linestyle(),
        "zorder": "above" if line.get_zorder() > 0 else "below",
        "enabled": line.get_visible(),
    }
    return d