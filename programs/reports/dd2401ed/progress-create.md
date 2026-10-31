# dd2401ed

- delay: `uv run python scripts/run_dl.py store dd2401ed` took 67 s on its second run, over 2592 cases on 7×15 grids. It cost about 1 min, and under Rules for one long command it allowed no third run, so the store points it printed then went unhandled.
- interference: `uv run python scripts/run_dl.py store dd2401ed` wrote a witness `near_color_at=stored` into the witness file, though the solver had no `@store` line for `near_color_at`. That witness named no case, and I removed it by hand. It cost one edit. The tool output was wrong, and that may still be so.
