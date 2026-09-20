+ index: headings
* comment: when editing this doc
    - Write in the imperative mood.
    - Do not add notices about tooling when it would not change the reader's action or when the tooling already explains itself

# Procedure
- The operations of a solver session.
- The entry point that runs them lists the ones its pass takes.

## Every pass
- **Task per operation.** Create a task per operation, and do them one at a time.
- **Lib protocol.** Apply the lib addition protocol where its trigger holds.
- **Roles.**
    - Run `uv run python scripts/context.py role <role>`.
    - Spawn the agent its first line names.
    - The prompt is the rest of its output, followed by the brief.
- **Source reading.**
    - Do not read `src/dl/` during a pass.
    - If you do, report to the user why, as a gap in the docs or the runner.
- **Corpus.**
    - Take a draft as no evidence for a claim about the corpus.
    - Cite a draft in a doc under `docs/` only in a survey result.
- **Keywords.**
    - If no keyword in [Keywords](docs/handbook/keywords.md) fits, propose one in the review, and add it to the solver's `@keywords:` line.
    - If an existing keyword's gloss should change, propose it in the review.

## Operations

### Draft
1. Analyze the task and the reference TS solver.
    - When they are not in the message, read them: `cat data/tasks/<task_id>.json ../arc-synth-bun/programs/solvers/<task_id>.ts`.
    - Do not pipe the task into anything.
    - The reference TS solver solves the task.
    - It might not encode the best model.
2. Write the solver (`programs/solvers/<task_id>.dl`).
    - Write the header's `@scene` and `@rule` lines with it.
    - Leave the `Determine` comp for the Determine operation.

### Develop
1. Run the solver (`uv run python scripts/run_dl.py <task_id>`).
2. Iterate until it works and passes lint.
    - When a hint appears, judge it, and put that judgment in the review.
    - Flag performance issues in the review.
    - When a performance issue prevents the principled form, make a temporary workaround, marked with the `@workaround` directive.
3. Look for peer models, and make the cases exactly the models that meet the case conditions.
    - If you find a model that meets the case conditions, add it.
    - For each parameter, try the model that derives its value from the input.
    - For each input-derived value constant across pairs, try the model that stores it in a parameter.
    - A model equivalent to the model of a case the solver already has stays out of the review.
4. Run the audit (`uv run python scripts/run_dl.py audit <task_id>`) and resolve the findings.

### Determine
- Run the plan (`uv run python scripts/run_dl.py determination-plan <task_id>`).
- When the plan lists actions and a different parameterization would give a simpler or more principled model, change the parameterization and run [Develop](docs/handbook/procedure.md#develop) again over the changed solver.
- Otherwise, do the actions the plan lists.
- In the plan's over-the-limit section, pick whichever parameters are simplest to determine until the product of the remaining candidate counts goes under the enumeration limit.

### Witness
- **Concept and branch claims.**
    - Write the header and branch lines.
    - Judge each plausibility and verdict from the witness and each case's output on it.
    - List each plausibility and verdict in the review.
    - On a branch's witness, an `other` verdict, or a non-concept verdict at `ordinary` plausibility, identifies a problem with the concept case.
- **Divergence witness.**
    - Build each witness the header requires.
    - Write every case's output on it.
- The condition a dropped peer fails decides what the review gives for it.
    - A peer dropped under Fidelity requires a witness in the review.
    - A model that fails Fit stays out of the review, including any note that it was considered.
- For each approximated rule, state in the review why no set of clauses states it.
- When no witness can be built, replace the rule's text with the approximation's and remove the `@approximated:` line.
- Record each witness with `uv run python scripts/run_dl.py record <task_id> <witness id> --separates "<what it separates>"`, with the grid on stdin.
    - For an `other` verdict, take the judged output from `uv run python scripts/run_dl.py grid <task_id>` on a control grid: the witness changed so that the program's output is the concept's reading.
- Choose a witness on which each model's output is defined, or write an undefined outcome as such.
- When the divergence requires a parameter to be reassigned, reassign that parameter.
* comment:
    - The audit runs the same check.
- `uv run python scripts/run_dl.py witness <task_id>` reads the solver against `programs/witnesses/<task_id>.wit.json`, whose shape is below.
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
- Use a string for a lib constant and a list for a record.
- A `<case>` takes one of these forms:
    - the constructor's name, such as `Alt`
    - under a record-typed `Choice`, the record of the fields' constructor names, such as `[Table, Lookup]`
    - under a constructor with fields, the constructor applied to its fields' constructor names, such as `Recolor(Box, Size)`
- For each entry named by `@witness`, put exactly the block's `@reassigned` parameters in `assign`.

### Simplify
- Express what the code claims with less code.
- The model, its parameterization, and its cases stay as they are.
- **Awkward code.** The targets are code that:
    - Reimplements what the lib provides.
    - Reads as implementation detail with no conceptual meaning.
    - Has repetition where a principled form exists.
    - Has unusual or needless indirection.

### Prune
- The reader is a future session that needs to understand the solver and its model hypothesis.
- Cut everything that does not serve that reader, exhaustively, from unnecessary words to irrelevant ideas.
- Judge necessity from the artifact alone, not from the session.
- Prune text copied from prior solvers like new text.
- Keep the prose plain.
- Do not compress it into a telegraphic style.

### Review
- Write the review for the user to act on.
- Include only items that the user can act on:
    - A case to keep or add.
    - An operation to promote.
    - A judgment call the session made.
    - An issue with something in a doc or tool that resulted in friction.
    - An item carried over from an earlier pass's report or the handoff brief, marked with the pass it came from.
        - Do not recheck it against the current runner, lib, or docs.
    - A fix or a problem in a file the pass does not edit, with the file, the line, and the fix it needs.
