# process.py
"""
Example driver script that demonstrates how to load many Raman spectra,
apply a user‑defined pipeline, and keep the processing history consistent.

Run it from a terminal:
    python process.py /path/to/spectra_folder --output /tmp/processed
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import List, Tuple, Dict

import numpy as np

# Local imports
from models.spectrum import RamanSpectrum
from treatments import (
    truncate,
    whitaker_hayes_despike,
    calibrate,
    smooth,
    baseline_correct,
    normalize,
    fit_peaks,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch Raman‑spectra processing.")
    parser.add_argument(
        "folder",
        type=str,
        help="Folder containing *.txt Raman spectra (two columns: shift \\t intensity).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="processed",
        help="Folder where processed spectra will be saved.",
    )
    # Optional flags to enable/disable treatments
    parser.add_argument("--no-calibration", action="store_true")
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument("--no-normalization", action="store_true")
    parser.add_argument("--no-peakfit", action="store_true")
    return parser.parse_args()


def build_pipeline(args: argparse.Namespace) -> List[Tuple[str, dict]]:
    """
    Return an ordered list of (step_name, kwargs) tuples according to the
    command-line switches.
    """
    pipeline = [
        ("truncation", {"min_shift": 100.0, "max_shift": 2000.0}),
        ("despiking", {"threshold": 7.0, "window": 5}),
        ("calibration", {"slope": 1.0, "intercept": 0.0}),
        ("smoothing", {"window_length": 11, "polyorder": 3}),
        ("baseline", {"lam": 1e5, "p": 0.01, "niter": 10}),
        ("normalization", {"method": "minmax"}),
        ("peak_fitting", {"peak_guesses": [(1000, 1500, 30)]}),  # dummy guess
    ]

    # Remove steps based on user flags
    if args.no_calibration:
        pipeline = [p for p in pipeline if p[0] != "calibration"]
    if args.no_baseline:
        pipeline = [p for p in pipeline if p[0] != "baseline"]
    if args.no_normalization:
        pipeline = [p for p in pipeline if p[0] != "normalization"]
    if args.no_peakfit:
        pipeline = [p for p in pipeline if p[0] != "peak_fitting"]
    return pipeline


def apply_step(
    spec: RamanSpectrum,
    step_name: str,
    kwargs: dict,
) -> None:
    """
    Dispatch to the appropriate treatment function and store the result
    inside ``spec`` using ``RamanSpectrum.add_step``.
    """
    # ------------------------------------------------------------------- #
    # 1️⃣ Determine which input data to feed the step.
    #    The most recent dataset is always used.
    # ------------------------------------------------------------------- #
    input_data = spec.current

    # ------------------------------------------------------------------- #
    # 2️⃣ Call the correct treatment.
    # ------------------------------------------------------------------- #
    if step_name == "truncation":
        spec.add_step("Truncated", *truncate(input_data, **kwargs))

    elif step_name == "despiking":
        spec.add_step("Despiked", *whitaker_hayes_despike(input_data, **kwargs))

    elif step_name == "calibration":
        calibration_result = calibrate(input_data, **kwargs)
        spec.add_step("calibrated", *calibration_result)

    elif step_name == "smoothing":
        smoothing_result = smooth(input_data, **kwargs)
        spec.add_step("smoothed", *smoothing_result)

    elif step_name == "baseline":
        baseline_result = baseline_correct(input_data, **kwargs)
        spec.add_step("baseline_corrected", *baseline_result)

    elif step_name == "normalization":
        normalization_result = normalize(input_data, **kwargs)
        spec.add_step("normalized", *normalization_result)

    elif step_name == "peak_fitting":
        # ``fit_peaks`` returns only the cumulative fit; we store it under
        # a dedicated name.  Individual peaks can be added later if needed.
        peak_result = fit_peaks(input_data, **kwargs)
        spec.add_step("peak_fitted", *peak_result)

    else:
        raise RuntimeError(f"Unsupported processing step '{step_name}'.")


def process_folder(folder: pathlib.Path, out_folder: pathlib.Path, pipeline: List[Tuple[str, dict]]) -> None:
    """
    Load every ``*.txt`` file in *folder*, run the *pipeline* and write the
    final spectrum (and optionally intermediate results) to *out_folder*.
    """
    txt_files = sorted(folder.glob("*.txt"))
    if not txt_files:
        print(f"[!] No *.txt files found in {folder!s}.", file=sys.stderr)
        return

    for txt in txt_files:
        try:
            spec = RamanSpectrum(txt, out_folder)
        except Exception as exc:
            print(f"[!] Skipping {txt.name}: {exc}", file=sys.stderr)
            continue

        print(f"\nProcessing {txt.name}")
        for step_name, kwargs in pipeline:
            try:
                apply_step(spec, step_name, kwargs)
                print(f"  • {step_name}: {spec.history[-1]['description']}")
            except Exception as exc:
                print(f"  ✖  Step '{step_name}' failed: {exc}", file=sys.stderr)
                # Stop further processing of this file – keep whatever we have.
                break

        # Export the **final** dataset and also the complete history as a CSV.
        final_name = spec.history[-1]["step_name"] if spec.history else "raw"
        spec.export_step(final_name, out_folder)

        # Optional: write a tiny log file that contains the processing chain.
        log_path = out_folder / f"{txt.stem}_log.txt"
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(spec.get_summary())

        print(f"  → saved {final_name} to {out_folder}")



def main() -> None:
    args = parse_args()
    folder = pathlib.Path(args.folder).expanduser().resolve()
    out_folder = pathlib.Path(args.output).expanduser().resolve()

    pipeline = build_pipeline(args)
    print("=== Raman batch processor ===")
    print(f"Input folder : {folder}")
    print(f"Output folder: {out_folder}")
    print("Pipeline steps (in order):")
    for i, (name, cfg) in enumerate(pipeline, 1):
        print(f"  {i}. {name}  {cfg}")

    process_folder(folder, out_folder, pipeline)


if __name__ == "__main__":
    main()
