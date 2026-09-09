---
name: session
description: On user ask, bootstrap a solver session for arc-workspace.
argument-hint: [solver|triage|retro|<task_id>]
---

First, when the handbook is not in your system prompt, read the output of `uv run python scripts/context.py` in full. It points back at each file for an entry or a body; read the file when the work is on the doc itself.

Then dispatch on `$ARGUMENTS`:

- `solver` — run `bash scripts/queue.sh` for the next queued solver and work it per the procedure.
- a task id — work that solver per the procedure.
- `triage` — rule on what the console's sessions called out about their tasks, per the triage section below.
- `retro` — rule on what the console's sessions called out beyond their own tasks, per the retro section below.
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

## `retro`

- Run the `retro` workflow (`.claude/workflows/retro.js`) with no `args`. Its agents, the `retro-*` definitions under `.claude/agents/`, read the window, check each issue, take a default on each open one, and make the fixes the defaults call for. Each definition carries its stage's rules. The main session reads no window, report, or doc.
- The workflow returns every call: the issue, its default (the outcome that holds unless the user rules otherwise), and what argues for and against it. Present the tally, the closed issues, the files the fixes changed, and the proposals entries written, then the calls clustered by the reason they turn on, as a numbered list: a count, one representative for and against, the ids it covers. No quote reaches the user.
- The user strikes a reason they do not accept. Remove it from every call. A call with one side left is unopposed: nothing against, and its default holds; nothing for, and its default reverses. A call with both sides left is contested. Present the contested calls clustered the same way, and repeat until the user reads them whole: each with its default, its for, and its against.
- Rulings. A made fix that reverses comes out with `git apply -R` on its diffs, the later diff first. One agent made every fix in a file as one diff, so the other fixes in that file come out with it and go into the second run. A drop that reverses, or a ruling for a fix, goes into a second run with the fixes as `fixes` in `args`, each with its id, kind, target, and edit as the first run returned them.
- A reason the user says should never count again goes into the agent definition that raised it, as a line.
- Close: `curl -sX POST localhost:8347/api/retro` moves the mark.
