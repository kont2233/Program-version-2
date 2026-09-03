# Development Guide

## Environment

Use the project virtual environment on Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall gui models treatments utils
```

For headless Qt checks, set `QT_QPA_PLATFORM=offscreen` before starting Python.

## Conventions

- Keep treatment algorithms independent of Qt.
- Preserve the two-column `(Raman shift, intensity)` array contract.
- Return treatment metadata that can be stored by `RamanSpectrum.add_step`.
- Store resettable parameters in `config/default.json`.
- Let `ConfigManager` persist last-used values to `config/last.json`.
- Add focused tests under `tests/` and deterministic sample data under `tests/fixtures/`.
- Avoid modifying files under `data/raw/` during development.
