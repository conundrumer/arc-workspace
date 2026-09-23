* comment: when editing this doc
    - Write in the imperative mood.
    - Do not add notices about tooling when it would not change the reader's action or when the tooling already explains itself.

# Procedure
- The operations a pass runs, and what holds for every pass.

## Every pass
- **One operation at a time.** Finish each operation before you start the next.
- **Cleanup.** When the user says `cleanup`, run [Simplify](#simplify), then [Prune](#prune).
- **Lib protocol.** Apply [Lib addition protocol](docs/handbook/lib-protocol.md) where its trigger holds.
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

## Review items
- A pass that asks for a report and no review puts the items the operations route to the review in that report.
- A pass that asks for a review and no report puts the items the messages route to the report in that review.

## Operations

### Analyze
1. Read the task: `cat data/tasks/<task_id>.json`.
    - Do not pipe the task into anything.
2. Write the concept to `.scratch/<task_id>/concept.md`, in this form:
    ```
    # <task_id>

    ## Scene
    - `<slug>`: <what every input contains, as the concept reads it>

    ## Rules
    - `<slug>`: <what the output takes from the input>

    ## Parameters
    - `<name>`: <its value, or each open value>
        - <what it holds, where the name does not say>
    ```
    - Check that it fits every pair.
    - After this step, the file is not changed.
3. Only after step 2 is complete, read the next steps: `cat .claude/analyze-next.md`.

### Analyze after the concept
1. Read the reference TS solver: `cat ../arc-synth-bun/programs/solvers/<task_id>.ts`.
    - The reference TS solver solves the task.
    - Each claim it makes that the concept statement does not make, or makes differently, is a branch.
2. Form every other branch.
    - A branch is stated by the slugs of the claims it replaces or adds, and its parameters.
    - A branch that derives a parameter's value, or stores a value the program derives, is stated as that derivation or that stored value.
    - Form them from the pairs, the reference TS solver, the headers of the solvers under `programs/solvers/`, probes over the pairs, and variations of the task.
        - `grep -l '^// @keywords:.*<keyword>' programs/solvers/*.dl` lists the solvers under a keyword, and `awk '/^$/{exit} 1' programs/solvers/<id>.dl` prints one solver's header.
3. Judge each branch's standing.
    - The concept case: each witness with verdict `other`, with the items below and the judged output.
    - A branch that fails Fit: the pair it fails.
    - A branch that fits every pair: one of its witnesses, with:
        - the input and the outputs on it, as a probe prints them
        - the scene claim the witness breaks, when it breaks one
        - the assignment it stands at, when that is not the stored one
        - its plausibility and verdict
    - A branch with no witness: why there is none.
4. Write the witnesses to `.scratch/<task_id>/witnesses.json` in the witness file's shape, with the branch names as the case names and every fitting branch in each witness's groups.
5. Write the report to `.scratch/<task_id>/report.md`, in this form:

    ```
    # <task_id>

    ## Concept
    - <its standing, and what the steps after the concept found about it>

    ## Choice points
    - `<property>`
        - `concept`: <the concept branch>
        - `<branch>`: <its claims>, <its standing>

    ## Not formed
    - <claim>: <why>
    ```

### Write
1. Read the task and the reference TS solver.
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
        - Your own judgment or taste is not grounds for omitting it.
    - For each parameter, try the model that derives its value from the input.
        - The runner has built-in derivations. `uv run python scripts/run_dl.py derive <task_id>` lists the ones that fit, and holds each as a case unless an `@ignore: derive` line dismisses it; write no branch for those.
        - Write every other derivation as a branch.
    - For each value the program fixes or derives, try the model that stores it.
        - `uv run python scripts/run_dl.py store <task_id>` lists the derived ones.
            - Write no branch for one the runner holds as a case.
4. Run the audit (`uv run python scripts/run_dl.py audit <task_id>`) and resolve the findings.

### Determine
- Run the plan (`uv run python scripts/run_dl.py determination-plan <task_id>`).
- When the plan lists actions and a different parameterization would give a simpler or more principled model, change the parameterization and run [Develop](#develop) again over the changed solver.
- Otherwise, do the actions the plan lists.
- In the plan's over-the-limit section, pick whichever parameters are simplest to determine until the product of the remaining candidate counts goes under the enumeration limit.

### Witness
- **Concept and branch claims.**
    - Write the header and branch lines.
    - Judge each plausibility and verdict from the witness and each case's output on it.
    - List each plausibility and verdict in the review.
    - On a branch's witness, an `other` verdict identifies a problem with the concept case, and so does a non-concept verdict at `ordinary` plausibility.
- **Divergence witness.**
    - Build each witness the header requires.
    - Write every case's output on it.
- The condition a dropped peer fails decides what the review gives for it.
    - A peer dropped under Relational form requires in the review why no set of clauses states its claim.
    - A model that fails Fit or Equivalence stays out of the review, including any note that it was considered.
- For each approximated rule, state in the review why no set of clauses states it.
- When no witness can be built, replace the rule's text with the approximation's and remove the `@approximated:` line.
- Record each witness with `uv run python scripts/run_dl.py record <task_id> <witness id> --separates "<what it separates>"`, with the grid on stdin.
    - For an `other` verdict, take the judged output from `uv run python scripts/run_dl.py grid <task_id>` on a control grid: the witness changed so that the program's output is the concept's reading.
- Write an undefined outcome as such.
- When the divergence requires a parameter to be reassigned, reassign that parameter.
* comment:
    - The audit runs the same check.
- `uv run python scripts/run_dl.py witness <task_id>` reads the solver against `programs/witnesses/<task_id>.wit.json`, whose shape [Witness file](docs/handbook/solver-file.md#witness-file) gives.
- Use a string for a lib constant and a list for a record.
- [`GRID_HxW` for grid data](docs/handbook/patterns.md#grid_hxw-for-grid-data) states the form of a stored grid.
- A `<case>` takes one of these forms:
    - the constructor's name, such as `Alt`
    - under a record-typed `Choice`, the record of the fields' constructor names, such as `[Table, Lookup]`
    - under a constructor with fields, the constructor applied to its fields' constructor names, such as `Recolor(Box, Size)`
    - `<param>=<Proposer>` for a case the runner holds under `@derive`
    - `<rel>=stored` for a case the runner holds under `@store`, whose entry has `output` per case and no `assign`
- For each witness `@witness` names, put exactly the block's `@reassigned` parameters in `assign`.

### Simplify
- Express what the code claims with less code.
- The model, its parameterization, and its cases stay as they are.
- Simplify covers code that:
    - Reimplements what the lib provides.
    - Reads as implementation detail with no conceptual meaning.
    - Has repetition where a principled form exists.
    - Has unusual or needless indirection.

### Prune
- The reader is a future session that needs to understand the solver and its model hypothesis.
- Cut everything that does not serve that reader, exhaustively, from unnecessary words to irrelevant ideas.
- Judge necessity from the artifact alone, not from the session that built it.
- Prune text copied from prior solvers like new text.
- Keep the prose plain.
- Do not compress it into a telegraphic style.

### Promote
- When the user says `promote` or `migrate` over an entry under `docs/wf-solver/proposals/`.
- On `promote`, move the plain relations or proposal comp into the module under `programs/lib/` whose file doc admits it, and update the solver that introduced the proposal.
- On `migrate`:
    1. Spawn the `migrate` role with the entry's path, the lib relation it became, the entry's callers, and the promotion's time.
    2. Spawn the `cleanup` role with the files and spans that `migrate` changed, the lib call they now make, and a scratch path under `.scratch/`.
    3. List in the review the callers that `migrate` skipped.

### Review
- Write the review as the record of the pass.

#### The items
- Include only:
    - A lib operation to promote.
    - A judgment the session made.
    - An issue with something in a doc or tool that resulted in friction.
    - An item carried over from an earlier pass's report, marked with the pass it came from.
        - Do not recheck it against the current runner, lib, or docs.
    - A fix or a problem in a file the pass does not edit, with the file, the line, and the fix it needs.
