"""
Main Window for ECPypsi Application

Defines the main QMainWindow, splitter, menu bar, left panel (Spectra Explorer),
right panel (QTabWidget), and bottom bar.
"""

from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout
from models.config_manager import ConfigManager
from gui.menu_functions import create_menu_bar
from gui.widgets.spectra_manager import SpectraManagerWidget
from gui.widgets.spectra_canvas import SpectraCanvas
from gui.status_bar import StatusBar
from gui.tabs.data_tab import DataTab
from gui.tabs.truncation_tab import TruncationTab
from gui.tabs.spike_removal_tab import SpikeRemovalTab
from gui.tabs.calibration_tab import CalibrationTab
from gui.tabs.smoothing_tab import SmoothingTab
from gui.tabs.baseline_tab import BaselineTab
from gui.tabs.normalization_tab import NormalizationTab
from gui.tabs.peak_fitting_tab import PeakFittingTab
from gui.tabs.component_analysis_tab import ComponentAnalysisTab
from gui.tabs.advanced_tab import AdvancedTab

from PySide6.QtWidgets import QTabWidget

class MainWindow(QMainWindow):
    """Main application window for ECPypsi."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECPypsi")
        self.setGeometry(100, 100, 1300, 900)
        self.cfg = ConfigManager()

        self.status_bar = StatusBar(self)

        # Add Spectra Viewer - embedded directly into the Data tab below,
        # and simultaneously driven by the Spectra Manager tree's eye-icon
        # toggles (see SpectraManagerWidget).
        self.spectra_canvas = SpectraCanvas(self)
        
        # Menu bar
        self.menu_bar = create_menu_bar(self)
        self.setMenuWidget(self.menu_bar)

        # Central splitter
        splitter = QSplitter(self)
        self.setCentralWidget(splitter)

        # Left panel: Spectra Manager
        self.spectra_manager = SpectraManagerWidget(self.spectra_canvas)
        splitter.addWidget(self.spectra_manager)

        # Right panel: Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumWidth(300)
        splitter.addWidget(self.tab_widget) 

        # Add tabs
        self.data_tab = DataTab(self.spectra_manager, self.spectra_canvas)
        self.tab_widget.addTab(self.data_tab, "Data")
        self.tab_widget.addTab(TruncationTab(self.spectra_manager, SpectraCanvas()), "Truncation")
        self.tab_widget.addTab(SpikeRemovalTab(self.spectra_manager), "Spike Removal")
        self.tab_widget.addTab(CalibrationTab(self.spectra_manager), "Calibration")
        self.tab_widget.addTab(SmoothingTab(self.spectra_manager, SpectraCanvas()), "Smoothing")
        self.tab_widget.addTab(BaselineTab(self.spectra_manager, SpectraCanvas()), "Baseline")
        self.tab_widget.addTab(NormalizationTab(self.spectra_manager, SpectraCanvas()), "Normalization")
        self.tab_widget.addTab(PeakFittingTab(self.spectra_manager, SpectraCanvas()), "Peak Fitting")
        self.tab_widget.addTab(ComponentAnalysisTab(), "Component Analysis")
        self.tab_widget.addTab(AdvancedTab(), "Advanced")

        splitter.setSizes([300, 1000])

        # Status bar
        
        self.setStatusBar(self.status_bar)

        # Example usage of the status bar
        self.status_bar.set_status("Ready")
        self.status_bar.set_progress(0)

        self._connect_signals()


        # Example usage of the Spectra Manager
        #self.spectra_manager.add_spectrum("Spectrum 1")
        #self.spectra_manager.add_treatment("Spectrum 1", "Truncation")
        #self.spectra_manager.add_treatment("Spectrum 1", "Baseline Correction", ["Baseline"])
        #self.spectra_manager.add_treatment("Spectrum 1", "Peak Fitting", ["Cumulative", "Peak1", "Peak2", "Peak3"])
        #self._connect_signals()

    def _connect_signals(self):
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.data_tab.statusChanged.connect(self.on_status_changed)
        self.spectra_manager.spectrum_selected.connect(self._on_manager_selection)

    #SignalProcessing
    def on_tab_changed(self, index):
        tab_name = self.tab_widget.tabText(index)
        self.status_bar.set_status(f"Switched to {tab_name} tab")
        tab = self.tab_widget.widget(index)
        refresh = getattr(tab, "refresh_from_manager", None)
        if refresh is not None:
            refresh()

    def on_status_changed(self, message):
        self.status_bar.set_status(message)

    def _on_manager_selection(self, spectrum):
        name = spectrum.name if spectrum is not None else "None"
        self.status_bar.set_status(f"Selected spectrum: {name}")