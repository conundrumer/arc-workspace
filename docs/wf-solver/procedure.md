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
- **Outside the pass.** Fix a problem in a file the pass does not edit when the docs say how and the fix raises no new issue. Otherwise put it in the review with the file, the line, and the fix it needs.
- **Roles.** Spawn a role as the agent the first line of `.claude/roles/<role>.md` names, `handbook` by default. The prompt is that file's text, followed by the brief.
- **Source reading.** Do not read `src/dl/` during a pass. If you do, report to the user why, as a gap in the docs or the runner.
- **Corpus.** Take a draft as no evidence for a claim about the corpus, and cite one in a doc under `docs/` only in a survey result.
- **Keywords.**
    - If no keyword in `keywords.md` fits, propose one in the review, and add it to the solver's `keywords:` line.
    - If an existing keyword's gloss should change, propose it in the review.

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
    - Flag performance issues in the review. If they prevent the principled form, make a temporary workaround, marked with the `@workaround` directive.
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
- A fix or a problem in a file the pass does not edit.
- An item carried over from an earlier pass's report or the handoff brief, marked with the pass it came from. Do not recheck it against the current runner, lib, or docs.

Ask these questions:

- Does the solver follow principles? Judge this independently of lint and passing pairs.
- Does any awkward code, as Simplify defines it, remain? Raise what its fix needs.
- Are there potential peer models?
    - **Equivalence.** Do not propose, and do not list in the review, a model equivalent to the model of a case the solver already has.
- When the plan listed actions, could changing the parameterization produce a simpler or more principled model?

**Concept and deviation.** Write the concept statement on the header's `concept:` line, and each non-intended branch's three estimates on its `@deviation` line, as style.md states them. A branch's `-` and `~` estimates are read off the witness file, from the branch's witness with the fewest violated invariants of the inputs.

**Divergence witness.** For each Choice case pair, and for each peer model considered and dropped, show where the models diverge, as a concrete witness: an input grid and each model's output on it.

- The test a dropped peer fails decides what that peer owes.
    - A peer dropped under Fidelity owes a witness.
    - A peer dropped under Equivalence owes the statement that no witness exists.
    - A peer that fails Fit stays out of the review.
- Take that witness from `uv run python scripts/run_dl.py grid <task_id>`, which runs the solver on a grid the session writes, of any size and any content.
- Choose a witness on which each model's output is defined, or record an undefined outcome as such.
- When the divergence requires a parameter to be reassigned, reassign that parameter.
- Write each witness to `programs/witnesses/<task_id>.wit.json`, whose shape style.md states. `uv run python scripts/run_dl.py witness <task_id>` checks the file and each `@deviation` line against it, and the audit runs that check.

**Ruled-out models.** Do not include a model that fails Fit, not even as a note on why it is absent.

**Delivery.** Write the review as a reply to the user. Finish all task updates first, and end the turn with the review.
