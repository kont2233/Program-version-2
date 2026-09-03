import json
import os
import numpy as np
from typing import Dict, List, Any
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QToolBar,
    QPushButton,
    QLabel,
    QLineEdit,
    QListWidget,
    QAbstractItemView,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from gui.widgets.spectra_canvas import SpectraCanvas
from gui.widgets.spectra_manager import SpectraManagerWidget
from models.spectrum import RamanSpectrum
from treatments.truncation import truncate
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector


class TruncationRangeDialog(QDialog):
    """Full-size zoomable selector for the wavenumber range to keep."""

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select truncation range")
        self.resize(1100, 700)
        self.data = data
        self.selection = None
        figure = Figure(figsize=(12, 7))
        axis = figure.add_subplot(111)
        axis.plot(data[:, 0], data[:, 1], color="tab:blue", linewidth=0.9)
        axis.set_xlabel("Raman shift (cm-1)")
        axis.set_ylabel("Intensity")
        axis.grid(True, which="both", linestyle=":", linewidth=0.5)
        self.axis = axis
        self.axis.set_xlim(float(data[:, 0].min()), float(data[:, 0].max()))
        self.canvas = FigureCanvas(figure)
        self.selector = SpanSelector(
            axis, self._selected, "horizontal", useblit=False,
            button=1, minspan=0, props={"facecolor": "tab:orange", "alpha": 0.3},
        )
        layout = QVBoxLayout(self)
        instructions = QLabel("Drag with the left mouse button across the range to keep. Use the toolbar to zoom, then drag again.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        layout.addWidget(NavigationToolbar(self.canvas, self))
        layout.addWidget(self.canvas)
        self.selection_label = QLabel("No range selected")
        layout.addWidget(self.selection_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _selected(self, start: float, end: float) -> None:
        self.selection = (min(start, end), max(start, end))
        self.selection_label.setText(
            f"Selected range: {self.selection[0]:.3f} - {self.selection[1]:.3f} cm-1"
        )
        self.axis.axvspan(*self.selection, color="tab:orange", alpha=0.3)
        self.canvas.draw_idle()


class TruncationTab(QWidget):
    """Tab for truncating Raman spectra based on wavenumber range."""

    CONFIG_FILE = "config/truncation_settings.json"
    NAME = "Truncation"

    def __init__(self, manager: SpectraManagerWidget, canvas: SpectraCanvas, parent=None):
        super().__init__(parent)
        self.saved_windows = []  # List to store saved truncation windows
        self.spectra_manager = manager
        self.init_ui(canvas)
        self.spectra_manager.spectrum_selected.connect(self._on_spectrum_selected)
        self.spectra_manager.dataset_selected.connect(self._on_dataset_selected)
        self.load_saved_windows()

    def init_ui(self, canvas):
        """Initialize the user interface for the Truncation tab."""
        # Main layout: Splitter dividing Spectra Panel and Settings Panel
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)

        # Spectra Panel
        self.spectra_panel: SpectraCanvas = canvas
        splitter.addWidget(self.spectra_panel)

        # Settings Panel
        self.settings_panel = QWidget()
        splitter.addWidget(self.settings_panel)
        splitter.setSizes([600, 300])  # Set default sizes for the panels

        self.init_settings_panel()

    def init_settings_panel(self):
        """Initialize the settings panel with toolbar, input fields, and list."""
        # Main layout for the settings panel
        settings_layout = QVBoxLayout(self.settings_panel)

        select_range_btn = QPushButton("Select range on spectrum")
        select_range_btn.clicked.connect(self.select_range_on_spectrum)
        settings_layout.addWidget(select_range_btn)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setFixedHeight(40)
        settings_layout.addWidget(toolbar)

        # Toolbar buttons
        apply_all_btn = QPushButton("Apply to All")
        apply_all_btn.setIcon(QIcon("resources/icons/apply_icon.png"))
        apply_all_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        toolbar.addWidget(apply_all_btn)

        apply_selected_btn = QPushButton("Apply to Selected")
        apply_selected_btn.setIcon(QIcon("resources/icons/apply_selected_icon.png"))
        apply_selected_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        toolbar.addWidget(apply_selected_btn)

        save_settings_btn = QPushButton("Save Settings")
        save_settings_btn.setIcon(QIcon("resources/icons/save_icon.png"))
        save_settings_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        toolbar.addWidget(save_settings_btn)

        load_settings_btn = QPushButton("Load Settings")
        load_settings_btn.setIcon(QIcon("resources/icons/load_icon.png"))
        load_settings_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        toolbar.addWidget(load_settings_btn)

        # Settings Input Fields and Reset Buttons
        settings_inputs_layout = QHBoxLayout()

        # Minimum Wavenumber
        min_label = QLabel("Minimum:")
        min_label.setFixedWidth(100)
        self.min_input = QLineEdit()
        self.min_input.setFixedWidth(100)
        self.min_input.setPlaceholderText("Enter min")
        self.min_input.setText("0")
        reset_min_btn = QPushButton()
        reset_min_btn.setIcon(QIcon("resources/icons/revert_icon.png"))
        reset_min_btn.setFixedSize(QSize(20, 20))

        settings_inputs_layout.addWidget(min_label)
        settings_inputs_layout.addWidget(self.min_input)
        settings_inputs_layout.addWidget(reset_min_btn)

        # Maximum Wavenumber
        max_label = QLabel("Maximum:")
        max_label.setFixedWidth(100)
        self.max_input = QLineEdit()
        self.max_input.setFixedWidth(100)
        self.max_input.setPlaceholderText("Enter max")
        self.max_input.setText("4000")
        reset_max_btn = QPushButton()
        reset_max_btn.setIcon(QIcon("resources/icons/revert_icon.png"))
        reset_max_btn.setFixedSize(QSize(20, 20))

        settings_inputs_layout.addWidget(max_label)
        settings_inputs_layout.addWidget(self.max_input)
        settings_inputs_layout.addWidget(reset_max_btn)

        settings_layout.addLayout(settings_inputs_layout)

        # Spectra Windows List
        self.windows_list = QListWidget()
        self.windows_list.setSelectionMode(QAbstractItemView.SingleSelection)
        settings_layout.addWidget(self.windows_list)

        # Add and Delete Buttons for Spectra Windows
        list_buttons_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        delete_btn = QPushButton("Delete")
        list_buttons_layout.addWidget(add_btn)
        list_buttons_layout.addWidget(delete_btn)
        settings_layout.addLayout(list_buttons_layout)

        # Connect signals
        self.min_input.textChanged.connect(self.updatespectra)
        self.max_input.textChanged.connect(self.updatespectra)
        reset_min_btn.clicked.connect(self.reset_min)
        reset_max_btn.clicked.connect(self.reset_max)
        apply_all_btn.clicked.connect(self.apply_to_all)
        apply_selected_btn.clicked.connect(self.apply_to_selected)
        save_settings_btn.clicked.connect(self.save_settings)
        load_settings_btn.clicked.connect(self.load_settings)
        add_btn.clicked.connect(self.add_window)
        delete_btn.clicked.connect(self.delete_window)
        self.windows_list.itemDoubleClicked.connect(self.load_window_to_fields)

    def reset_min(self):
        """Reset minimum wavenumber to the lowest value in the spectra."""
        # Example functionality: Replace with actual logic
        self.min_input.setText("149.874")  # Replace with actual min from spectra

    def reset_max(self):
        """Reset maximum wavenumber to the highest value in the spectra."""
        # Example functionality: Replace with actual logic
        self.max_input.setText("3165.972")  # Replace with actual max from spectra

   

    def save_settings(self):
        """Save the current truncation settings to a JSON file."""
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(self.saved_windows, f, indent=4)
        print("Truncation settings saved.")

    def load_settings(self):
        """Load truncation settings from a JSON file."""
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                self.saved_windows = json.load(f)
            self.update_windows_list()
            print("Truncation settings loaded.")

    def add_window(self):
        """Add a new truncation window to the list."""
        min_value = self.min_input.text()
        max_value = self.max_input.text()
        if min_value and max_value:
            window = {"min": min_value, "max": max_value}
            self.saved_windows.append(window)
            self.windows_list.addItem(f"{min_value} - {max_value}")
            print(f"Added window: {min_value} - {max_value}")

    def delete_window(self):
        """Delete the selected truncation window from the list."""
        selected_item = self.windows_list.currentItem()
        if selected_item:
            index = self.windows_list.row(selected_item)
            self.saved_windows.pop(index)
            self.windows_list.takeItem(index)
            print(f"Deleted window: {selected_item.text()}")

    def load_window_to_fields(self, item):
        """Load the selected window's data into the input fields."""
        index = self.windows_list.row(item)
        window = self.saved_windows[index]
        self.min_input.setText(window["min"])
        self.max_input.setText(window["max"])
        print(f"Loaded window: {window['min']} - {window['max']}")

    def update_windows_list(self):
        """Update the windows list widget with saved windows."""
        self.windows_list.clear()
        for window in self.saved_windows:
            self.windows_list.addItem(f"{window['min']} - {window['max']}")

    def load_saved_windows(self):
        """Load saved windows from the configuration file."""
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                self.saved_windows = json.load(f)
            self.update_windows_list()

    def refresh_from_manager(self):
        """Render the manager's current dataset when this tab is opened."""
        spec = self.spectra_manager.current_spectrum()
        if spec is None:
            self.spectra_panel.clear_plot()
            return
        self._on_dataset_selected(spec, self.spectra_manager.current_dataset())

    def _on_spectrum_selected(self, spec: RamanSpectrum | None):
        if spec is not None:
            self._on_dataset_selected(spec, self.spectra_manager.current_dataset())

    def select_range_on_spectrum(self):
        """Open a full-size plot and use the selected span as truncation bounds."""
        if getattr(self, "_selected_source", None) is None:
            return
        dialog = TruncationRangeDialog(self._selected_source, self)
        dialog.showMaximized()
        if dialog.exec() == QDialog.Accepted and dialog.selection is not None:
            minimum, maximum = dialog.selection
            self.min_input.setText(str(minimum))
            self.max_input.setText(str(maximum))
            self._render_comparison(self._selected_spec, self._selected_source)

    #
    # Tab functions that need to be there in every tab
    #
    def apply_to_all(self):
        """Apply truncation to all spectra."""
        args: Dict[str, Any] = self.getparameters()
        self.spectra_manager._apply_to_all(self.NAME, truncate, **args)
        print(f"Applying truncation to all spectra: {args}")

    def apply_to_selected(self):
        """Apply truncation to selected spectra."""
        args: Dict[str, Any] = self.getparameters()
        self.spectra_manager._apply_to_checked(self.NAME, truncate, **args)
        print(f"Applying truncation to selected spectra: {args}")

    def getparameters(self) -> Dict[str, Any]:
        args: Dict[str, Any] = {
            "min_shift": float(self.min_input.text() or 0),
            "max_shift": float(self.max_input.text() or 0)
        }
        return args 
    
    def apply(self, data: np.ndarray) -> np.ndarray:
        args = self.getparameters()
        d: np.ndarray = truncate(data, **args)[0]
        d = d[:, [d.ndim-2, d.ndim-1]] #take the last two columns
        return d

    def updatespectra(self) -> None:
        if getattr(self, "_selected_spec", None) is not None:
            self._render_comparison(self._selected_spec, self._selected_source)
    
    def drawpreview(self, spec: RamanSpectrum):
        self._on_dataset_selected(spec, "current")

    def _on_dataset_selected(self, spec: RamanSpectrum | None, dataset: str):
        if spec is None:
            self.spectra_panel.clear_plot()
            return
        if dataset == "current":
            source = spec.current
        elif dataset in spec.datasets:
            source = spec.get_step_data(dataset)
        else:
            source = spec.raw
            dataset = "raw"
        self._selected_spec = spec
        self._selected_source = source
        self._render_comparison(spec, source)

    def _render_comparison(self, spec: RamanSpectrum, source: np.ndarray):
        self.spectra_panel.clear_plot()
        try:
            truncated = self.apply(source)
        except ValueError:
            truncated = source.copy()
        self.spectra_panel.ax.plot(
            spec.raw[:, 0], spec.raw[:, 1], label=f"{spec.name}: raw", linewidth=0.9
        )
        self.spectra_panel.ax.plot(
            truncated[:, 0], truncated[:, 1],
            label=f"{spec.name}: truncated", linewidth=1.1,
        )
        self.spectra_panel.ax.set_xlabel("Raman shift (cm-1)")
        self.spectra_panel.ax.set_ylabel("Intensity")
        self.spectra_panel.ax.grid(True, which="both", linestyle=":", linewidth=0.5)
        self.spectra_panel.ax.legend()
        self.spectra_panel.canvas.draw_idle()
    



