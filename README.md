# ECPypsi

ECPypsi is a PySide6 desktop application for evaluating Raman spectra. It imports two-column Raman data, displays multiple spectra, previews processing steps, stores treatment history, and exports processed datasets.

## Current capabilities

- Import comma- or delimiter-separated two-column text spectra
- Select and view multiple spectra in the manager and Matplotlib canvas
- Store raw data, processed datasets, parameters, and treatment history in `RamanSpectrum`
- Preview and apply processing to one spectrum, all spectra, or checked spectra
- Truncation and interactive preview
- Spike removal with Whitaker-Hayes detection and manual span bridging
- Linear calibration with manual and reference workflows
- Smoothing with Savitzky-Golay, moving-average, and Gaussian methods
- Baseline correction with ALS, SNIP, polynomial, constant, and custom baselines
- Normalization to 0-1, selected intensity regions, or a peak
- Peak detection and Gaussian, Lorentzian, and Voigt fitting previews
- JSON-backed defaults and last-used settings
- TXT, CSV, image, and processed-dataset export paths

## Requirements

- Python 3.10 or newer
- PySide6, NumPy, SciPy, Matplotlib, Pydantic, scikit-learn, and pandas
- pytest for development checks

Install dependencies into the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the application

```powershell
.\.venv\Scripts\python.exe main.py
```

On Windows, close the running application before changing settings if `config/last.json` is locked by another process.

## Project structure

```text
ECPypsi/
├── main.py                         Application entry point
├── gui/                            PySide6 windows, tabs, and widgets
│   ├── main_window.py              Main window and tab composition
│   ├── tabs/                       Data and treatment workflows
│   ├── widgets/                    Spectra manager and plotting widgets
│   └── dialogs/                    Settings and export dialogs
├── models/                         Application state and configuration
│   ├── spectrum.py                 RamanSpectrum data/history model
│   ├── config_manager.py           JSON defaults and last-used settings
│   └── singleton_*.py              Shared widget/model helpers
├── treatments/                     GUI-independent numerical algorithms
│   ├── truncation.py
│   ├── spike_removal.py
│   ├── calibration.py
│   ├── smoothing.py
│   ├── baseline.py
│   ├── normalization.py
│   └── peak_fitting.py
├── config/                         Defaults, last settings, and standards
├── data/raw/                       Input spectra and example files
├── data/processed/                 Generated or exported datasets
├── resources/icons/                Application icons
├── utils/                          File, plotting, math, and action helpers
├── tests/                          Automated tests and future fixtures
├── docs/                           Architecture and development notes
├── scripts/                        Maintenance and developer scripts
├── requirements.txt                Runtime/development dependencies
├── setup.py                        Package metadata and console entry point
└── README.md                       Project overview
```

See [docs/architecture.md](docs/architecture.md) for runtime data flow and [docs/development.md](docs/development.md) for development conventions.

## Processing flow

```text
Input file
  -> Data tab
  -> RamanSpectrum
  -> Spectra manager
  -> Selected spectrum
  -> Treatment preview
  -> Treatment function
  -> New dataset and history record
  -> Canvas and tree refresh
  -> Export
```

Treatment functions remain independent of PySide6. Tabs collect parameters and preview results; the manager applies results to `RamanSpectrum`; the canvas visualizes them.

## Configuration

- `config/default.json` contains resettable defaults.
- `config/last.json` contains the most recently used arguments.
- `config/calibration_standards.json` contains reference calibration standards.
- `config/peak_shapes.json` documents supported peak-shape equations.
- Custom baseline points and peak-fit settings are saved as JSON.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall gui models treatments utils
```

## Development status

Data import, spectra management, plotting, truncation, spike removal, calibration, smoothing, baseline, normalization, and peak fitting are active development areas. Component analysis, advanced processing, and some menu actions remain incomplete or experimental.
