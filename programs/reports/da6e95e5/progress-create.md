# da6e95e5 progress

- interference: `uv run python scripts/run_dl.py record da6e95e5 inset=TileDim` with an id already in the witness file rewrote only that witness's `separates` text and kept its old input. To replace the input, the old witness had to be removed from the witness file by hand before the `record` call. Cost: one extra `record` run. The output is correct now.
- interference: [Simplify](#simplify) "Run `deletions` once, after the last solver edit before the report." The `deletions` findings led to a solver edit, so `deletions` ran a second time. Cost: one extra run of about 6 s.
