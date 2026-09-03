"""
Convenient re-exports of all treatment functions.
"""
from .truncation import truncate
from .spike_removal import whitaker_hayes_despike, bridge_span
from .calibration import calibrate
from .smoothing import smooth
from .baseline import baseline_correct
from .normalization import normalize
from .peak_fitting import fit_peaks

__all__ = [
    "truncate",
    "whitaker_hayes_despike",
    "bridge_span",
    "calibrate",
    "smooth",
    "baseline_correct",
    "normalize",
    "fit_peaks",
]