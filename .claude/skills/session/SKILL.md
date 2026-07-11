---
name: session
description: Bootstrap a solver session for arc-workspace.
argument-hint: [solver|<task_id>]
disable-model-invocation: true
---

Read all docs in `docs/wf-solver/`.

Then dispatch on `$ARGUMENTS`:

- `solver` — run `bash scripts/queue.sh` for the next queued solver and work it per the cadence below.
- a task id — work that solver per the cadence below.
- anything else — an ordinary working request; proceed with the docs as context. A solver session is declared by keyword, never inferred from prose.

# Solver session

A solver session writes a Souffle solver (`programs/solvers/<task_id>.dl`) that models an ARC task. Reference: the TS solver (`../arc-synth-bun/programs/solvers/`).

## Entry

- Read `programs/lib.dl` in full before writing or editing a solver.
- If requested to continue from prior solver work, run `uv run python scripts/inspect-session.py --solver-only` and read the output in full.
- `bash scripts/queue.sh` prints the next solver and its estimated complexity.

## Cadence

Do each step individually; never batch them. Create a task per step.

1. Create the solver
    - Analyze the task: `cat data/tasks/<task_id>.json` (already formatted, do not pipe into anything)
    - Draft from the reference
    - Run against materialized train+test pairs (`uv run python programs/run_dl.py <task_id>`)
    - Iterate until it works
2. Simplify if possible
3. Prune everything that does not serve the reader — exhaustively, from unnecessary words to irrelevant ideas. Judge necessity from the artifact alone, not from the session.
    - Text copied from prior solvers may not have been pruned; prune it like new text
4. Review:
    - The review is for the user to act on: keep or add cases, fix awkward code, promote primitives. Include only items the user can act on. An item included only as context still makes the user verify it against the rules, which is the work the review should do for them.
    - Does it follow principles?
    - Is there anything awkward or roundabout, like code that reads as pure implementation details with no conceptual meaning, or code that reimplements something existing?
    - Any potential alt models? Alt impls are not models — do not propose them, and do not list them in the review.
    - For each Choice case pair, and for each alt model considered and dropped: show where the models diverge, as a concrete input fragment and each model's output on it. The fragment must witness a valid divergence: the diverging model's output on it is well-formed. For data-indistinguishable pairs, state what the shared data hides. A model the data rules out was never a candidate: it does not appear in the review, not even as a note on why it is absent.
    - The review is a reply to the user, and it ends the turn: finish all task updates first, then write it with no tool calls after it.

For prune and `revise`, the reader and purpose: a future session who needs to understand the solver and its model claim.

When the user says `cleanup`, create tasks for Simplify and Prune and do them.

## `next`

- User trigger to advance to the next solver. No advance without it.
- Clear all completed tasks before advancing.

## `commit`

- User trigger to commit. No commit without it. Make multiple commits when changes split cleanly. This includes pre-existing session work. Batch solvers appropriately.

## Lib addition protocol

A new primitive qualifies for `programs/lib.dl` through real use, not by looking general. The order:

1. Write the primitive in the solver's Consts or body. Run it. Confirm it works in context.
2. Surface it to the user: name it, describe the operation, show the solver-local version.
3. On agreement, stage it: wrap the solver-local version in a task-local `.comp` named for the primitive, and write the addition proposal to `docs/wf-solver/proposals.md`. `stage` refers to this step and always includes the comp form.
4. On approval, move to `programs/lib.dl`. Update callers.

Reuse of a staged proposal is promotion evidence. When a solver copies a primitive that already has a `proposals.md` entry, surface the reuse directly: name the proposal and the new home, ask whether it moves to lib, and record the home in the entry (the `Second home (protocol step 1)` convention).
