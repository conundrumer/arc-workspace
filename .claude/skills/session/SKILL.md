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

- Run the `retro` workflow (`.claude/workflows/retro.js`) with `roles` in `args`: the text of each role file the run needs, keyed by role name, as the workflow's `args` note names them. Its agents read the window, check each issue, take a default on each open one, make the fixes the defaults call for, tier 4 excepted, act on each review line those fixes and the sweep wrote into a solver, run the cleanup pass over each solver the run wrote, and verify what the run changed. The `solver` role carries a solver fix and the resolve stage. A `resolve` run, `resolve` in `args` holding a list of task ids, runs the resolve stage over those solvers. Each stage's rules live in its role, under `.claude/roles/`. The main session reads the role files to pass them, and no window, report, solver, or doc, and runs no edit, revert, or check itself: those go to agents.
- The workflow returns every call with its default, its tier, and what argues for and against it. Present the tally, the closed issues, the files the fixes changed, and the entries written. Then present the calls as a numbered list of the tiers, each tier item starting with its name in bold — **No judgment needed**, **Straightforward**, **Defensible**, **Insufficient basis** — and holding a numbered list of its calls, so the user can name a call by its index (2.3). Issue ids stay out, and so do quotes.
- A call's heading is a verdict word — Fixed, Dropped, or Deferred — then the issue, stated as what is wrong in the shared thing. These sub-bullets come under it, in this order.
    - **Context:** what the thing is and does, for a reader who does not have the doc in their head.
    - **Impact:** a phrase for how the raising sessions were affected, then its evidence from the check result's `changed_how` and the review's `reason`.
    - **Resolution:** the change. For a doc rule, state the meaning before and the meaning after. A dropped or deferred call takes **Proposal:** instead.
        - **Basis:** the principle, norm, or fact the call rests on, from the call's `basis`. A call the check dropped takes that basis from the check result, and every other call from the review result. A call that carries no `basis` takes no Basis sub-bullet.
    - **Concerns:** one sub-bullet per independent concern, each with its evidence, or with the likelihood and what it takes for it to be real. Churn, reversals of earlier commits, and file growth are not concerns.
    - **Tasks:** the task ids.
- The resolve stage's items take the same form as a call. A review line the stage left unfinished is a Deferred call: what is wrong, why the stage left it, and what it needs. A judgment call a resolve report raises takes the tier its basis puts it in, and its **Proposal:** is the ruling it needs. A line the stage finished is not presented; the solver's report in the console carries it.
- An unprincipled divergence the consistency stage reports is presented as a call: the point the solvers share, the rule they read differently, the reading the docs should force, and the form they should agree on. When its fix is a wording change in `docs/wf-solver/principles.md`, it takes the standalone discussion form this section gives for a fix to that file.
- A call whose fix carries an illustration shows it under the call: for each cited task, the case sets under each reading and a witness input where the readings differ.
- A grid in the presentation is drawn as a grid: one row per line, cells separated by spaces, background as `.`.
- A call whose fix edits `docs/wf-solver/principles.md` is presented as a standalone discussion: the text before and after, quoted; the concrete cases, with small grid fragments; and the options the workflow returned — keep, amend in place, leave — each with its consequence over the approved solvers, then a recommendation. The user's answer picks one option. The **Basis:**, **Impact:**, and **Concerns:** sub-bullets come under it, as they do under a call.
- A keyword addition or a gloss change is tier 4, and is presented as a proposal for a separate session.
- The workflow's Verify results come after the calls, and hold a failing check, a finding no round acted on, and an edit outside the run's targets, such as an approved solver. A failing check blocks the close. The presentation ends with these items.
- A follow-up fix from the workflow's `followups` is presented under the call whose verify raised it, as a further Resolution line that names the file and the change.
- The user answers per item. A question is answered from the call's record before any action. A veto on a made fix reverses it, and a ruling for a dropped or tier-4 fix makes it. Follow-up rulings batch into one agent run after they settle.
- Every follow-up item carries one of two labels. **Queued**: it goes into the batch with nothing more from the user. **Needs ruling**: it waits on the user.
- Reversal: an agent runs `git apply -R` on the file's diffs, the later first. Every fix in that file comes out with it, and the kept hunks return with `git apply --include` on the same patch. The rulings for fixes go into a second run with `roles` again and the fixes as `fixes` in `args`: one entry per file a fix edits, each with its kind, target, and edit, under the call's id, as the first run returned them under each call's `fixes`. The second run's prune pass keeps their substance, revises the wording to the file's style, and reports that the meaning held.
- A lib change that keeps interface and meaning is a mechanical fix and goes to an agent directly.
- A citation of a draft solver waits in the doc in the pending form, with a `// review cite:` line in the solver, and approval places it. It is not presented.
- A reason the user says should never count again, or a stance the user states, goes into the role that raised it, as a line.
- Close: Run `uv run python tools/console/retro.py mark` to move the mark. Commit all changes made in the retro session, leaving alone the changes under `programs/solvers/` this session did not make.
