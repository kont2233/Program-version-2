# --------------------------------------------------------------
#  file: tree_actions.py
# --------------------------------------------------------------
"""
Collection of reusable QAction factories for the TreeView widget.

The actions are deliberately kept in a separate module so that any
other widget can import them and add the same behaviours to its
own context‑menus without creating duplicate code.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QObject, Signal, Slot


# ------------------------------------------------------------------
# Helper: a tiny QObject that can emit custom signals from QAction.
# This makes it easy for the main widget to react to the menu choice.
# ------------------------------------------------------------------
class ActionSignalEmitter(QObject):
    """Small signal holder used by the action factories."""
    triggered = Signal()


def _make_action(parent: QObject,
                 text: str,
                 icon_path: str | None = None,
                 shortcut: str | None = None) -> QAction:
    """
    Small helper that creates a QAction, attaches a custom signal
    (`triggered`) and returns it.

    Parameters
    ----------
    parent: QObject
        The QObject that will own the action (normally the TreeView widget).
    text: str
        Text displayed in the menu.
    icon_path: str | None
        Optional path to an icon – can be ``None``.
    shortcut: str | None
        Optional keyboard shortcut (e.g. ``"Ctrl+D"``).

    Returns
    -------
    QAction
        The freshly created action.
    """
    action = QAction(text, parent)
    if icon_path:
        action.setIcon(QIcon(icon_path))
    if shortcut:
        action.setShortcut(shortcut)

    # Attach a dedicated signal that the widget can connect to.
    emitter = ActionSignalEmitter(parent)
    action.triggered.connect(emitter.triggered)
    action._emitter = emitter  # type: ignore[attr-defined]  # store for later use
    return action


# ------------------------------------------------------------------
# Public factories – one for each menu entry required in the spec.
# ------------------------------------------------------------------
def make_fully_disable_action(parent: QObject) -> QAction:
    """
    Create the **Fully Disable** action.

    The calling widget can connect to ``action._emitter.triggered`` to
    receive a clean signal without needing to know about the internal
    QAction implementation.
    """
    return _make_action(parent, "Fully Disable", icon_path=None)


def make_deload_action(parent: QObject) -> QAction:
    """Create the **Deload** action."""
    return _make_action(parent, "Deload")


def make_select_action(parent: QObject) -> QAction:
    """Create the **Select** action."""
    return _make_action(parent, "Select")


def make_view_action(parent: QObject) -> QAction:
    """Create the **View** action."""
    return _make_action(parent, "View")


def make_remove_treatment_action(parent: QObject) -> QAction:
    """Create the **Remove Treatment** action."""
    return _make_action(parent, "Remove Treatment")


def make_open_in_explorer_action(parent: QObject) -> QAction:
    """Create the **Open in Explorer** action."""
    return _make_action(parent, "Open in Explorer")


def make_show_history_action(parent: QObject) -> QAction:
    """Create the **Show History** action."""
    return _make_action(parent, "Show History")
