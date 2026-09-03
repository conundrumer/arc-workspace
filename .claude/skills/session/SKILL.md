---
name: session
description: On user ask, bootstrap a solver session for arc-workspace.
argument-hint: [solver|triage|debrief|<task_id>]
---

First, read the output of `uv run python scripts/context.py` in full. It points back at each file for an entry or a body; read the file when the work is on the doc itself.

Then dispatch on `$ARGUMENTS`:

- `solver` — run `bash scripts/queue.sh` for the next queued solver and work it per the cadence.
- a task id — work that solver per the cadence.
- `triage` — rule on what the console's sessions called out about their tasks, per the triage section below.
- `debrief` — rule on what the console's sessions called out beyond their own tasks, per the debrief section below.
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

## `debrief`

- Send an agent to read the window (`curl -s localhost:8347/api/debrief`): the tasks landed since the last debrief, each with its callouts. It keeps the callouts that reach beyond the task's own solver and the Lib addition protocol, clusters them by what they are about, and returns one entry per cluster: a count, the gap in one plain sentence, the tasks, and one quote.
- Send an agent per cluster to check whether a later change has closed it. It opens a report under `tools/console/state/reports/<task>/` when an entry needs its context, reads a doc as a session does (`uv run python scripts/context.py`), and reproduces a perf claim. It says whether the gap changed what a session did or was only noted. When the cluster is open, it returns the smallest edit that closes the gap, or the ways forward with the for and against of each. A gap the lib or the runner can close is closed there, and not in what a session reads. An argument from what earlier solvers did is weak, weakest for the earliest. An edit that serves one task's case overfits; it returns none.
- Present the open clusters as a numbered list: the count, the gap, the tasks, whether it changed a session's work, and the edit or the ways forward, each in plain words. A cluster with one clear fix gets that fix made by an agent, and a second pass by kind: a solver gets the `cleanup` agent, a lib change gets its comments pruned, a doc addition gets pruned. A doc addition that answers text the doc already holds replaces that text. A cluster with more than one way forward gets the user's ruling, and then the fix and its second pass.
- When the debrief is done, `curl -sX POST localhost:8347/api/debrief` moves the timestamp.
