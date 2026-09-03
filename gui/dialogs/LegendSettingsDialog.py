"""Modal dialog for editing the plot legend: visibility, font size, title,
and the text of each individual entry.

Matplotlib's legend already supports dragging (see SpectraCanvas._update_legend,
which turns that on with blitting for a responsive drag). This dialog covers
everything dragging doesn't: hiding it, shrinking/growing it, giving it a
title, and renaming what each line says in it ("write on it").
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QCheckBox,
    QSpinBox,
    QLineEdit,
    QScrollArea,
    QWidget,
    QDialogButtonBox,
    QLabel,
)


class LegendSettingsDialog(QDialog):
    """Edit legend visibility/font size/title and rename individual entries.

    `lines` is the list of currently-plotted Line2D objects (in the order
    they should be listed); the dialog reads each one's current label as
    the starting text for its rename field.
    """

    def __init__(self, parent=None, *, lines, visible: bool, font_size: int, title: str):
        super().__init__(parent)
        self.setWindowTitle("Legend settings")
        self._lines = list(lines)
        self._label_edits: list[QLineEdit] = []
        self._build_ui(visible, font_size, title)

    def _build_ui(self, visible: bool, font_size: int, title: str) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.visible_check = QCheckBox("Show legend")
        self.visible_check.setChecked(visible)
        form.addRow(self.visible_check)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(4, 48)
        self.font_size_spin.setValue(font_size)
        form.addRow("Font size:", self.font_size_spin)

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("(no title)")
        form.addRow("Legend title:", self.title_edit)

        layout.addLayout(form)

        if self._lines:
            layout.addWidget(QLabel("Entry labels:"))
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_widget = QWidget()
            scroll_layout = QFormLayout(scroll_widget)
            for line in self._lines:
                edit = QLineEdit(line.get_label())
                self._label_edits.append(edit)
                scroll_layout.addRow(edit)
            scroll_area.setWidget(scroll_widget)
            scroll_area.setMaximumHeight(220)
            layout.addWidget(scroll_area)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ #
    # Results, read after exec() == QDialog.Accepted
    # ------------------------------------------------------------------ #
    def is_visible(self) -> bool:
        return self.visible_check.isChecked()

    def font_size(self) -> int:
        return self.font_size_spin.value()

    def title(self) -> str:
        return self.title_edit.text()

    def new_labels(self) -> dict:
        """Return {line: new_label_text} for every line whose text changed."""
        result = {}
        for line, edit in zip(self._lines, self._label_edits):
            text = edit.text()
            if text != line.get_label():
                result[line] = text
        return result