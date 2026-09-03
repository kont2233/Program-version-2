import json
import os
import threading
import sys
from typing import Any, Dict, List, MutableMapping, Optional
from pathlib import Path
from models.singleton_meta import  SingletonMeta

DEFAULT_CONFIG_FILE = "config/default.json"
LAST_CONFIG_FILE = "config/last.json"
CREATE_IF_MISSING = True
ENC = "utf-8"

class _SingletonMeta(type):
    """
    A metaclass that creates exactly one instance of the class that uses it.
    Thread‑safe: the first thread that asks for the instance creates it,
    all subsequent calls receive the same object.
    """
    _instances: Dict[type, Any] = {}
    _lock = threading.Lock()          # protects _instances dict

    def __call__(cls, *args, **kwargs):
        # Double‑checked locking pattern
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]

class ConfigManager(metaclass=SingletonMeta):

    def __init__(self) -> None:
        self.file_path = Path(LAST_CONFIG_FILE)
        self.encoding = ENC

        if not Path(DEFAULT_CONFIG_FILE).exists():
            self._write_json(Path(DEFAULT_CONFIG_FILE), {})
        if not Path(LAST_CONFIG_FILE).exists():
                    self._write_json(Path(LAST_CONFIG_FILE), {})

        # Load once – subsequent calls use the in‑memory dict and write back on changes.
        self._last: Dict[str, Any] = self._read_json(self.file_path)
        self._default: Dict[str, Any] = self._read_json(Path(DEFAULT_CONFIG_FILE))

    # --------------------------------------------------------------------- #
    #                         Private helpers                               #
    # --------------------------------------------------------------------- #

    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        """Read the JSON file and return its content as a dict."""
        try:
            with file_path.open("r", encoding=self.encoding) as f:
                content = json.load(f)
                if not isinstance(content, dict):
                    raise ValueError("Root element of the JSON file must be an object.")
                return content
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {file_path}: {exc}") from exc

    def _write_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Write the provided dict to the JSON file atomically."""
        tmp_path = file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding=self.encoding) as f:
            json.dump(data, f, indent=4, sort_keys=True)
        tmp_path.replace(file_path)  # atomic on most POSIX systems

    

    def _get_value(self, data: Dict[str, Any], path: List[str])-> Optional[Dict[str, Any]]:
        
        parent = _traverse(data, path[:-1], create_missing=False)
        leaf_key = path[-1]
        
        if leaf_key not in parent:
            raise KeyError(f"Key {'/'.join(path)!r} not found.")
        leaf = parent[leaf_key]
        
        if not isinstance(leaf, dict):
            raise TypeError(
                f"Value at {'/'.join(path)!r} is not a dictionary (got {type(leaf).__name__})."
            )
        return leaf
    # --------------------------------------------------------------------- #
    #                         Public API                                    #
    # --------------------------------------------------------------------- #


    def get_value(self, path: List[str]) -> Optional[Dict[str, Any]]:
        """
        Retrieve the dictionary stored at ``path``.

        Parameters
        ----------
        path : list[str]     List of parent-node keys leading to the desired location.

        Returns
        -------
        dict | None    The stored dictionary, or ``None`` if the location exists but does not contain a dictionary.

        Raises
        ------
        KeyError      If any part of ``path`` does not exist.
        TypeError     If the final value is not a dictionary.
        """
        if not path:
            # Empty path means “return the whole config”.
            return self._data

        parent = _traverse(self._last, path[:-1], create_missing=False)
        leaf_key = path[-1]

        if leaf_key not in parent:
            parent = _traverse(self._default, path[:-1], create_missing=True)
            leaf_key = path[-1]
            print(f"Key {'/'.join(path)!r} not found. - Getting Default Value")
        leaf = parent[leaf_key]

        if not isinstance(leaf, dict):
            raise TypeError(
                f"Value at {'/'.join(path)!r} is not a dictionary (got {type(leaf).__name__})."
            )
        return leaf

    def get_default_value(self, path: List[str], fallback: Any = None) -> Any:
        """Return a value from default.json without changing last.json."""
        current: Any = self._default
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return fallback
            current = current[key]
        return current

    def set_value(self, path: List[str], data: Dict[str, Any]) -> None:
        """
        Store ``value`` (must be a dictionary) at ``path``. Intermediate dictionaries are created automatically.

        Parameters
        ----------
        path : list[str]    List of parent-node keys that locate where to store the value.
        value : dict        The dictionary to be saved.

        Raises
        ------
        TypeError
            If ``value`` is not a dictionary.
        """
        if not isinstance(data, dict):
            raise TypeError("kwargs must be a dict")

        if not path:
            # Empty path replaces the whole configuration.
            #self._data = value
            #self._write_json(self._data)
            return

        parent = _traverse(self._last, path[:-1], create_missing=True)
        leaf_key = path[-1]
        parent[leaf_key] = data
        self._write_json(self.file_path, self._last)

    def delete(self, path: List[str]) -> None:
        """
        Delete the entry located at ``path``.

        Parameters
        ----------
        path : list[str]
            List of keys identifying the entry to delete.

        Raises
        ------
        KeyError
            If the specified path does not exist.
        """
        if not path:
            raise ValueError("Path must contain at least one key to delete.")

        parent = _traverse(self._last, path[:-1], create_missing=False)
        leaf_key = path[-1]

        if leaf_key not in parent:
            raise KeyError(f"Key {'/'.join(path)!r} not found.")
        del parent[leaf_key]
        self._write_json(self._data)

    def reload(self) -> None:
        """Re-read the JSON file, discarding any in‑memory changes."""
        self._last = self._read_json()

    def dump(self) -> str:
        """
        Return a pretty‑printed JSON string of the current in‑memory config.
        Useful for debugging or logging.
        """
        return json.dumps(self._data, indent=4, sort_keys=True)

    def change_config(self, file_path: Path):
        self._last = self._read_json(file_path)

    def exit_saves(self):
        self._write_json(Path(LAST_CONFIG_FILE), self._last)

def get_config_manager() -> ConfigManager:
    """
    Return the global ``ConfigManager`` instance.

    Using a helper function makes the intent explicit:
        >>> from config_manager import get_config_manager
        >>> cfg = get_config_manager()
    """
    return ConfigManager()          # the metaclass guarantees a single instance

def _traverse(
    data: Dict[str, Any],
    keys: List[str],
    create_missing: bool = False,
) -> MutableMapping[str, Any]:
    """
    Walk through the nested dict according to ``keys`` and
    return the deepest dictionary reached.

    Parameters
    ----------
    keys : list[str]
        Sequence of keys that describe the path.
    create_missing : bool
        If ``True`` missing intermediate dictionaries are created.

    Returns
    -------
    dict
        The dictionary that corresponds to the deepest level.

    Raises
    ------
    KeyError
        If a key in the path does not exist and ``create_missing`` is ``False``.
    TypeError
        If a non‑dict object is encountered while traversing.
    """
    current: MutableMapping[str, Any] = data
    for i, key in enumerate(keys):
        if not isinstance(current, dict):
            raise TypeError(
                f"Expected a dict at {'/'.join(keys[:i])!r}, "
                f"found {type(current).__name__}."
            )
        if key not in current:
            if create_missing:
                current[key] = {}
            else:
                raise KeyError(f"Key {'/'.join(keys[: i + 1])!r} not found.")
        current = current[key]  # type: ignore[assignment]
    return current
