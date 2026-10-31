# de493100 progress

- delay: `uv run python scripts/run_dl.py deletions de493100` stopped at `timeout 120` (exit 124). It cost 2 min and gave no report. The solver and witness file stayed as they were.
- delay: `uv run python scripts/run_dl.py store de493100` took 49 s, and the audit's store check took 47 s. The cost comes from `axis_pair`, which has more than 20000 rows on one input.
