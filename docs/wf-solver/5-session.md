# Session

A solver session writes a Souffle solver (`programs/solvers/<task_id>.dl`) modeling an ARC task. Reference: the TS solver (`../arc-synth-bun/programs/solvers/`). When a Python solver exists for the task (`programs/solvers/<task_id>.py`), it's also reference.

## Entry

- Read `programs/lib.dl` — self-explanatory.
- If requested to continue from prior solver work, run `uv run python scripts/inspect-session.py --solver-only` and read the output in full.
- `bash scripts/queue.sh` prints the next solver.

## Cadence

- Analyze the task.
- Draft from the reference.
- Run against materialized train+test pairs (`uv run python programs/run_dl.py <task_id>`).
- Once the primary impl works, propose alternative modeling forms.
- Iterate with the user.

## `next`

- User trigger to advance to the next solver. No advance without it.

## `commit`

- User trigger to commit. No commit without it. Make multiple commits when changes split cleanly.

## Python as fallback

Python is available as a fallback in special circumstances (`programs/solvers/<task_id>.py`, run via `programs/run.py`).
