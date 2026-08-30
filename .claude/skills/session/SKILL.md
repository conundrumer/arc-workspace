---
name: session
description: On user ask, bootstrap a solver session for arc-workspace.
argument-hint: [solver|triage|<task_id>]
---

First, read the output of `uv run python scripts/context.py` in full. It points back at each file for an entry or a body; read the file when the work is on the doc itself.

Then dispatch on `$ARGUMENTS`:

- `solver` — run `bash scripts/queue.sh` for the next queued solver and work it per the cadence.
- a task id — work that solver per the cadence.
- `triage` — rule on what the console's sessions called out, per the triage section below.
- anything else — an ordinary working request; proceed with the docs as context. A solver session is declared by keyword, never inferred from prose.

## Entry

- Read `programs/lib.dl` before writing or editing a solver, in full or as signatures. Read a primitive's body when its signature and comment leave the semantics open.
- If requested to continue from prior solver work, run `uv run python scripts/inspect-session.py --solver-only` and read the output in full.
- `bash scripts/queue.sh` prints the next solver and its estimated complexity.

## `next`

- User trigger to advance to the next solver. No advance without it.
- Clear all completed tasks before advancing.

## `commit`

- User trigger to commit. No commit without it. Make multiple commits when changes split cleanly. This includes pre-existing session work. Batch solvers appropriately.

## `triage`

- Read the console state (`curl -s localhost:8347/api/state`) and the backlog (`curl -s localhost:8347/api/backlog`). Both carry each item's parsed callout entries and badges — the callouts are the index. Open a report under `tools/console/state/reports/<task>/` only when an entry needs its context to rule on.
- Cluster the callouts by what they are about, and present the clusters as a numbered list: a count, one representative quote, and the tasks it covers.
- Write the user's rulings as flags, one call per task: `curl -sX POST localhost:8347/api/flag -d '{"id": "<task_id>", "level": 1}'`. Level 1 sorts first in the console's finalize lens; level 0 clears the flag. The flag is the whole ruling.
