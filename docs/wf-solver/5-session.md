# Session

A solver session writes a Souffle solver (`programs/solvers/<task_id>.dl`) modeling an ARC task. Reference: the TS solver (`../arc-synth-bun/programs/solvers/`). When a Python solver exists for the task (`programs/solvers/<task_id>.py`), it's also reference.

## Entry

- If requested to continue from prior solver work, run `uv run python scripts/inspect-session.py --solver-only` and read the output in full.
- `bash scripts/queue.sh` prints the next solver.

## Cadence

- Analyze the task.
- Draft from the reference.
- Run against materialized train+test pairs (`uv run python programs/run_dl.py <task_id>`).
- Iterate until the impl works
- Run `/revise` on the solver file.
- Propose alternative modeling forms.
- Iterate with the user.

## `next`

- User trigger to advance to the next solver. No advance without it.

## `commit`

- User trigger to commit. No commit without it. Make multiple commits when changes split cleanly.

## Python as fallback

Python is available as a fallback in special circumstances (`programs/solvers/<task_id>.py`, run via `programs/run.py`).

## Lib addition protocol

A new primitive earns its place in `programs/lib.dl` by working in a real task first, not by looking general. The order:

1. **Task-local.** Write the primitive in the solver's Consts or body. Run it; confirm it works in context.
2. **Propose.** Surface it to the user — name it, describe the operation, show the solver-local version.
3. **Lib (on approval).** Move to `programs/lib.dl`. Update callers.
