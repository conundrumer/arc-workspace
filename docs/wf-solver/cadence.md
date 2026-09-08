<!-- When editing this doc:
- Write in the imperative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed. -->

# Cadence

A solver session writes a Souffle solver (`programs/solvers/<task_id>.dl`) that models an ARC task. A solver session runs in passes. Each pass is a sequence of operations. Do each operation individually. Do not batch them. Create a task per operation.

In every pass, when an encoding in the solver needs a banned form, or when a grep for its shape over `programs/solvers/` finds another solver that writes it, apply the lib addition protocol (lib-protocol.md) to that encoding.

## Operations

**Create.**

1. Analyze the task and the reference TS solver. When they are not in the message, read them: `cat data/tasks/<task_id>.json ../arc-synth-bun/programs/solvers/<task_id>.ts`. The task is already formatted. Do not pipe it into anything. The reference TS solver solves the task but might not encode the best model.
2. Draft the solver. Do not write the `Determine` comp yet.
    - Write setup following the corpus's precedent. Fidelity and reuse take priority over it.
3. Run against materialized train+test pairs (`uv run python scripts/run_dl.py <task_id>`)
4. Iterate until it works and passes lint.
    - When a hint appears, judge it, and put that judgment in the review.
    - If there are performance issues, flag them in the review for future tooling fixes.
        - If they prevent the solver from being in its principled form, make a temporary workaround.
5. Run the audit (`run_dl.py audit <task_id>`) and resolve the findings. Raise judgment calls in the review.

**Simplify.** Make the code express the same hypothesis with less code. The targets are code that is roundabout, code that reads as implementation detail with no conceptual meaning, code that reimplements what lib holds, and repeated code where a principled form exists. What the code claims stays as it is.

**Prune.** For Prune and for `revise`, the reader is a future session that needs to understand the solver and its model hypothesis. Cut everything that does not serve that reader, exhaustively, from unnecessary words to irrelevant ideas. Judge necessity from the artifact alone, not from the session. Text copied from prior solvers may not have been pruned. Prune it like new text. The prose stays plain. Do not compress it into a telegraphic style.

**Determination-plan.** Run `determination-plan` and report the verdict (bold it) on whether a determination pass is needed.

**Review.**

- Write the review for the user to act on: keep or add cases, fix awkward code, promote primitives. Include only items that the user can act on.
- Does it follow principles? Judge this independently of lint and passing pairs.
- Is there anything awkward or roundabout, like code that reads as pure implementation details with no conceptual meaning, or code that reimplements something existing, or repetitive code that might have a more principled form?
- Any potential peer models? Do not propose alt impls, and do not list them in the review.
- For each Choice case pair, and for each peer model considered and dropped, show where the models diverge, as a concrete witness. A witness is an input fragment and each model's output on it, taken from `uv run python scripts/run_dl.py grid <task_id>`. When the divergence requires a parameter to be reassigned, reassign that parameter. Choose a witness that shows a valid divergence. For data-indistinguishable pairs, state what the shared data hides. Do not include a model that the data rules out, not even as a note on why it is absent.
- Write the review as a reply to the user, and end the turn with it: finish all task updates first, then write it with no tool calls after it.

## Passes

The creation pass comes first. Run its operations in this order:

1. Create.
2. Simplify.
3. Prune.
4. Determination-plan.
5. Review.

When the user says `determine`, the determination pass runs:

1. Run `determination-plan`. If there are no actions to take, you are done.
2. Do the determination-plan actions.
    - In the plan's over-budget section, pick whichever settling parameters are simplest to determine until the product of the rest goes under the budget.
3. Simplify, then Prune.
4. Review as before, where applicable. Also ask whether changing the parameterization could produce a simpler or more principled model.

When the user says `cleanup`, run Simplify, then Prune.

Do not read `src/dl/` during a pass. The docs and the run output have all the information you need. Anticipating or confirming anything by reading the source is unnecessary. If you choose to read the source, that indicates a gap or error in the docs or runner. Report to the user why you read it.
