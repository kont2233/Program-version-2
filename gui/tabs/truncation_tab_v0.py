from PySide6.QtWidgets import (
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
from gui.widgets.spectra_canvas import SpectraCanvas
from PySide6.QtGui import QIcon


class TruncationTab(QWidget):
    """Tab for truncating Raman spectra based on wavenumber range."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface for the Truncation tab."""
        # Main layout: Splitter dividing Spectra Panel and Settings Panel
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)

        # Spectra Panel
        self.spectra_panel = SpectraCanvas()
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

        # Toolbar
        toolbar = QToolBar()
        toolbar.setFixedHeight(50)
        settings_layout.addWidget(toolbar)

        # Toolbar buttons
        apply_all_btn = QPushButton("Apply to All")
        apply_all_btn.setIcon(QIcon("resources/apply_icon.png"))
        apply_all_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        toolbar.addWidget(apply_all_btn)

        apply_selected_btn = QPushButton("Apply to Selected")
        apply_selected_btn.setIcon(QIcon("resources/apply_selected_icon.png"))
        apply_selected_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        toolbar.addWidget(apply_selected_btn)

        save_settings_btn = QPushButton("Save Settings")
        save_settings_btn.setIcon(QIcon("resources/save_icon.png"))
        save_settings_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        toolbar.addWidget(save_settings_btn)

        load_settings_btn = QPushButton("Load Settings")
        load_settings_btn.setIcon(QIcon("resources/load_icon.png"))
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
        reset_min_btn = QPushButton()
        reset_min_btn.setIcon(QIcon("resources/revert_icon.png"))
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
        reset_max_btn = QPushButton()
        reset_max_btn.setIcon(QIcon("resources/revert_icon.png"))
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
        reset_min_btn.clicked.connect(self.reset_min)
        reset_max_btn.clicked.connect(self.reset_max)
        apply_all_btn.clicked.connect(self.apply_to_all)
        apply_selected_btn.clicked.connect(self.apply_to_selected)
        save_settings_btn.clicked.connect(self.save_settings)
        load_settings_btn.clicked.connect(self.load_settings)
        add_btn.clicked.connect(self.add_window)
        delete_btn.clicked.connect(self.delete_window)

    def reset_min(self):
        """Reset minimum wavenumber to the lowest value in the spectra."""
        # Example functionality: Replace with actual logic
        self.min_input.setText("149.874")  # Replace with actual min from spectra

    def reset_max(self):
        """Reset maximum wavenumber to the highest value in the spectra."""
        # Example functionality: Replace with actual logic
        self.max_input.setText("3165.972")  # Replace with actual max from spectra

    def apply_to_all(self):
        """Apply truncation to all spectra."""
        min_value = float(self.min_input.text() or 0)
        max_value = float(self.max_input.text() or 0)
        print(f"Applying truncation to all spectra: {min_value}-{max_value}")

    def apply_to_selected(self):
        """Apply truncation to selected spectra."""
        min_value = float(self.min_input.text() or 0)
        max_value = float(self.max_input.text() or 0)
        print(f"Applying truncation to selected spectra: {min_value}-{max_value}")

    def save_settings(self):
        """Save the current truncation settings."""
        print("Saving truncation settings...")

    def load_settings(self):
        """Load saved truncation settings."""
        print("Loading truncation settings...")

    def add_window(self):
        """Add a new truncation window to the list."""
        min_value = self.min_input.text()
        max_value = self.max_input.text()
        if min_value and max_value:
            self.windows_list.addItem(f"{min_value} - {max_value}")
            print(f"Added window: {min_value} - {max_value}")

    def delete_window(self):
        """Delete the selected truncation window from the list."""
        selected_item = self.windows_list.currentItem()
        if selected_item:
            self.windows_list.takeItem(self.windows_list.row(selected_item))
            print(f"Deleted window: {selected_item.text()}")


