# treatments/spike_removal.py
"""
Spike (cosmic-ray) removal for Raman spectra.

Detection: Whitaker-Hayes modified z-score on the *first-difference*
series of the spectrum, not on raw intensity (Whitaker, D.A. & Hayes, K.,
2018, "A simple algorithm for despiking Raman spectra", Chemometrics and
Intelligent Laboratory Systems). Working in the difference domain is what
lets the method tell a real, sharp Raman band apart from a cosmic-ray
spike: a genuine band still rises and falls over several pixels, so its
point-to-point steps stay moderate even when its peak height is large; a
cosmic-ray hit jumps almost instantly and drops back the next pixel, so
its point-to-point steps are extreme regardless of its height.

Correction: a flagged point is replaced by the mean of its *unflagged*
neighbours within a window, so the replacement value is not itself
contaminated by other nearby spike points.

Every corrected point/span is recorded as a structured event (index
range, wavenumber range, raw vs. corrected values) so both the automatic
pass and manual corrections can be logged identically and are
individually revertible. Event grouping, the ``spike_log`` shape, and
how these records accumulate across repeated calls are consumed by
``models.spectrum.RamanSpectrum`` (``add_step`` with ``merge_keys``).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _group_into_spans(flagged_idx: np.ndarray) -> List[Tuple[int, int]]:
    """Collapse a sorted array of individual flagged indices into contiguous
    (start, end) index spans, so a multi-pixel spike is logged as one event
    with a wavenumber *range*, rather than one event per pixel."""
    if flagged_idx.size == 0:
        return []
    spans: List[Tuple[int, int]] = []
    span_start = int(flagged_idx[0])
    prev = span_start
    for idx in flagged_idx[1:]:
        idx = int(idx)
        if idx == prev + 1:
            prev = idx
            continue
        spans.append((span_start, prev))
        span_start = idx
        prev = idx
    spans.append((span_start, prev))
    return spans


def _spike_events(
    x: np.ndarray,
    y_raw: np.ndarray,
    y_out: np.ndarray,
    spans: List[Tuple[int, int]],
    origin: str,
    method: str,
) -> List[Dict[str, Any]]:
    """Build one log record per (start, end) index span."""
    events = []
    for start, end in spans:
        events.append(
            {
                "event_id": uuid.uuid4().hex[:12],
                "origin": origin,               # "auto" | "manual"
                "method": method,                # "whitaker_hayes" | "linear_interpolation"
                "index_start": start,
                "index_end": end,
                "wavenumber_start": float(x[start]),
                "wavenumber_end": float(x[end]),
                "raw_values": [float(v) for v in y_raw[start : end + 1]],
                "corrected_values": [float(v) for v in y_out[start : end + 1]],
                "status": "active",              # "active" | "reverted"
            }
        )
    return events


def _result(
    data: np.ndarray,
    method: str,
    parameters: Dict[str, Any],
    description: str,
) -> Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]:
    return (
        data,
        method,
        ["Despiked", "Despiked"],
        ["Raman shift", "Intensity"],
        ["cm-1", "a. u."],
        parameters,
        description,
    )


# --------------------------------------------------------------------------- #
# Automatic detection & correction — Whitaker-Hayes
# --------------------------------------------------------------------------- #
def whitaker_hayes_despike(
    data: np.ndarray,
    threshold: float = 7.0,
    window: int = 5,
    protect_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]:
    """
    Detect and correct cosmic-ray spikes with the Whitaker-Hayes method.

    Parameters
    ----------
    data : np.ndarray
        Two-column spectrum (Raman shift, intensity).
    threshold : float, optional
        Modified z-score cutoff applied to the first-difference series
        (default 7.0). Lower values flag more points as spikes (higher
        risk of catching real sharp peaks); higher values are more
        conservative (higher risk of missing faint spikes).
    window : int, optional
        Number of neighbouring points (on each side, roughly) considered
        when computing the replacement value for a flagged point. Only
        *unflagged* neighbours within this window are averaged, so the
        replacement is not contaminated by other spike points nearby.
    protect_mask : np.ndarray of bool, optional
        Same length as ``data``. Points where this is True are never
        flagged, regardless of their score (protected Raman bands).

    Returns
    -------
    Standard treatment-function tuple (see other functions in this
    module). ``parameters["spike_log"]`` holds the structured list of
    corrected spans for this call (see module docstring).
    """
    if window < 1:
        raise ValueError("window must be a positive integer.")
    if threshold <= 0:
        raise ValueError("threshold must be positive.")

    x = data[:, 0]
    y = np.asarray(data[:, 1], dtype=float)
    n = len(y)

    if n < 3:
        # Not enough points to form a meaningful difference series.
        return _result(
            data.copy(),
            "Whitaker-Hayes",
            {"threshold": threshold, "window": window, "spike_log": []},
            "Spectrum too short for despiking; no changes made.",
        )

    # ------------------------------------------------------------------- #
    # 1. Detection: modified z-score on the first-difference series.
    # ------------------------------------------------------------------- #
    dY = np.diff(y)  # length n-1; dY[i] = y[i+1] - y[i]
    median_dY = np.median(dY)
    mad_dY = np.median(np.abs(dY - median_dY))
    robust_sigma = 1.4826 * mad_dY if mad_dY > 1e-9 else (np.std(dY) or 1.0)
    z = (dY - median_dY) / robust_sigma
    diff_spike = np.abs(z) > threshold  # length n-1

    # A spike between points i and i+1 implicates *both* points, since we
    # don't know a priori which side of the jump is the genuine value and
    # which is the spike; the window-based replacement below resolves it.
    point_mask = np.zeros(n, dtype=bool)
    point_mask[:-1] |= diff_spike
    point_mask[1:] |= diff_spike

    if protect_mask is not None:
        protect_mask = np.asarray(protect_mask, dtype=bool)
        if protect_mask.shape[0] != n:
            raise ValueError("protect_mask must be the same length as data.")
        point_mask &= ~protect_mask

    n_flagged = int(point_mask.sum())
    if n_flagged == 0:
        return _result(
            data.copy(),
            "Whitaker-Hayes",
            {"threshold": threshold, "window": window, "spike_log": []},
            "No spikes detected.",
        )

    # ------------------------------------------------------------------- #
    # 2. Correction: replace each flagged point with the mean of its
    #    unflagged neighbours within `window`. Neighbour means are always
    #    computed from the original (raw) intensities, so the order in
    #    which points are corrected never affects the result.
    # ------------------------------------------------------------------- #
    half = window // 2
    y_out = y.copy()
    flagged_idx = np.where(point_mask)[0]
    for i in flagged_idx:
        lo, hi = max(0, i - half), min(n, i + half + 1)
        neighbours = np.arange(lo, hi)
        usable = neighbours[~point_mask[neighbours]]
        if usable.size == 0:
            # Rare edge case: every neighbour in range is also flagged
            # (e.g. threshold set very low). Fall back to using them
            # anyway rather than leaving the point uncorrected.
            usable = neighbours
        y_out[i] = np.mean(y[usable])

    # ------------------------------------------------------------------- #
    # 3. Build the structured log (grouped into contiguous spans).
    # ------------------------------------------------------------------- #
    spans = _group_into_spans(flagged_idx)
    spike_log = _spike_events(x, y, y_out, spans, origin="auto", method="whitaker_hayes")

    cleaned = np.column_stack((x, y_out))
    description = (
        f"Whitaker-Hayes: corrected {n_flagged} point(s) across {len(spans)} "
        f"span(s) (threshold={threshold}, window={window})."
    )
    return _result(
        cleaned,
        "Whitaker-Hayes",
        {"threshold": threshold, "window": window, "spike_log": spike_log},
        description,
    )


def whitaker_hayes_scores(
    data: np.ndarray,
    protect_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Return the modified z-score for every point in the first-difference
    series (length ``len(data) - 1``), with protected points removed.

    Used to drive the diagnostic histogram in the GUI (shows where the
    chosen threshold sits relative to the spectrum's actual noise), kept
    separate from ``whitaker_hayes_despike`` so the histogram can be
    refreshed without re-running the correction step.
    """
    y = np.asarray(data[:, 1], dtype=float)
    if len(y) < 3:
        return np.array([])
    dY = np.diff(y)
    median_dY = np.median(dY)
    mad_dY = np.median(np.abs(dY - median_dY))
    robust_sigma = 1.4826 * mad_dY if mad_dY > 1e-9 else (np.std(dY) or 1.0)
    z = (dY - median_dY) / robust_sigma
    if protect_mask is not None:
        protect_mask = np.asarray(protect_mask, dtype=bool)
        # A diff index is left in the diagnostic view unless *both* points
        # it connects are protected.
        keep = ~(protect_mask[:-1] & protect_mask[1:])
        z = z[keep]
    return z


