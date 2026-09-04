# Cadence

A solver session writes a Souffle solver (`programs/solvers/<task_id>.dl`) that models an ARC task. A solver session runs in passes, and each pass is a sequence of operations. Do each operation individually; do not batch them. Create a task per operation.

## Operations

**Create.**

1. Analyze the task and the reference TS solver. When they are not in the message, read them: `cat data/tasks/<task_id>.json ../arc-synth-bun/programs/solvers/<task_id>.ts`
    - The task is already formatted. Do not pipe it into anything.
    - The reference TS solver solves the task but might not encode the best model.
2. Draft the solver. Do not write the `Fit` comp yet.
3. Run against materialized train+test pairs (`uv run python scripts/run_dl.py <task_id>`)
4. Iterate until it works and passes lint. When a hint appears, judge it, and put that judgment in the review.
5. Run the audit (`run_dl.py audit <task_id>`) and resolve the findings. Raise judgment calls in the review.

**Simplify.** Make the code express the same claim with less code. The targets are code that is roundabout, code that reads as implementation detail with no conceptual meaning, code that reimplements what lib holds, and repeated code where a principled form exists. What the code claims stays as it is.

**Prune.** The reader, for Prune and for `revise`, is a future session that needs to understand the solver and its model claim. Cut everything that does not serve that reader, exhaustively, from unnecessary words to irrelevant ideas. Judge necessity from the artifact alone, not from the session. Text copied from prior solvers may not have been pruned; prune it like new text. The prose stays plain; do not compress it into a telegraphic style.

**Fit-plan.** Run `fit-plan` and report the verdict (bold it) on whether there needs to be a fit pass.

**Review.**

- The review is for the user to act on: keep or add cases, fix awkward code, promote primitives. Include only items the user can act on. An item included only as context still makes the user verify it against the rules, which is the work the review should do for them.
- Does it follow principles? The review does not depend on lint or passing pairs.
- Is there anything awkward or roundabout, like code that reads as pure implementation details with no conceptual meaning, or code that reimplements something existing, or repetitive code that might have a more principled form?
- Any potential alt models? Alt impls are not models: do not propose them, and do not list them in the review.
- For each Choice case pair, and for each alt model considered and dropped, show where the models diverge, as a concrete witness. A witness is an input fragment and each model's output on it, taken from `uv run python scripts/run_dl.py grid <task_id>`. When the divergence requires a Consts slot to be refilled, refill that slot. The witness must show a valid divergence: the diverging model's output on it is well-formed. For data-indistinguishable pairs, state what the shared data hides. A model the data rules out was never a candidate: it does not appear in the review, not even as a note on why it is absent.
- The review is a reply to the user, and it ends the turn: finish all task updates first, then write it with no tool calls after it.

## Passes

The creation pass comes first. Run its operations in this order:

1. Create.
2. Simplify.
3. Prune.
4. Fit-plan.
5. Review.

When the user says `fit`, the fit pass runs:

1. Run `fit-plan`. If there are no actions to take, you are done.
2. Do the fit-plan actions.
3. Simplify, then Prune.
4. Review as before, where applicable. Also ask whether changing the Consts shape could produce a simpler or more principled model.

When the user says `cleanup`, run Simplify, then Prune.

Do not read `src/dl/` during a pass. The docs and the run output should have all the information you need. You should not need to anticipate or confirm anything by reading the source. If you choose to read the source, that indicates there is a gap or error in the docs or runner. Report to the user why you read it.
