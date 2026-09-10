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

`triage` and `retro` need a running console at `localhost:8347`. Without one, stop and say so.

A role is spawned as the `handbook` agent, `.claude/agents/handbook.md`. `uv run python scripts/context.py --write` writes it from the docs, and `scripts/claude.py` does that before it starts `claude`. `claude` registers the file at its start only, so a session cannot write it for itself. When the file is missing, say so before any spawn.

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

- Run the `retro` workflow (`.claude/workflows/retro.js`) with `roles` in `args`: the text of each role file the run needs, keyed by role name, as the workflow's header lists them. Its agents read the window, check each issue, take a default on each open one, make the fixes the defaults call for, tier 4 excepted, and verify what those fixes changed. Each stage's rules live in its role, under `.claude/roles/`. The main session reads the role files to pass them, and no window, report, solver, or doc, and runs no edit, revert, or check itself: those go to agents.
- The workflow returns every call with its default, its tier, and what argues for and against it. Present the tally, the closed issues, the files the fixes changed, and the entries written. Then present the calls as a numbered list of the four tiers, each tier a numbered sub-list of its calls, so the user can name a call by its index (2.3). Each call carries its task ids. Issue ids stay out, and so do quotes.

    ```
    1. **No judgment needed.**
       1. **Fixed: <the issue, a few words>.** `<task id>` `<task id>`
          - What the sessions hit.
          - What the thing is, in one sentence, for a reader who does not have the doc in their head.
          - What the default did.
          - What stands against it, when something does.
       2. **Dropped: <the issue>.** `<task id>`
          - ...
    2. **Straightforward.**
       1. ...
    3. **Defensible.**
       1. ...
    4. **Insufficient basis.**
       1. ...
    ```

- A call whose fix carries an illustration shows it under the call: for each cited task, the case sets under each reading and a witness input where the readings differ.
- The workflow's Verify results come after the calls: each finding with the fix it got, and each check with its summary. A failing check blocks the close.
- The presentation ends with the borderline drops as one list, each a task id and a few words, so the user can pull one back.
- The user answers per item. A question is answered from the call's record before any action. A veto on a made fix reverses it, and a ruling for a dropped or tier-4 fix makes it. Follow-up rulings batch into one agent run after they settle.
- Every follow-up item carries one of two labels. **Queued**: it goes into the batch with nothing more from the user. **Needs ruling**: it waits on the user.
- Reversal: an agent runs `git apply -R` on the file's diffs, the later first. Every fix in that file comes out with it, and the kept hunks return with `git apply --include` on the same patch. The rulings for fixes go into a second run with `roles` again and the fixes as `fixes` in `args`: one entry per file a fix edits, each with its kind, target, and edit, under the call's id, as the first run returned them under each call's `fixes`. The second run's prune pass keeps their substance, revises the wording to the file's style, and reports that the meaning held.
- A lib change that keeps interface and meaning is a mechanical fix and goes to an agent directly.
- A reason the user says should never count again, or a stance the user states, goes into the role that raised it, as a line.
- Close: Run `curl -sX POST localhost:8347/api/retro` to move the mark. Commit all changes made in the retro session, leaving alone the changes under `programs/solvers/` this session did not make.
