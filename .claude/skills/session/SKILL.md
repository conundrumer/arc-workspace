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

## `triage`

- Read the console state (`curl -s localhost:8347/api/state`) and the backlog (`curl -s localhost:8347/api/backlog`). Both carry each item's parsed callout entries and badges — the callouts are the index. Open a report under `tools/console/state/reports/<task>/` only when an entry needs its context to rule on.
- Cluster the callouts by what they are about, and present the clusters as a numbered list: a count, one representative quote, and the tasks it covers.
- Write the user's rulings as flags, one call per task: `curl -sX POST localhost:8347/api/flag -d '{"id": "<task_id>", "level": 1}'`. Level 1 sorts first in the console's finalize lens; level 0 clears the flag. The flag is the whole ruling.

## `retro`

- Run the `retro` workflow (`.claude/workflows/retro.js`) with no `args`. Its agents, the `retro-*` definitions under `.claude/agents/`, read the window, check each issue, take a default on each open one, and make the fixes the defaults call for, tier 4 excepted. Each definition carries its stage's rules. The main session reads no window, report, solver, or doc, and runs no edit, revert, or check itself: those go to agents.
- The workflow returns every call with its default, its tier, and what argues for and against it. Present the tally, the closed issues, the files the fixes changed, and the entries written. Then present the calls as a numbered list of the four tiers, each tier a numbered sub-list of its calls, so the user can name a call by its index (2.3). No ids and no quotes.

    ```
    1. **No judgment needed.**
       1. **Fixed: <the issue, a few words>.** What was wrong, in plain terms. What the fix did. What stands against it, when something does.
       2. **Dropped: <the issue>.** What was raised. Why nothing changed.
    2. **Straightforward.**
       1. ...
    3. **Defensible.**
       1. ...
    4. **Insufficient basis.**
       1. ...
    ```

- The user answers per item. A question is answered from the call's record before any action. A veto on a made fix reverses it, and a ruling for a dropped or tier-4 fix makes it. Follow-up rulings batch into one agent run after they settle.
- Reversal: an agent runs `git apply -R` on the file's diffs, the later first. Every fix in that file comes out with it, and the kept hunks return with `git apply --include` on the same patch. The rulings for fixes go into a second run with the fixes as `fixes` in `args`, each with its id, kind, target, and edit as the first run returned them. The second run's prune pass keeps their substance, revises the wording to the file's style, and reports that the meaning held.
- A lib change that keeps interface and meaning is a mechanical fix and goes to an agent directly.
- A reason the user says should never count again, or a stance the user states, goes into the agent definition that raised it, as a line.
- Close: `curl -sX POST localhost:8347/api/retro` moves the mark.
