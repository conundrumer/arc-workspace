# edb79dae

- interference: `uv run python scripts/run_dl.py edb79dae` lint, on the witness id `$KeySourceBySide` that `witnesses.json` gives: the lint requires a slug id, and [Witness file](docs/handbook/solver-file.md#witness-file) lets Analyze give a constructor name as an id. Cost: one rename and one extra pairs run. The output was a lint failure, and the rename to `mirrored-keys` fixed it.
