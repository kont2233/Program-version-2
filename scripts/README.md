# Scripts

Place maintenance, validation, and data-preparation scripts in this directory.

Scripts should:

- use the project virtual environment when invoking Python;
- avoid changing files under `data/raw/`;
- report failures with a non-zero exit code;
- keep generated output under `data/processed/` or a clearly named temporary directory.
