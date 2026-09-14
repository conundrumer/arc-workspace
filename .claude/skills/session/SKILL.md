---
name: session
description: On user ask, bootstrap a solver session for arc-workspace.
argument-hint: [solver|retro|<task_id>]
---

First, when the handbook is not in your system prompt, read the output of `uv run python scripts/context.py` in full. It points back at each file for an entry or a body; read the file when the work is on the doc itself.

Then dispatch on `$ARGUMENTS`:

- `solver` — run `bash scripts/queue.sh` for the next queued solver and work it per the procedure.
- a task id — work that solver per the procedure.
- `retro` — rule on what the console's sessions called out beyond their own tasks, per the retro section below.
- anything else — an ordinary working request; proceed with the docs as context. A solver session is declared by keyword, never inferred from prose.

## Entry

`uv run python scripts/context.py --write` writes the agents; `scripts/claude.py` does that before it starts `claude`. `claude` registers the agent files at its start only, so a session cannot write them for itself. When one is missing, say so before any spawn.

- Read the lib before writing or editing a solver, as the handbook renders it. When a primitive's interface leaves the semantics open, read its body in the module.
- If requested to continue from prior solver work, run `uv run python scripts/inspect-session.py --solver-only` and read the output in full.
- `bash scripts/queue.sh` prints the next solver and its estimated complexity.

## `next`

- User trigger to advance to the next solver. No advance without it.
- Clear all completed tasks before advancing.

## `retro`

Rule on what the console's sessions called out beyond their own tasks. The workflow reads, checks, fixes, and verifies. The main session passes the roles, presents the result, and takes the rulings.

- **Run.**
    - Run the `retro` workflow (`.claude/workflows/retro.js`) with `roles` in `args`: the text of each role file the run needs, keyed by role name, as the workflow's `args` note names them. A retro takes three runs, each with its own `args`.
    - The first run is `dry: true`. It reads, checks, and reviews, and returns every call with its default and the fixes it would make, under `dry`. It makes no fix, and the sweep does not run in it.
    - The main session reads the role files to pass them, and no window, report, solver, or doc. It runs no edit or check itself: those go to agents.
    - The runs' agents read the window, check each issue, take a default on each open one, make the fixes the rulings keep, sweep the window's solvers, act on each review line those fixes and the sweep wrote into a solver, run the cleanup pass over each solver the runs wrote, and verify what they changed. Each stage's rules live in its role, under `.claude/roles/`. The `solver` role carries a solver fix and the resolve stage.
- **Report.** The dry run returns every call with its default, its level, and what argues for and against it.
    - What reaches the user is a call whose fix changes a rule the user reads, in `principles.md`, `keywords.md`, or a gloss, and the Verify issues. A solver particular stays with the agents and the console's reports.
    - Present the calls, as one numbered list, ordered by dependency and then by level ascending. Issue ids stay out, and so do quotes.
    - A call is a decision in the settle form:

        ```
        ### <n>. [<level>] <what is wrong in the shared thing, as a question>? <the default>.

        - **Context:**
            - <what the thing is and does, for a reader who does not have the doc in their head>
            - <its current text or state>
            - **Impact:** <how the raising sessions were affected>
                - <the evidence, from the check's `changed_how` and the review's `reason`>
            - **Tasks:** <the task ids>
        - **Options:**
            1. **<label>.** <the default's action>
                - **For:** <a reason>
                    - <the reason's ground>
                - **Against:** <a reason>
                    - <its evidence, or `Given <condition>. <likelihood>.`>
            2. **<label>.** <the option's action>
        ```

        - The level is the call's discretion level, as the check and review roles define it. A level-4 fix, and a fix to `principles.md` at any level, is presented for ruling like every other call.
        - The default states what holds, the fix or the drop.
        - The default is option 1, and the other options come strongest first, each labeled in one word. Reasons come strongest first.
        - The first ground under the default is the call's `basis`. A call the check dropped takes it from the check result, and every other call from the review result. A call with no `basis` states no ground for it.
        - A concern is an Against reason with its evidence, or with the likelihood and what it takes for it to be real. Churn, reversals of earlier commits, and file growth are not concerns.
        - For a doc rule, the default's action states the meaning before and the meaning after.
        - A follow-up fix from the workflow's `followups` is a further line under the default's action, naming the file and the change.
    - Some calls carry more.
        - A call whose fix edits `docs/wf-solver/principles.md`: Context quotes the text before and after, and shows the concrete cases with small grid fragments. The options are the readings the workflow returned, each with its wording and its consequence over the approved solvers.
        - A call whose fix carries an illustration shows it under the call: for each cited task, the case sets under each reading and a witness input where the readings differ.
        - A keyword addition or a gloss change is level 4, presented as a proposal for a separate session.
        - A citation of a draft solver is not presented. It waits in the doc in the pending form, with a `// review cite:` line in the solver, and approval places it.
    - The workflow's Verify issues end the presentation: a failing check, a finding no round acted on, and an edit outside the run's targets, such as an approved solver. Do not report non-issues. A failing check blocks the close.
- **Rulings.**
    - The user rules per call, by index: accept the default, pick another option, or reject a reason. A call the user does not rule on takes its default. A question is answered from the call's record before any action.
    - Follow-up work batches into one agent run after the rulings settle. Each follow-up item carries one of two labels. **Queued**: it goes into the batch with nothing more from the user. **Needs ruling**: it waits on the user.
    - The rulings for fixes go into a second run with `roles` again and the fixes as `fixes` in `args`: the fixes as the dry run returned them under `dry`, each with its call id, kind, target, edit, and task ids, filtered to those the rulings keep, plus any fix a ruling for another option calls for. The second run's prune pass keeps their substance, revises the wording to the file's style, and reports that the meaning held.
    - The sweep goes into a third run after the fixes run, with `roles` again, `resolve` in `args` as an empty list, and `sweep` holding the window's task ids. That run sweeps those solvers, marks the drafts a parameter stays open in, and resolves, compares, and cleans up those drafts. It reports its Verify issues.
    - A lib change that keeps interface and meaning is a mechanical fix and goes to an agent directly.
- **Close.**
    - Run `uv run python tools/console/retro.py mark` to move the mark.
    - Commit all changes made in the retro session, leaving alone the changes under `programs/solvers/` this session did not make.
