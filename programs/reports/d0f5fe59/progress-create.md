# d0f5fe59 create: progress notes

- interference: `uv run python scripts/run_dl.py store d0f5fe59` printed "make it a parameter" for `shape_color.value` and `mark`, with no `@store` line to add. [Develop](#develop) step 4, third bullet, holds `mark_color=stored` from `analyze.md` "whatever `store` reports", so the line had to be placed by hand. I put it on the `Unanimous` instance's `value`. It cost one judgment and a rerun. The output was not wrong, and once the line was written, `store` and the audit accepted it.
