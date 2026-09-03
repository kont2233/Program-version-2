# treatments/truncation.py
from typing import Tuple, List, Dict, Any
import numpy as np


def truncate(
    data: np.ndarray, min_shift: float, max_shift: float
) -> Tuple[np.ndarray, str, str, List[str], Dict[str, Any], str]:
    """
    Crop the spectrum to the interval [min_shift, max_shift].

    Parameters
    ----------
    data : np.ndarray
        Two-column (shift, intensity) array.
    min_shift, max_shift : float
        Desired limits of the Raman shift axis.

    Returns
    -------
    tuple[np.ndarray, str]
        (cropped_data, description)
    """
    if min_shift >= max_shift:
        raise ValueError("min_shift must be smaller than max_shift - changed it around")

    mask = (data[:, 0] >= min_shift) & (data[:, 0] <= max_shift)
    new_data = data[mask]

    if new_data.size == 0:
        raise ValueError(
            f"No data points fall inside the interval [{min_shift}, {max_shift}]."
        )

    method: str = "Truncation"
    column_header: List[str] = ["Truncated","Truncated"]
    column_names: List[str] = ["Raman shift", "Intensity"]
    units: List[str] = ["cm-1", "a. u."]
    parameters: Dict[str, Any] = {"min": min_shift,"max": max_shift}
    description: str = f"Truncated to [{min_shift}, {max_shift}] cm⁻¹ ({new_data.shape[0]} points)."

    return new_data, method, column_header, column_names, units, parameters, description
