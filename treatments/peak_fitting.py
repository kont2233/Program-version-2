"""Peak-shape functions and multi-component peak fitting."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.optimize import curve_fit
from scipy.special import voigt_profile


def gaussian(x, amplitude, center, width):
    width = max(abs(width), np.finfo(float).eps)
    return amplitude * np.exp(-0.5 * ((x - center) / width) ** 2)


def lorentzian(x, amplitude, center, width):
    width = max(abs(width), np.finfo(float).eps)
    return amplitude / (1.0 + ((x - center) / width) ** 2)


def voigt(x, amplitude, center, width):
    width = max(abs(width), np.finfo(float).eps)
    return amplitude * voigt_profile(x - center, width, width)


_SHAPES = {"Gaussian": gaussian, "Lorentzian": lorentzian, "Voigt": voigt}


def component_values(x, peak):
    """Return y values for one ``[height, center, width, shape]`` record."""
    height, center, width, shape = peak
    return _SHAPES.get(shape, gaussian)(x, height, center, width)


def fit_peaks(
    data: np.ndarray,
    peak_guesses: List[Tuple[float, float, float]],
    bounds: Tuple[List[float], List[float]] | None = None,
    shapes: List[str] | None = None,
) -> tuple:
    """Fit multiple Gaussian/Lorentzian/Voigt components and return metadata."""
    if not peak_guesses:
        raise ValueError("At least one peak guess is required.")
    x, y = data[:, 0], data[:, 1]
    shapes = shapes or ["Gaussian"] * len(peak_guesses)
    if len(shapes) != len(peak_guesses):
        raise ValueError("One shape is required for each peak guess.")

    initial = [value for guess in peak_guesses for value in guess]
    if bounds is None:
        lower = [-np.inf] * len(initial)
        upper = [np.inf] * len(initial)
    else:
        lower, upper = bounds
        if len(lower) != len(initial) or len(upper) != len(initial):
            raise ValueError("Bounds length must match peak guesses.")

    def model(axis, *parameters):
        values = np.zeros_like(axis, dtype=float)
        for index, shape in enumerate(shapes):
            values += _SHAPES.get(shape, gaussian)(axis, *parameters[index * 3:index * 3 + 3])
        return values

    fitted_parameters, _ = curve_fit(model, x, y, p0=initial, bounds=(lower, upper), maxfev=20000)
    components = [
        [float(fitted_parameters[i]), float(fitted_parameters[i + 1]), abs(float(fitted_parameters[i + 2])), shapes[i // 3]]
        for i in range(0, len(fitted_parameters), 3)
    ]
    cumulative = np.column_stack((x, model(x, *fitted_parameters)))
    return (
        cumulative,
        "Peak Fitting",
        ["Cumulative fit", "Intensity"],
        ["Raman shift", "Intensity"],
        ["cm-1", "a. u."],
        {"peaks": components, "bounds": bounds},
        f"Fitted {len(components)} peaks.",
    )


_gaussian = gaussian
_multi_gaussian = lambda x, *params: sum(gaussian(x, *params[i:i + 3]) for i in range(0, len(params), 3))
