# treatments/baseline.py
from typing import Any, Dict, List, Tuple
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.interpolate import interp1d, UnivariateSpline


def _als_baseline(intensity: np.ndarray, lam: float = 1e5, p: float = 0.01, niter: int = 10):
    """
    Asymmetric Least Squares baseline correction algorithm (Eilers, 2005).

    Returns the estimated baseline.
    """
    L = len(intensity)
    D = sparse.diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(L - 2, L))
    D = lam * D.transpose().dot(D)  # smoothness penalty matrix, shape (L, L)

    w = np.ones(L)
    for _ in range(niter):
        W = sparse.spdiags(w, 0, L, L)
        Z = W + D
        z = spsolve(Z.tocsr(), w * intensity)
        w = p * (intensity > z) + (1 - p) * (intensity < z)
    return z


def baseline_correct(
    data: np.ndarray, lam: float = 1e5, p: float = 0.01, niter: int = 10
) -> Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]:
    """
    Estimate and subtract a baseline using the Asymmetric Least Squares method.

    Parameters
    ----------
    data : np.ndarray
        Two-column spectrum.
    lam, p, niter : float/int, optional
        Algorithm parameters (default values work well for most Raman data).

    Returns
    -------
    tuple[np.ndarray, str]
        (baseline-corrected data, description)
    """
    baseline = _als_baseline(data[:, 1], lam=lam, p=p, niter=niter)
    corrected_intensity = data[:, 1] - baseline
    corrected = np.column_stack((data[:, 0], corrected_intensity))
    description = f"Baseline corrected (λ={lam:.0e}, p={p}, iterations={niter})."
    return _result(corrected, "ALS", {"lam": lam, "p": p, "niter": niter}, description)


def polynomial_baseline(data: np.ndarray, degree: int = 2) -> tuple:
    """Fit and subtract a polynomial baseline from the spectrum."""
    if degree < 0 or degree > 12:
        raise ValueError("degree must be between 0 and 12.")
    coefficients = np.polyfit(data[:, 0], data[:, 1], degree)
    baseline = np.polyval(coefficients, data[:, 0])
    corrected = np.column_stack((data[:, 0], data[:, 1] - baseline))
    return _result(corrected, "Polynomial", {"degree": degree}, f"Polynomial baseline corrected (degree={degree}).")


def snip_baseline(data: np.ndarray, iterations: int = 20) -> tuple:
    """Estimate a baseline using the iterative SNIP clipping procedure."""
    if iterations < 1:
        raise ValueError("iterations must be positive.")
    baseline = data[:, 1].astype(float).copy()
    for width in range(1, min(iterations, len(baseline) // 2) + 1):
        left = np.roll(baseline, width)
        right = np.roll(baseline, -width)
        candidate = (left + right) / 2
        baseline[width:-width] = np.minimum(baseline[width:-width], candidate[width:-width])
    corrected = np.column_stack((data[:, 0], data[:, 1] - baseline))
    return _result(corrected, "SNIP", {"iterations": iterations}, f"SNIP baseline corrected ({iterations} iterations).")


def constant_baseline(data: np.ndarray, mode: str = "Mean", value: float = 0.0) -> tuple:
    """Subtract a constant baseline selected from common statistics or a value."""
    if mode == "Min":
        baseline = float(np.min(data[:, 1]))
    elif mode == "Max":
        baseline = float(np.max(data[:, 1]))
    elif mode == "Median":
        baseline = float(np.median(data[:, 1]))
    elif mode == "Custom":
        baseline = float(value)
    else:
        baseline = float(np.mean(data[:, 1]))
    corrected = np.column_stack((data[:, 0], data[:, 1] - baseline))
    return _result(corrected, "Constant", {"mode": mode, "value": baseline}, f"Constant baseline corrected ({mode}: {baseline:.6g}).")


def custom_baseline(data: np.ndarray, points: list, connection: str = "Linear", fit_points: bool = False) -> tuple:
    """Subtract a baseline interpolated through user-defined anchor points."""
    if len(points) < 2:
        raise ValueError("At least two custom baseline points are required.")
    anchors = np.asarray(points, dtype=float)
    if anchors.ndim != 2 or anchors.shape[1] != 2:
        raise ValueError("Custom baseline points must contain shift and intensity pairs.")
    order = np.argsort(anchors[:, 0])
    anchors = anchors[order]
    if np.any(np.diff(anchors[:, 0]) <= 0):
        raise ValueError("Custom baseline point positions must be unique.")
    if fit_points:
        anchors[:, 1] = np.interp(anchors[:, 0], data[:, 0], data[:, 1])

    if connection in ("Spline", "BSpline"):
        interpolator = UnivariateSpline(anchors[:, 0], anchors[:, 1], s=0, k=min(3, len(anchors) - 1))
    else:
        interpolator = interp1d(anchors[:, 0], anchors[:, 1], kind="linear", fill_value="extrapolate")
    baseline = np.asarray(interpolator(data[:, 0]), dtype=float)
    corrected = np.column_stack((data[:, 0], data[:, 1] - baseline))
    return _result(corrected, "Custom", {"points": anchors.tolist(), "connection": connection, "fit_points": fit_points}, "Custom baseline corrected.")


def _result(data, method: str, parameters: Dict[str, Any], description: str):
    return data, method, ["Baseline corrected", "Intensity"], ["Raman shift", "Intensity"], ["cm-1", "a. u."], parameters, description
