# singleton_meta.py
"""
Utility module that provides a thread‑safe Singleton metaclass
compatible with both PyQt5 and PySide2.
"""

from __future__ import annotations

import threading
import warnings
from typing import Any, Optional, Type
from PySide6.QtWidgets import QWidget

QtMeta = type(QWidget)
class SingletonMeta(QtMeta):
    """
    Thread‑safe metaclass that guarantees a class has only one instance.

    The first call to the class creates the object; later calls return
    the same object, while silently ignoring any new ``*args`` / ``**kwargs``.
    In debug mode a ``RuntimeWarning`` is emitted when arguments are ignored.

    Attributes
    ----------
    _instance : Optional[object]
        The sole instance of the class (or ``None`` before the first creation).
    _lock : threading.Lock
        Ensures that two threads cannot create two separate instances.
    """

    _instance: Optional[object] = None
    _lock = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Create or return the singleton instance."""
        # Fast path – instance already exists (no lock needed)
        if cls._instance is not None:
            if __debug__ and (args or kwargs):
                warnings.warn(
                    f"{cls.__name__} is a singleton – extra arguments are ignored.",
                    RuntimeWarning,
                )
            return cls._instance

        # No instance yet – protect creation with a lock
        with cls._lock:
            if cls._instance is None:                # double‑checked locking
                cls._instance = super().__call__(*args, **kwargs)
        return cls._instance
