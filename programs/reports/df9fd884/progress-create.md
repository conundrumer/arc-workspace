# df9fd884 progress

- interference, `uv run python scripts/run_dl.py store df9fd884`: the report printed `mouth_line[a]: no witness: ... at the case values the cases that take its @store branch hold`, but `mouth_line` has no `@store` line. Reading it cost about half a minute. The line is still in the output. It changed nothing in the solver.
- interference, `uv run python scripts/run_dl.py audit df9fd884` (first run): the case names it printed for the `two-objects` group mismatch (`$StopAtObstacle & $EachObject`) denoted a case that also takes `trip=stored`. Because of that, it looked like a Gravity fault. Checking `heading` and `fall.travel` with `relation` cost about two minutes. `record --all` cleared the mismatch. The solver was not wrong.
