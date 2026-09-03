# Architecture

## Layers

- `gui/` contains PySide6 windows, tabs, dialogs, the spectra manager, and plotting widgets.
- `models/` contains `RamanSpectrum`, which owns raw data, processed datasets, and treatment history.
- `treatments/` contains numerical functions that do not depend on PySide6.
- `config/` contains defaults, last-used values, calibration standards, and shape definitions.
- `data/` contains input and generated spectra.

## Runtime flow

```text
main.py
  -> MainWindow
  -> DataTab imports RamanSpectrum
  -> SpectraManagerWidget registers and selects spectra
  -> Treatment tab previews through a canvas
  -> treatment function returns processed data and metadata
  -> RamanSpectrum.add_step stores the result
  -> manager refreshes tree and canvas
```

The spectra manager is the coordination point for applying a treatment to the current spectrum, all spectra, or checked spectra. The model is the source of truth for data and history; canvases should remain presentation components.
