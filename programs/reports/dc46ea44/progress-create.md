# dc46ea44 create: progress notes

- delay: `uv run python scripts/run_dl.py sweep dc46ea44` stopped at its 120 s timeout (exit 124) with no output. It cost 2 min of the Determine budget, and the pass has no sweep result.
- delay: `uv run python scripts/run_dl.py store dc46ea44` took 43 s on its first run (8 s on the second). The cost was under 1 min.
- interference: `uv run python scripts/run_dl.py audit dc46ea44` rejected a `@store` line on the derived relation `divider`, because the parameter `divider` has the same name, and the relabeling run then failed ("`divider` is not one value on every input ... it differs on train 1"). The store line was taken out and marked `@workaround`, which cost about 1 min. The divider's stored branch is still not formed.
