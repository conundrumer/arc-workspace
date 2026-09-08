<!-- When editing this doc:
- Write in the imperative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed. -->

# Procedure

The operations and passes of a solver session.

## Passes

- **Creation pass.** The first pass. Run every operation, in the order listed.
- **Cleanup pass.** When the user says `cleanup`, run Simplify, then Prune.

## Every pass

- **Task per operation.** Create a task per operation, and do them one at a time.
- **Lib protocol.** Apply the lib addition protocol where its trigger holds.
- **Source reading.** Do not read `src/dl/` during a pass. If you do, report to the user why, as a gap in the docs or the runner.
- **Keywords.** If no keyword in `keywords.md` fits, add one and report it. Do not change an existing keyword's gloss. Propose the change in the review.

## Operations

### Create

1. Analyze the task and the reference TS solver.
    - When they are not in the message, read them: `cat data/tasks/<task_id>.json ../arc-synth-bun/programs/solvers/<task_id>.ts`.
    - Do not pipe the task into anything.
    - The reference TS solver solves the task. It might not encode the best model.
2. Draft the solver (`programs/solvers/<task_id>.dl`).
    - Do not write the `Determine` comp yet.
3. Run it (`uv run python scripts/run_dl.py <task_id>`).
4. Iterate until it works and passes lint.
    - When a hint appears, judge it, and put that judgment in the review.
    - Flag performance issues in the review. If they prevent the principled form, make a temporary workaround.
5. Run the audit (`uv run python scripts/run_dl.py audit <task_id>`) and resolve the findings.

### Determine

Run the plan (`uv run python scripts/run_dl.py determination-plan <task_id>`) and do the actions it lists.

- In the plan's over-budget section, pick whichever settling parameters are simplest to determine until the product of the rest goes under the budget.

### Simplify

Express what the code claims with less code. The model, its parameterization, and its cases stay as they are.

**Awkward code.** The targets are code that:

- Reimplements what lib holds.
- Reads as implementation detail with no conceptual meaning.
- Has repetition where a principled form exists.
- Has unusual or needless indirection.

### Prune

The reader is a future session that needs to understand the solver and its model hypothesis.

- Cut everything that does not serve that reader, exhaustively, from unnecessary words to irrelevant ideas.
- Judge necessity from the artifact alone, not from the session.
- Prune text copied from prior solvers like new text.
- Keep the prose plain. Do not compress it into a telegraphic style.

### Review

Write the review for the user to act on.

Include only items that the user can act on:

- A case to keep or add.
- A primitive to promote.
- A judgment call the session made.
- A gap in a doc or a tool.

Ask these questions:

- Does the solver follow principles? Judge this independently of lint and passing pairs.
- Does any awkward code, as Simplify defines it, remain? Raise what its fix needs.
- Are there potential peer models?
    - **Implementations.** Do not propose another implementation of a model, and do not list one in the review.
- When the plan listed actions, could changing the parameterization produce a simpler or more principled model?

**Divergence witness.** For each Choice case pair, and for each peer model considered and dropped, show where the models diverge, as a concrete witness: an input fragment and each model's output on it.

- Take that witness from `uv run python scripts/run_dl.py grid <task_id>`.
- Choose a witness that shows a valid divergence.
- When the divergence requires a parameter to be reassigned, reassign that parameter.
- For data-indistinguishable pairs, state what the shared data hides.

**Ruled-out models.** Do not include a model that the data rules out, not even as a note on why it is absent.

**Delivery.** Write the review as a reply to the user. Finish all task updates first, and end the turn with the review.
