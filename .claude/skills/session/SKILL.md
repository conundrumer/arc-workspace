---
name: session
description: On user ask, bootstrap a solver session for arc-workspace.
argument-hint: [solver|triage|<task_id>]
---

<!-- batch:skip -->
Read the docs in `docs/wf-solver/` in this order: principles, style, patterns, concepts, shapes, proposals. For plain solver work, read the full output of `uv run python scripts/context.py` instead — those docs and `programs/lib.dl` in the same order and in a shorter form, with `patterns.md` and `proposals.md` as one line per entry and `lib.dl` as signatures. It points back at each file for an entry or a body.

Then dispatch on `$ARGUMENTS`:

- `solver` — run `bash scripts/queue.sh` for the next queued solver and work it per the cadence below.
- a task id — work that solver per the cadence below.
- `triage` — rule on what the console's sessions called out, per the triage section below.
- anything else — an ordinary working request; proceed with the docs as context. A solver session is declared by keyword, never inferred from prose.
<!-- /batch:skip -->

# Solver session

A solver session writes a Souffle solver (`programs/solvers/<task_id>.dl`) that models an ARC task.

<!-- batch:skip -->
## Entry

- Read `programs/lib.dl` before writing or editing a solver, in full or as signatures. Read a primitive's body when its signature and comment leave the semantics open.
- If requested to continue from prior solver work, run `uv run python scripts/inspect-session.py --solver-only` and read the output in full.
- `bash scripts/queue.sh` prints the next solver and its estimated complexity.
<!-- /batch:skip -->

## Cadence

For each pass: Do each step individually. Do not batch them. Create a task per step.

Creation pass, do this first:

1. Create the solver
    1. Analyze the task and the reference TS solver. When they are not in the message, read them: `cat data/tasks/<task_id>.json ../arc-synth-bun/programs/solvers/<task_id>.ts`
        - The task is already formatted, do not pipe into anything.
        - The reference TS solver solves the task but might not encode the best model.
    2. Draft the solver. Do not write the `Fit` comp yet.
    3. Run against materialized train+test pairs (`uv run python scripts/run_dl.py <task_id>`)
    4. Iterate until it works and passes lint.
    5. Run the audit (`run_dl.py audit <task_id>`) and resolve the findings. Raise judgment calls in the review.
2. Simplify if possible
3. Prune everything that does not serve the reader — exhaustively, from unnecessary words to irrelevant ideas. Judge necessity from the artifact alone, not from the session.
    - Text copied from prior solvers may not have been pruned; prune it like new text
4. Run `fit-plan` and report the verdict (bold it) on if there needs to be a fit pass.
5. Review:
    - The review is for the user to act on: keep or add cases, fix awkward code, promote primitives. Include only items the user can act on. An item included only as context still makes the user verify it against the rules, which is the work the review should do for them.
    - Does it follow principles? The review does not rest on lint or passing pairs.
    - Is there anything awkward or roundabout, like code that reads as pure implementation details with no conceptual meaning, or code that reimplements something existing, or repetitive code that might have a more principled form?
    - Any potential alt models? Alt impls are not models — do not propose them, and do not list them in the review.
    - For each Choice case pair, and for each alt model considered and dropped: show where the models diverge, as a concrete witness — an input fragment, refilling a Consts slot when the divergence needs one — and each model's output on it, taken from `uv run python scripts/run_dl.py grid <task_id>`. The witness must show a valid divergence: the diverging model's output on it is well-formed. For data-indistinguishable pairs, state what the shared data hides. A model the data rules out was never a candidate: it does not appear in the review, not even as a note on why it is absent.
    - The review is a reply to the user, and it ends the turn: finish all task updates first, then write it with no tool calls after it.

Fit pass, triggered when the user says `fit`:

1. Run `fit-plan`. If there are no actions to take, you are done.
2. Do the fit-plan actions.
3. Simplify
4. Prune
5. Review as before as applicable, keeping in mind "The review is for the user to act on", with these additions:
    - Given you could modify the model (i.e. changing consts shape), is there any simpler or more principled alternative?

For `prune` and `revise`, the reader and purpose: a future session who needs to understand the solver and its model claim.

When the user says `cleanup`, create tasks for Simplify and Prune and do them.

Do not read `src/dl/` during the cadence. The docs and the run output should have all the information you need. You should not need to anticipate or confirm anything by reading the source. If you choose to read the source, report to the user why, as that indicates there is a gap or error in the docs or runner.

<!-- batch:skip -->
## `next`

- User trigger to advance to the next solver. No advance without it.
- Clear all completed tasks before advancing.

## `commit`

- User trigger to commit. No commit without it. Make multiple commits when changes split cleanly. This includes pre-existing session work. Batch solvers appropriately.

## `triage`

- Read the console state (`curl -s localhost:8347/api/state`) and the backlog (`curl -s localhost:8347/api/backlog`). Both carry each item's parsed callout entries and badges — the callouts are the index. Open a report under `tools/console/state/reports/<task>/` only when an entry needs its context to rule on.
- Cluster the callouts by what they are about, and present the clusters as a numbered list: a count, one representative quote, and the tasks it covers.
- Write the user's rulings as flags, one call per task: `curl -sX POST localhost:8347/api/flag -d '{"id": "<task_id>", "level": 1}'`. Level 1 sorts first in the console's finalize lens; level 0 clears the flag. The flag is the whole ruling.
<!-- /batch:skip -->

## Lib addition protocol

A new primitive qualifies for `programs/lib.dl` through real use in the corpus, not by looking general. The order:

1. Write the primitive as plain body relations, keyed when cases share it. If the linter would flag it, write it as a proposal comp: a `.comp` named for the primitive, which exists only as the code form of a lib proposal. An extension of a lib comp has no comp form; its local rule sits beside the instance. Run it. Confirm it works in context.
2. Surface it: name it, describe the operation, show the solver-local version, and send an opus agent to sweep `programs/solvers/` for sites that hand-write it. Tell the agent what is not this concept, and ask whether the interface should change. Dispatch it early, and write the report or review after it returns, carrying the result. Do not sweep yourself.
3. Recommend a verdict on the sweep. Each verdict is the user's word, like `next` and `commit`; act on none without it.
    - promote — repeated real use, or the sweep changed the interface
    - close — no second home. Plain relations stay as written. A proposal comp goes with its proposal: the arithmetic it held seemed necessary and is not, so the solver's encoding is rethought in relational form.
    - park — worth keeping with no second home yet; a `docs/wf-solver/proposals.md` entry carrying the sweep's result. Any proposal comp stays.
4. On `promote`: move it to `programs/lib.dl` and update the surfacing solver. On `migrate`: an opus agent migrates the sweep's homes, and a separate opus agent runs Simplify and Prune over what changed.

The same gates cover changes to what already stands: an edit to an existing `lib.dl` primitive, or to a term's definition in `concepts.md`, starts at step 2 with the change as the sweep's target.

A proposal comp outlives its verdict only when parked: after the verdict, a comp with no `proposals.md` entry is a defect. Later reuse of a parked entry goes under `Second home` and is promotion evidence.
