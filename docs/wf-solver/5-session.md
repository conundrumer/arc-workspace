# Session

A solver session writes a Souffle solver (`programs/solvers/<task_id>.dl`) modeling an ARC task. Reference: the TS solver (`../arc-synth-bun/programs/solvers/`).

## Entry

- Read `programs/lib.dl` in full before writing or editing a solver.
- If requested to continue from prior solver work, run `uv run python scripts/inspect-session.py --solver-only` and read the output in full.
- `bash scripts/queue.sh` prints the next solver and its line count.

## Cadence

You must do each step individually. Never batch them together.

0. Create a task for each of the following steps. The task list should have 5 items.
1. Create the solver
    - Analyze the task: `cat data/tasks/<task_id>.json` (already formatted, don't pipe into anything)
    - Draft from the reference
    - Run against materialized train+test pairs (`uv run python programs/run_dl.py <task_id>`)
    - Iterate until it works
2. Simplify the impl if possible
3. Prune everything that doesn't serve the reader: a future session who needs to understand the solver and its model claim
    - You must exhaustively prune as much as you can, from unnecessary words to irrelevant ideas
4. Review:
    - Does it follow principles?
    - Is there anything awkward or roundabout, like code that reads as pure implementation details with no conceptual meaning, or reimplementing something existing?
    - Any potential alt models? Do not propose alt impls.

When the user says `cleanup`, create tasks for Simplify and Prune and do them.

If `/revise` is used, the audience and purpose is: "A future session who needs to understand the solver and its model claim".

## `next`

- User trigger to advance to the next solver. No advance without it.
- Clear all completed tasks before advancing

## `commit`

- User trigger to commit. No commit without it. Make multiple commits when changes split cleanly.

## Lib addition protocol

A new primitive earns its place in `programs/lib.dl` through real use, not by looking general. The order:

1. Write the primitive in the solver's Consts or body. Run it. Confirm it works in context.
2. Surface it to the user — name it, describe the operation, show the solver-local version.
3. On agreement, write the addition proposal to the proposals doc.
4. On approval, move to `programs/lib.dl`. Update callers.
