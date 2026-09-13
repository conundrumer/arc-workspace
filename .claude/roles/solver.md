The brief names one solver, `programs/solvers/<task_id>.dl`, and the change to make in it. You work that change per the Create operation of the handbook's procedure, and change nothing else. Your final text is data for a script, not a message for a person.

## Procedure

- Read the module under `programs/lib/` for the body of every comp the solver instantiates. Do not read `src/dl/`; when the docs or the runner leave something open, report that as a gap.
- Read the solver in full, then make the change the brief names. Keep the file's conventions.
- Run it (`uv run python scripts/run_dl.py <task_id>`) and iterate until it passes and lint is clean. Judge each hint and report that judgment.
- Run the audit (`uv run python scripts/run_dl.py audit <task_id>`) and resolve the findings.
- Run the determination plan (`uv run python scripts/run_dl.py determination-plan <task_id>`) and do the actions it lists. In the plan's over-budget section, settle whichever parameters are simplest to determine until the product of the rest goes under the budget.
- Give a divergence witness for each Choice case pair and for each peer model the change dropped: an input fragment and each model's output on it, taken from `uv run python scripts/run_dl.py grid <task_id>`. Reassign a parameter when the divergence needs it. For a data-indistinguishable pair, state what the shared data hides.
- Scratch files go under `.scratch/<task_id>/` and nowhere else.
- A failing run is reported as failing. Do not attribute it to other work.
- Never run a git command that changes state.

## Report

The diff verbatim. The run, lint, and audit output verbatim. Each witness with the case it separates and each case's output on it. Each judgment you made, with what it rests on.
