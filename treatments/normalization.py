"""Intensity normalization algorithms."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def normalize(
    data: np.ndarray,
    method: str = "minmax",
    peak_shift: float | None = None,
    tolerance: float = 0.5,
    min_shift: float | None = None,
    max_shift: float | None = None,
    low_min_shift: float | None = None,
    low_max_shift: float | None = None,
    peak_min_shift: float | None = None,
    peak_max_shift: float | None = None,
    peak_shape: str = "Gaussian",
) -> tuple:
    """Normalize a two-column spectrum using whole or selected regions."""
    if data.ndim != 2 or data.shape[1] != 2 or len(data) == 0:
        raise ValueError("data must be a non-empty two-column spectrum.")

    if method in ("minmax", "zero_one"):
        low = float(np.min(data[:, 1]))
        high = float(np.max(data[:, 1]))
        parameters = {"method": "zero_one"}
        description = "Normalized to [0, 1]."
    elif method == "highest":
        high_region = _region(data, min_shift, max_shift)
        low_region = _region(data, low_min_shift, low_max_shift)
        low = float(np.min(low_region[:, 1]))
        high = float(np.max(high_region[:, 1]))
        parameters = {"method": method, "min_shift": min_shift, "max_shift": max_shift, "low_min_shift": low_min_shift, "low_max_shift": low_max_shift}
        description = "Normalized using selected highest and lowest regions."
    elif method == "peak":
        region = _region(data, peak_min_shift, peak_max_shift)
        if peak_shift is None:
            peak_shift = float(region[np.argmax(region[:, 1]), 0])
        index = int(np.argmin(np.abs(data[:, 0] - peak_shift)))
        if abs(float(data[index, 0]) - peak_shift) > tolerance:
            raise ValueError(f"No peak found within +/-{tolerance} cm-1.")
        scale = float(data[index, 1])
        if scale == 0:
            raise ValueError("Reference peak intensity is zero.")
        normalized = np.column_stack((data[:, 0], data[:, 1] / scale))
        parameters = {"method": method, "peak_shift": peak_shift, "peak_min_shift": peak_min_shift, "peak_max_shift": peak_max_shift, "tolerance": tolerance, "peak_shape": peak_shape}
        return _result(normalized, "Peak", parameters, f"Normalized to peak at {data[index, 0]:.4f} cm-1.")
    else:
        raise ValueError(f"Unsupported normalization method '{method}'.")

    if high == low:
        raise ValueError("Normalization bounds must not be equal.")
    normalized = np.column_stack((data[:, 0], (data[:, 1] - low) / (high - low)))
    return _result(normalized, "Highest" if method == "highest" else "0 to 1", parameters, description)


def _region(data: np.ndarray, start: float | None, end: float | None) -> np.ndarray:
    region = data
    if start is not None:
        region = region[region[:, 0] >= start]
    if end is not None:
        region = region[region[:, 0] <= end]
    if region.size == 0:
        raise ValueError("The selected normalization region contains no data.")
    return region


def _result(data, method: str, parameters: Dict[str, Any], description: str):
    return data, method, ["Normalized", "Intensity"], ["Raman shift", "Intensity"], ["cm-1", "a. u."], parameters, description
