# spectra.py
"""
Raman spectrum container and processing manager.

The :class:`RamanSpectrum` class keeps:

* ``raw`` - the un-modified two-column data (shift, intensity)
* ``datasets`` - a dictionary mapping *step name* → processed ndarray
* ``history`` - an ordered list of dictionaries describing each performed step

Processing steps are **stateless** - they are implemented in the
``treatments`` module and *do not* modify the original array.  The class
takes care of chaining steps, re-running downstream steps when an
earlier step is altered, and exposing the latest spectrum via the
``current`` property.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import numpy as np

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #
def _load_txt(file_path: Path, delimiter: str) -> np.ndarray:
    """
    Load a two-column Raman spectrum from a tab-separated ``*.txt`` file.

    Parameters
    ----------
    file_path: Path
        Path to the file to read.

    Returns
    -------
    np.ndarray
        2-D array with shape ``(n_points, 2)`` - columns are ``shift`` and ``intensity``.

    Raises
    ------
    FileNotFoundError
        If ``file_path`` does not exist.
    ValueError
        If the file cannot be parsed into two numeric columns.
    """
    if not file_path.is_file():
        raise FileNotFoundError(str(file_path))

    candidates = [delimiter, "\t", ",", ";", None]
    tried = set()
    detected_delimiter = None
    header_count = 0
    found_data = False
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    for candidate in candidates:
        if candidate in tried:
            continue
        tried.add(candidate)
        for line_number, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            fields = stripped_line.split(candidate) if candidate else stripped_line.split()
            try:
                values = [float(field) for field in fields]
            except ValueError:
                continue
            if len(values) == 2:
                detected_delimiter = candidate
                header_count = line_number
                found_data = True
                break
        if found_data:
            break

    if not found_data:
        raise ValueError(f"Could not detect two numeric columns in {file_path!s}.")

    try:
        data = np.loadtxt(
            file_path,
            delimiter=detected_delimiter,
            skiprows=header_count,
            dtype=float,
        )
    except Exception as exc:
        raise ValueError(f"Could not read {file_path!s} as a two-column txt file.") from exc

    if data.ndim == 1:
        data = data.reshape(1, -1)

    if data.ndim != 2 or data.shape[1] != 2:
        raise ValueError(f"File {file_path!s} must contain exactly two columns (shift, intensity).")

    # Sort by Raman shift just in case the file is not ordered
    data = data[data[:, 0].argsort()]
    return data

def _get_metadata(file_path: Path) -> Dict[str, str]:
    # Placeholder implementation - actual metadata extraction logic would go here
    return {}

def _save_txt(file_path: Path):
    return
# --------------------------------------------------------------------------- #
# Core class
# --------------------------------------------------------------------------- #
class RamanSpectrum:
    """
    Container for a single Raman spectrum and its successive processing steps.

    Parameters
    ----------
    file_path : str | Path
        Path to the raw ``.txt`` file (two columns: shift \\t intensity).

    Attributes
    ----------
    raw : np.ndarray
        Unmodified data loaded from ``file_path``.
    datasets : dict[str, np.ndarray]
        Mapping ``step_name`` → processed data array.  The key ``"raw"``
        always points to the original data.
    history : list[dict]
        Ordered record of all performed steps.  Each record contains
        ``'step'``, ``'params'`` and ``'description'`` entries.
    """

    def __init__(self, file_path: str | Path, new_path: str | Path | None, delimiter: str = ","):
        self._raw_path = Path(file_path).expanduser().resolve()
        self.raw = _load_txt(self._raw_path, delimiter)
        self._name = self._raw_path.stem
        self._path = Path(str(Path(new_path).expanduser().resolve()) + "/" + self._name + ".txt")

        # ``datasets`` always contains the raw spectrum; other keys are added later.
        self.datasets: Dict[str, np.ndarray] = {"raw": self.raw.copy()}

        # History is a list of dicts; each dict stores what was done.
        self.history: List[Dict] = []
        self.history.append(
                    {
                        "step_name": "raw",
                        "method_name" : "raw",
                        "column_header": ["Raman Shift","Intensity"],
                        "params": "",
                        "description": f"raw data from {str(file_path)}",
                        "column_names": ["Raw Data x", "Raw Data y"],
                        "units": ["cm-1","a. u."],
                    })

    # ------------------------------------------------------------------- #
    # Public API
    # ------------------------------------------------------------------- #
    @property
    def current(self) -> np.ndarray:
        """
        Return the most recent processed spectrum (the output of the latest step).

        If no processing has been performed, the raw data is returned.
        """
        
        if not self.history:
            return self.datasets["raw"]
        last_step = self.history[-1]["step_name"]
        n: np.ndarray = self.get_step_dataset_with_data(last_step)["data"]
        if n.ndim > 2:
            match last_step:
                case "Baseline":
                    n = n[:, [n.ndim-2,n.ndim-1]] #last two columns
                    return n
                case "Peak-Fitting":
                    last_step = self.history[len(self.history)-2]["step_name"]
                    n: np.ndarray = self.get_step_dataset_with_data(last_step)["data"]
                    if n.ndim>2:
                        n = n[:, [0, 1]] # first two columns
                    else:
                        n = n[:, [n.ndim-2,n.ndim-1]] #last two columns
                    return n
                case _:
                    n = n[:, n.ndim-2]
                    n = n[:, n.ndim-1]
                    return n
        else:
            return n
        return n

    @property
    def raw_path(self) -> Path:
        """Return the path to the raw spectrum file."""
        return self._raw_path
    @property
    def path(self) -> Path:
            """Return the path to the raw spectrum file."""
            return self._path
    @property
    def name(self) -> str:
        """Return the name of the spectrum (derived from the raw file name)."""
        return self._name
    
    def set_path(self, new_path: str | Path) -> None:
        """Set a new path for the spectrum file."""
        self._path = Path(new_path).expanduser().resolve()
        #self._name = self._path.stem

    def add_step(
        self,
        step_name: str,
        data: np.ndarray,
        method_name: str,
        column_header: List[str] = [],
        column_names: List[str] = [],
        units: List[str] = [],
        params: Optional[dict] = None,
        description: str = "",
        merge_keys: Optional[List[str]] = None,
    ) -> None:
        """
        Store the result of a processing step and update the history.

        Parameters
        ----------
        step_name : str
            Unique identifier for the step (e.g. ``"truncation"``,
            ``"calibration"``, ``"smoothed"`` …).  The same name can be
            reused later - the old entry will be overwritten, and all
            downstream steps will be discarded and need to be recomputed.
        data : np.ndarray
            Two-column array produced by the treatment function.
        params : dict | None
            Parameters that were used for the step (saved for reproducibility).
        description : str
            Human-readable description of what the step did.
        merge_keys : list[str] | None
            Optional list of ``params`` keys that should be *merged* rather
            than replaced when ``step_name`` already exists in history. For
            each key in ``merge_keys``, if the existing entry's ``params``
            has that key as a list and the new ``params`` also has it as a
            list, the stored value becomes ``old list + new list`` instead
            of the new list overwriting the old one. This lets a step that
            re-runs on the same data (e.g. despiking after a manual
            correction) log only its own new events, while previously
            logged events are preserved. Has no effect when ``step_name``
            is new, or when omitted (default ``None`` - existing callers
            are completely unaffected).
        """
        # ------------------------------------------------------------------- #
        # 1. Consistency check - ensure the array has the right shape.
        # ------------------------------------------------------------------- #
        if data.ndim != 2 or data.shape[1] != 2:
            raise ValueError("All spectrum datasets must be two-column (shift, intensity).")

        # ------------------------------------------------------------------- #
        # 2. If the step already exists, wipe it and all later steps.
        # ------------------------------------------------------------------- #
        step_names = [h["step_name"] for h in self.history]
        if step_name in step_names:
            idx = step_names.index(step_name)

            # Merge selected list-valued params with the entry being
            # overwritten, before it is discarded below.
            if merge_keys:
                old_params = self.history[idx].get("params") or {}
                merged_params = dict(params) if params else {}
                for key in merge_keys:
                    old_val = old_params.get(key)
                    new_val = merged_params.get(key)
                    if isinstance(old_val, list) and isinstance(new_val, list):
                        merged_params[key] = old_val + new_val
                params = merged_params

            # Remove downstream datasets & history entries
            for downstream in step_names[idx:]:
                self.datasets.pop(downstream, None)
            self.history = self.history[:idx]

        # ------------------------------------------------------------------- #
        # 3. Store the new dataset and extend the history.
        # ------------------------------------------------------------------- #
        self.datasets[step_name] = data.copy()
        self.history.append(
            {
                "step_name": step_name,
                "method_name" : method_name,
                "column_header": column_header,
                "column_names": column_names,
                "units": units,
                "params": params or {},
                "description": description,
            }
        )

    def revert_spike_event(self, step_name: str, event_id: str) -> None:
        """
        Undo a single previously logged spike-correction event.

        Looks up ``step_name`` in ``history``, finds the matching event
        (by ``event_id``) inside that step's ``params["spike_log"]``,
        writes its ``raw_values`` back into the stored dataset at
        ``index_start:index_end + 1``, and marks the event
        ``"status": "reverted"`` in place (the record is kept, not
        removed, so the log stays a full audit trail).

        Since the dataset for ``step_name`` changes, any steps computed
        after it are no longer valid and are discarded - the same way
        :meth:`add_step` discards downstream steps when a step is
        recomputed. ``step_name``'s own history entry and dataset are
        kept (with the reverted value and mutated spike_log); only what
        comes after it is removed.

        Parameters
        ----------
        step_name : str
            The history step whose spike_log should be searched (e.g.
            ``"Despiked"``).
        event_id : str
            The ``event_id`` of the spike_log entry to revert.

        Raises
        ------
        KeyError
            If ``step_name`` is not found in history, or no event with
            ``event_id`` exists in that step's spike_log.
        """
        step_names = [h["step_name"] for h in self.history]
        if step_name not in step_names:
            raise KeyError(f"Step '{step_name}' not found in history.")
        idx = step_names.index(step_name)
        entry = self.history[idx]

        spike_log = (entry.get("params") or {}).get("spike_log")
        if not spike_log:
            raise KeyError(f"No spike_log found for step '{step_name}'.")

        event = next((e for e in spike_log if e.get("event_id") == event_id), None)
        if event is None:
            raise KeyError(
                f"Event '{event_id}' not found in spike_log for step '{step_name}'."
            )

        if event["status"] == "reverted":
            return  # Already reverted - idempotent, nothing further to do.

        # ------------------------------------------------------------------- #
        # Write the raw values back into the stored dataset.
        # ------------------------------------------------------------------- #
        start, end = event["index_start"], event["index_end"]
        dataset = self.datasets[step_name]
        dataset[start : end + 1, 1] = event["raw_values"]

        event["status"] = "reverted"

        # ------------------------------------------------------------------- #
        # Invalidate downstream steps only - step_name's own entry and
        # dataset survive with the reverted value.
        # ------------------------------------------------------------------- #
        for downstream in step_names[idx + 1 :]:
            self.datasets.pop(downstream, None)
        self.history = self.history[: idx + 1]

    # ------------------------------------------------------------------- #
    # Convenience helpers for external scripts
    # ------------------------------------------------------------------- #
    def get_step_data(self, name: str) -> np.ndarray:
        """
        Return a stored dataset by name.

        Parameters
        ----------
        name : str
            Name of the dataset (e.g. ``"raw"``, ``"truncated"``, ``"smoothed"``,
            ``"baseline_corrected"``, …).

        Raises
        ------
        KeyError
            If the requested dataset does not exist.
        """
        if name not in self.datasets:
            raise KeyError(f"Dataset '{name}' not found in this spectrum.")
        return self.datasets[name].copy()

    def get_summary(self) -> str:
        """
        Produce a short multi-line string summarising the current state of the object.
        """
        lines = [
            f"Spectrum: {self._raw_path.name}",
            f"  Points (raw): {self.raw.shape[0]}",
            "  Processing history:",
        ]
        if not self.history:
            lines.append("    - none")
        else:
            for rec in self.history:
                lines.append(
                    f"    • {rec['step_name']}: {rec['description']} (params={rec['params']})"
                )
        return "\n".join(lines)

    # ------------------------------------------------------------------- #
    # Export helpers
    # ------------------------------------------------------------------- #
    def export_step(self, step_name: str, folder: str | Path) -> Path:
        """
        Write a processed dataset to a tab-separated txt file.

        Parameters
        ----------
        step_name : str
            The dataset to export (must exist in ``self.datasets``).
        folder : str | Path
            Destination folder - will be created if it does not exist.

        Returns
        -------
        Path
            Full path to the written file.
        """
        data = self.get_step_data(step_name)
        out_dir = Path(folder).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{self._raw_path.stem}_{step_name}.txt"
        np.savetxt(out_file, data, fmt="%s", delimiter="\t")
        return out_file

    def get_step_dataset_with_data(self, step: str) -> Dict[str, Any]:
        data = self.dataset_into_history()
        for idx, item in enumerate(data):
            if item.get("step_name") == step:
                return data[idx]
    
    def dataset_into_history(self) -> List[Dict]:
        n = self.history.copy()
        for h in n:
            h["data"] = self.datasets[h["step_name"]]
        return n


    def get_full_dataset(self,
        headers: List[str] = None,
    ) -> np.ndarray:
    
        # --------------------------------------------------------------------- #
        # Basic validation
        # --------------------------------------------------------------------- #
        if len(self.datasets) != len(self.history):
            raise ValueError(
                f"`datasets` (size {len(self.datasets)}) and `history` (size {len(self.history)}) "
                "must contain the same number of steps (except raw)."
            )

        # Preserve the insertion order of the dict (Python ≥3.7 guarantees it)
        step_names = list(self.datasets.keys())

        # --------------------------------------------------------------------- #
        # Determine the overall shape of the output matrix
        # --------------------------------------------------------------------- #
        # Number of data rows = max rows among all datasets (padding with NaN later)
        data_rows = max(
            arr.shape[0] if arr.ndim > 1 else 1 for arr in self.datasets.values()
        )

        # Total number of columns = sum of columns of each dataset
        total_columns = sum(
            arr.shape[1] if arr.ndim > 1 else 1 for arr in self.datasets.values()
        )

        # How many header rows do we need?
        header_rows = len(headers) # step-name row is always present

        # Allocate the final array (object dtype to hold strings & numbers)
        result = np.full(
            (header_rows + data_rows, total_columns), np.nan, dtype=object
        )

        # --------------------------------------------------------------------- #
        # Fill the matrix column by column
        # --------------------------------------------------------------------- #
        col_offset = 0
        for idx, step in enumerate(step_names):
            arr = self.datasets[step]

            # Normalise the dataset to a 2-D column-major shape
            if arr.ndim == 1:
                arr = arr.reshape(-1, 1)          # (n_rows, 1)
            elif arr.ndim == 2:
                pass                               # already (n_rows, n_cols)
            else:
                raise ValueError(
                    f"Dataset for step `{step}` must be 1-D or 2-D, got {arr.ndim}-D."
                )

            n_rows, n_cols = arr.shape

            # ----- Header rows ------------------------------------------------ #
            # Row 0 - step name
            #result[0, col_offset : col_offset + n_cols] = step

            # Row for history_key1 (if not omitted)
            header_cursor = 0
            for h in headers:
                val = ""
                match h:
                    case "column_names + units":
                        val = []
                        for x in range(len(self.history[idx].get("column_names", np.nan))):
                            val.append(self.history[idx].get("column_names", np.nan)[x] + " " + self.history[idx].get("units", np.nan)[x])
                            print(f"idx is {idx} x is {x} length is {len(self.history[idx].get('column_names', np.nan))} appendix is {self.history[idx].get('column_names', np.nan)[x]}")
                    case "parameters":
                        val = self.history[idx].get("parameters", np.nan)
                        if isinstance(val, Dict):
                            val=""
                            for k in self.history[idx].get("parameters", np.nan).keys():
                                val += str(k) + ": " + self.history[idx].get("parameters", np.nan)[k]
                        else:
                            val = "param: " + str(val)
                    case "step_name + method_name":
                        val = self.history[idx].get("step_name", np.nan) + " - " + self.history[idx].get("method_name", np.nan)
                    case "":
                        val = ""
                    case _:
                        val = self.history[idx].get(h, np.nan)
                print(f"{h}: {val}")
                result[header_cursor, col_offset : col_offset + n_cols] = val
                header_cursor += 1


            # ----- Data rows --------------------------------------------------- #
            data_start = header_rows
            # Pad with NaN if this dataset has fewer rows than the global max
            result[data_start : data_start + n_rows,
                col_offset : col_offset + n_cols] = arr

            col_offset += n_cols

        return result