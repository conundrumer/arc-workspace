# Session

A solver session ports TS reference solvers (`../arc-synth-bun/programs/solvers/`) to Python (`programs/solvers/<task_id>.py`).

## Entry

- `bash scripts/queue.sh` prints the next solver to port.

## Cadence

- Draft from the TS reference.
- Run against materialized train+test pairs (`uv run python programs/run.py <task_id>`).
- Revise based on user review until settled.

## next

- User trigger to advance to the next solver. No advance without it.
