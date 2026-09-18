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
    - If no keyword in `keywords.md` fits, propose one in the review, and add it to the solver's `@keywords:` line.
    - If an existing keyword's gloss should change, propose it in the review.

## Operations

### Create

1. Analyze the task and the reference TS solver.
    - When they are not in the message, read them: `cat data/tasks/<task_id>.json ../arc-synth-bun/programs/solvers/<task_id>.ts`.
    - Do not pipe the task into anything.
    - The reference TS solver solves the task. It might not encode the best model.
2. Draft the solver (`programs/solvers/<task_id>.dl`).
    - Draft the header's `@scene` and `@rule` lines with it.
    - Do not write the `Determine` comp yet.
3. Run it (`uv run python scripts/run_dl.py <task_id>`).
4. Iterate until it works and passes lint.
    - When a hint appears, judge it, and put that judgment in the review.
    - Flag performance issues in the review. If they prevent the principled form, make a temporary workaround, marked with the `@workaround` directive.
5. Run the audit (`uv run python scripts/run_dl.py audit <task_id>`) and resolve the findings.

### Determine

Run the plan (`uv run python scripts/run_dl.py determination-plan <task_id>`) and do the actions it lists.

- In the plan's over-the-limit section, pick whichever parameters are simplest to determine until the product of the remaining candidate counts goes under the enumeration limit.

### Simplify

Express what the code claims with less code. The model, its parameterization, and its cases stay as they are.

**Awkward code.** The targets are code that:

- Reimplements what the lib provides.
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
- An operation to promote.
- A judgment call the session made.
- A gap in a doc or a tool.
- A fix or a problem in a file the pass does not edit.
- An item carried over from an earlier pass's report or the handoff brief, marked with the pass it came from. Do not recheck it against the current runner, lib, or docs.

Ask these questions:

- Does the solver follow principles? Judge this independently of lint and passing pairs.
- Does any awkward code remain? Raise what its fix needs.
- Are there potential peer models?
    - **Equivalence.** Do not propose, and do not list in the review, a model equivalent to the model of a case the solver already has.
    - **Drops.** Do not drop a peer that meets the case conditions, for any reason.
- When the plan listed actions, could changing the parameterization produce a simpler or more principled model?

**Concept and branch claims.** Write the header and branch lines. Judge each plausibility and verdict from the witness and each case's output on it. List each plausibility and verdict in the review. On a branch's witness, an `other` verdict, or a non-concept verdict at `ordinary` plausibility, identifies a problem with the concept case.

**Divergence witness.** Build each witness the header requires, and write every case's output on it.

- The condition a dropped peer fails decides what the review gives for it.
    - A peer dropped under Fidelity requires a witness in the review.
    - A peer dropped under Equivalence requires the statement that no witness exists.
    - A model that fails Fit stays out of the review, including any note that it was considered.
- For each approximated rule, state in the review why no set of clauses states it. When no witness can be built, replace the rule's text with the approximation's and remove the `@approximated:` line.
- Record each witness with `uv run python scripts/run_dl.py record <task_id> <witness id> --separates "<what it separates>"`, with the grid on stdin.
    - For an `other` verdict, take the judged output from `uv run python scripts/run_dl.py grid <task_id>` on a control grid: the witness changed so that the program's output is the concept's reading.
- Choose a witness on which each model's output is defined, or write an undefined outcome as such.
- When the divergence requires a parameter to be reassigned, reassign that parameter.
- `uv run python scripts/run_dl.py witness <task_id>` checks the solver against `programs/witnesses/<task_id>.wit.json`, whose shape is below. The audit runs the same check.

```
{ "id": <task_id>,
  "witnesses": [{
    "id": slug,                              // unique within this file
    "separates": string,                     // models separated by this input
    "input": Grid,
    "assign": {<parameter>: Fact[] | Grid},  // GRID_HxW form from patterns.md for stored parameters
    "output": {<case>: Grid | null}          // when the verdict is not other: each case's output, with null for undefined
            | Grid                           // when the verdict is other: the annotator's judged output
  }] }

Grid: number[][]                      // rows of colors
Fact: Arg[]                           // the arguments of one fact
Arg: number | string | Arg[]
```

Use a string for a lib constant and a list for a record.

A `<case>` takes one of these forms:

- the constructor's name, such as `Alt`
- under a record-typed `Choice`, the record of the fields' constructor names, such as `[Table, Lookup]`
- under a constructor with fields, the constructor applied to its fields' constructor names, such as `Recolor(Box, Size)`

For each entry named by `@witness`, put exactly the block's `@reassigned` parameters in `assign`.

**Delivery.** Write the review as a reply to the user. Finish all task updates first, and end the turn with the review.
