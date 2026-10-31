# e45ef808

- delay: `uv run python scripts/run_dl.py store e45ef808` took 61 s and printed the full survey of witnessed cases, 14 grids, once for each of the four store points, about 900 lines that differ only in the name of the stored relation. Cost: about 20k tokens of output to read, and the rule for one long command then capped `store` at one more run. Still so.
- delay: the first `uv run python scripts/run_dl.py audit e45ef808` printed about 1300 lines. Most were group mismatches in the copied `witnesses.json`, whose groups name branch models and not the combination cases of the solver. Those mismatches go away once the Witness operation runs `record --all`, and the audit runs during Develop, which is before that. Cost: about 36k tokens of output. Still so.