# --------------------------------------------------------------------------- #
# Manual correction — bridge a user-selected span
# --------------------------------------------------------------------------- #
def bridge_span(
    data: np.ndarray,
    start_wavenumber: float,
    end_wavenumber: float,
) -> Tuple[np.ndarray, str, List[str], List[str], List[str], Dict[str, Any], str]:
    """
    Manually correct a user-flagged span by linear interpolation between
    the nearest unflagged points *outside* the span (not the immediate
    edge pixels of the span itself, since a spike is often more than one
    pixel wide).

    Parameters
    ----------
    data : np.ndarray
        Two-column spectrum (Raman shift, intensity) — the *current*
        working data, not necessarily the raw input.
    start_wavenumber, end_wavenumber : float
        The wavenumber range to bridge, as selected by the user (a single
        click and a drag both resolve to a start/end pair; a single click
        has start == end).

    Returns
    -------
    Standard treatment-function tuple. ``parameters["spike_log"]`` holds
    a single-event list describing this correction.
    """
    if end_wavenumber < start_wavenumber:
        start_wavenumber, end_wavenumber = end_wavenumber, start_wavenumber

    x = data[:, 0]
    y = np.asarray(data[:, 1], dtype=float)
    n = len(y)

    span_mask = (x >= start_wavenumber) & (x <= end_wavenumber)
    if not np.any(span_mask):
        return _result(
            data.copy(),
            "Linear Interpolation",
            {"spike_log": []},
            f"No points found between {start_wavenumber} and {end_wavenumber} cm-1; no changes made.",
        )

    span_idx = np.where(span_mask)[0]
    start_idx, end_idx = int(span_idx[0]), int(span_idx[-1])

    y_out = y.copy()
    left_idx = start_idx - 1
    right_idx = end_idx + 1

    if left_idx >= 0 and right_idx < n:
        x_edges = [x[left_idx], x[right_idx]]
        y_edges = [y[left_idx], y[right_idx]]
        y_out[span_idx] = np.interp(x[span_idx], x_edges, y_edges)
    elif left_idx >= 0:
        # Span touches the end of the spectrum: nothing to bridge to on
        # the right, hold the last good value flat across the span.
        y_out[span_idx] = y[left_idx]
    elif right_idx < n:
        # Span touches the start of the spectrum: hold the first good
        # value flat across the span.
        y_out[span_idx] = y[right_idx]
    else:
        # The entire spectrum was selected — nothing outside it to
        # bridge from; leave the data unchanged.
        return _result(
            data.copy(),
            "Linear Interpolation",
            {"spike_log": []},
            "Selected span covers the entire spectrum; no changes made.",
        )

    spike_log = _spike_events(
        x, y, y_out, [(start_idx, end_idx)], origin="manual", method="linear_interpolation"
    )

    cleaned = np.column_stack((x, y_out))
    description = (
        f"Manual correction: bridged {end_idx - start_idx + 1} point(s) "
        f"between {start_wavenumber:.2f} and {end_wavenumber:.2f} cm-1."
    )
    return _result(
        cleaned,
        "Linear Interpolation",
        {"spike_log": spike_log},
        description,
    )
# --------------------------------------------------------------------------- #
# Backward-compatible aliases
# --------------------------------------------------------------------------- #
# Keep the old names as compatibility aliases for external callers. Internal
# code imports `whitaker_hayes_despike` directly.
despike = whitaker_hayes_despike
median_despike = whitaker_hayes_despike
