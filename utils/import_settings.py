"""Centralised import-configuration helpers.

Single source of truth for "how should a spectrum file be read, and where
should its processed copy be written" - used by File > Open
(gui/menu_functions.py) and by the Import Settings dialog
(gui/dialogs/ImportSettingsDialog.py).

Replaces logic that used to live in gui/tabs/data_tab.py
(DataTab._get_selected_delimiter / DataTab._get_new_path), which read
directly from UI widgets and had two real bugs, both fixed here:
  1. `if self.use_source_folder_cb:` tested the checkbox *widget object*
     (always truthy) instead of `.isChecked()`.
  2. `Path.is_dir(self.proc_path_input.text)` was missing the `()` call on
     `.text`, so it passed a bound method object instead of a string.
"""
from __future__ import annotations

import os
from pathlib import Path

from models.config_manager import ConfigManager

CONFIG_KEY = "Import-Settings"
PROCESSED_SUBFOLDER = "/processed/"

_DELIMITER_MAP = {
    "Tab": "\t",
    "Comma": ",",
    "Semicolon": ";",
}


def get_selected_delimiter() -> str:
    """Return the delimiter character to use when reading a spectrum file."""
    cfg = ConfigManager()
    settings = cfg.get_value([CONFIG_KEY]) or {}
    choice = settings.get("Delimiter", "Comma")
    if choice == "Other":
        custom = settings.get("CustomDelimiter", "")
        return custom if custom else ","
    return _DELIMITER_MAP.get(choice, ",")


def get_new_path(path: str | Path) -> str:
    """Return the folder a processed copy of `path` should be written into."""
    cfg = ConfigManager()
    settings = cfg.get_value([CONFIG_KEY]) or {}
    use_source_folder = bool(settings.get("UseSourceFolder", True))
    processing_path = settings.get("ProcessingPath", "")

    resolved = Path(path).resolve()
    if use_source_folder:
        return os.path.dirname(resolved) + PROCESSED_SUBFOLDER
    if processing_path and Path(processing_path).is_dir():
        return processing_path
    # Custom path requested but empty/invalid: fall back to source folder
    # rather than crash or silently write to the working directory.
    return os.path.dirname(resolved) + PROCESSED_SUBFOLDER