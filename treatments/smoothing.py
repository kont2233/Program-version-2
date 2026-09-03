# treatments/smoothing.py
from typing import Any, Dict, List, Tuple
import numpy as np
from scipy.signal import savgol_filter
from scipy.ndimage import gaussian_filter1d, uniform_filter1d


def smooth(
    data: np.ndarray,
    window_length: int = 11,
    polyorder: int = 3,
) -> Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]:
    """
    Smooth intensity values using a Savitzky‑Golay filter.

    Parameters
    ----------
    data : np.ndarray
        Two‑column spectrum.
    window_length : int, optional
        Length of the filter window (must be odd, default 11).
    polyorder : int, optional
        Polynomial order of the filter (default 3).

    Returns
    -------
    tuple[np.ndarray, str]
        (smoothed_data, description)
    """
    if window_length % 2 == 0 or window_length < 3:
        raise ValueError("window_length must be odd and ≥ 3.")
    if polyorder >= window_length:
        raise ValueError("polyorder must be < window_length.")

    smoothed_intensity = savgol_filter(data[:, 1], window_length, polyorder)
    smoothed = np.column_stack((data[:, 0], smoothed_intensity))
    description = (
        f"Smoothed with Savitzky‑Golay (window={window_length}, polyorder={polyorder})."
    )
    return _result(smoothed, "Savitzky-Golay", {"window_length": window_length, "polyorder": polyorder}, description)


def moving_average(
    data: np.ndarray,
    window: int = 5,
) -> Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]:
    """Smooth intensities with a centered moving-average window."""
    _validate_window(window)
    smoothed = np.column_stack((data[:, 0], uniform_filter1d(data[:, 1], size=window, mode="nearest")))
    return _result(smoothed, "Moving Average", {"window": window}, f"Smoothed with moving average (window={window}).")


def gaussian_smooth(
    data: np.ndarray,
    sigma: float = 2.0,
) -> Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]:
    """Smooth intensities with a one-dimensional Gaussian filter."""
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("sigma must be a positive finite number.")
    smoothed = np.column_stack((data[:, 0], gaussian_filter1d(data[:, 1], sigma=sigma, mode="nearest")))
    return _result(smoothed, "Gaussian", {"sigma": sigma}, f"Smoothed with Gaussian filter (sigma={sigma}).")


def _validate_window(window: int) -> None:
    if window < 3 or window % 2 == 0:
        raise ValueError("window must be an odd number of at least 3.")


def _result(data, method: str, parameters: Dict[str, Any], description: str):
    return (
        data,
        method,
        ["Smoothed", "Smoothed"],
        ["Raman shift", "Intensity"],
        ["cm-1", "a. u."],
        parameters,
        description,
    )
