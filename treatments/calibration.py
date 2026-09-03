# treatments/calibration.py
from typing import Any, Dict, List, Tuple
import numpy as np


def calibrate(
    data: np.ndarray, slope: float, intercept: float
) -> Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]:
    """
    Apply a linear calibration to the Raman shift axis.

    NewShift = slope * OldShift + intercept

    Parameters
    ----------
    data : np.ndarray
        Two-column spectrum.
    slope, intercept : float
        Calibration coefficients.

    Returns
    -------
    tuple[np.ndarray, str]
        (calibrated_data, description)
    """
    if not np.isfinite(slope) or not np.isfinite(intercept):
        raise ValueError("Calibration coefficients must be finite numbers.")

    calibrated_shift = slope * data[:, 0] + intercept
    calibrated = np.column_stack((calibrated_shift, data[:, 1]))
    description = f"Calibrated (shift = {slope:.6g}·shift + {intercept:.6g})."
    return (
        calibrated,
        "Linear Calibration",
        ["Calibrated", "Intensity"],
        ["Raman shift", "Intensity"],
        ["cm-1", "a. u."],
        {"slope": slope, "intercept": intercept},
        description,
    )