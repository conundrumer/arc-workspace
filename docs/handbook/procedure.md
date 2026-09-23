* comment: when editing this doc
    - Write in the imperative mood.
    - Do not add notices about tooling when it would not change the reader's action or when the tooling already explains itself.

# Procedure
- The operations a pass runs, and what holds for every pass.

## Every pass
- **One operation at a time.** Finish each operation before you start the next.
- **Lib protocol.** Apply [Lib addition protocol](docs/handbook/lib-protocol.md) where its trigger holds.
- **Source reading.**
    - Do not read `src/dl/` during a pass.
    - If you do, say why in the review, as a gap in the docs or the runner.
- **Corpus.**
    - Take a draft as no evidence for a claim about the corpus.
    - Cite a draft in a doc under `docs/` only in a survey result.
- **Keywords.**
    - If no keyword in [Keywords](docs/handbook/keywords.md) fits, propose one in the review, and add it to the solver's `@keywords:` line.
    - If an existing keyword's gloss should change, propose it in the review.

## Every session
- **Cleanup.** When the user says `cleanup`, run [Simplify](#simplify), then [Prune](#prune).
- **Roles.**
    - Run `uv run python scripts/context.py role <role>`.
    - Spawn the agent its first line names.
    - The prompt is the rest of its output, followed by the brief.

## Review items
- A pass that asks for a report and no review puts the items the operations route to the review in that report.
- A pass that asks for a review and no report puts the items the messages route to the report in that review.

## Operations

### Analyze
1. Read the task: `cat data/tasks/<task_id>.json`.
    - Do not pipe the task into anything.
    - Read it whole here; a probe you write may load the file.
    - A pair's `alt` of kind `rule` is a second candidate, and of kind `tiebreak` a tiebreak.
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
    - `bun scripts/ref.ts <task_id>` runs it on the grid on stdin.
2. Form every other branch.
    - A branch is stated by the slugs of the claims it replaces or adds, and its parameters.
    - A branch that derives a parameter's value, or stores a value the program derives, is stated as that derivation or that stored value, and by the claim it replaces.
    - Form them from the pairs, the reference TS solver, the headers of the solvers under `programs/solvers/`, probes over the pairs, and variant tasks.
        - `grep -l '^// @keywords:.*<keyword>' programs/solvers/*.dl` lists the solvers under a keyword, and `awk '/^$/{exit} 1' programs/solvers/<id>.dl` prints one solver's header.
        - A probe is a script you write under `.scratch/<task_id>/` that runs a reading over grids and prints the outputs.
    - Name each branch by a slug of its own.
    - A claim considered and not formed as a branch goes under Not formed, with why.
3. Place each choice point at the concept or under a branch, as [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) states.
    - For each two choice points where neither stands under a branch of the other, state the model of a case that takes a non-concept branch at both.
    - When that model is one branch's model alone, the other point's property does not exist with that branch, and that section says where the point goes.
    - Report an open parameter with its open values.
4. Judge each branch's standing.
    - The concept case: each witness with verdict `other` that no branch below lists, with the items below, and the rule restated as the generator applies it, which the concept file's rule approximates.
    - A branch that fails Fit: the pair it fails.
    - A branch that fits every pair: one of its witnesses, with:
        - its id in the witness file
        - the scene claim the witness breaks, when it breaks one
        - the assignment it stands at, when that is not the stored one
        - its plausibility and verdict
    - A branch with no witness: why there is none.
5. Write the witnesses to `.scratch/<task_id>/witnesses.json` in the witness file's shape, with each branch's slug as its name, and every fitting branch in the groups of each witness.
    - `uv run python scripts/run_dl.py witness --file .scratch/<task_id>/witnesses.json` checks the file's shape.
6. Write the report to `.scratch/<task_id>/report.md`, in this form:

    ```
    # <task_id>

    ## Concept
    - <its standing, and what the steps after the concept found about it>

    ## Choice points
    - `<property>`
        - `concept`: <the concept branch>
        - `<branch>`: <its claims>, <its standing>
            - `<property>`: <a choice point under this branch, in the same form, with this branch as its concept branch>
    - `<property>` & `<property>`: <the model of a case that takes a non-concept branch at both>

    ## Not formed
    - <claim>: <why>

    ## Interference
    - <the doc or tool line that interfered, and how>, or `none`
    ```

### Write
1. Read the task: `cat data/tasks/<task_id>.json`.
    - Do not pipe the task into anything.
2. Read the Analyze files, one at a time: `.scratch/<task_id>/concept.md`, `report.md`, and `witnesses.json`.
    - The concept file gives the concept case's claims, and the report gives each branch's standing.
3. Write the solver (`programs/solvers/<task_id>.dl`).
    - Write the header's `@scene` and `@rule` lines from the concept file's claims, and `Params` from its parameters, under their names.
    - A rule the report restates takes the restated text, and the concept file's text stands under it as its `@approximated:` line.
    - Each branch the report gives a witness is a constructor, nested as the report nests its choice point.
    - A concept branch's constructor takes a name of your own.
    - The cases are the combinations of those branches that fit, which the run shows.
    - A `<property>` & `<property>` line of the report gives what a case that takes both branches reads.
    - Leave the `Determine` comp for the Determine operation.

### Develop
1. Run the solver (`uv run python scripts/run_dl.py <task_id>`).
2. Iterate until it works and passes lint.
    - When a hint appears, judge it, and put that judgment in the review.
    - Flag performance issues in the review.
    - When a performance issue prevents the principled form, make a temporary workaround, marked with the `@workaround` directive.
3. Form each claim under the report's Not formed as a branch, and add its case when it meets the case conditions.
4. Hold each branch that derives a parameter's value, or stores a value the program derives, as a case.
    - `uv run python scripts/run_dl.py derive <task_id>` lists the built-in derivations that fit.
    - `uv run python scripts/run_dl.py store <task_id>` lists the derived values it holds as stored cases.
    - Write the directive line each prints, in the form the [`@derive` directive](docs/handbook/solver-file.md#params) gives, with the plausibility and verdict the report gives the branch.
    - A branch the runner holds loses its constructor and gets no clauses of its own.
5. Run the audit (`uv run python scripts/run_dl.py audit <task_id>`) and resolve the findings.

### Determine
- Run the plan (`uv run python scripts/run_dl.py determination-plan <task_id>`).
- When the plan lists actions and a different parameterization would give a simpler or more principled model, change the parameterization, run [Develop](#develop) again over the changed solver, and put the change in the review.
- Otherwise, do the actions the plan lists.
- In the plan's over-the-limit section, pick whichever parameters are simplest to determine until the product of the remaining candidate counts goes under the enumeration limit.

### Witness
- **Concept and branch claims.**
    - Write the `@witness` lines of the header and the branches, with each plausibility and verdict as the report gives it, `@relaxed` for the scene claim it breaks, and `@reassigned` for each parameter of the assignment it stands at.
    - A witness of the concept case with verdict `other` stands under an `@approximated:` line of the rule it breaks.
    - On a branch's witness, an `other` verdict identifies a problem with the concept case, and so does a non-concept verdict at `ordinary` plausibility; it goes in the review as open.
- **Divergence witness.**
    - Copy the witness file: `cp .scratch/<task_id>/witnesses.json programs/witnesses/<task_id>.wit.json`.
    - Remove from the groups each name that denotes no case of the solver, and remove a witness that then separates nothing.
    - Rename each name for a case the runner holds to the form [Witness file](docs/handbook/solver-file.md#witness-file) gives it, and remove a witness of such a branch, which the runner builds itself.
    - Add each branch added in Develop to the groups of every copied witness.
    - Rewrite each `assign` in the form `Params` reads.
    - For a branch added in Develop, build the witness its `@witness` line needs.
    - Judge the plausibility and verdict of a witness you build, and put that judgment in the review.
- A branch dropped under a case condition goes in the review with the condition it fails, and for Relational form with why no set of clauses states its claim.
- For each approximated rule, state in the review why no set of clauses states it.
- When no witness can be built, replace the rule's text with the approximation's and remove the `@approximated:` line.
- Record each witness you build with `uv run python scripts/run_dl.py record <task_id> <witness id> --separates "<what it separates>"`, with the grid on stdin.
    - For an `other` verdict, take the judged output from `uv run python scripts/run_dl.py grid <task_id>` on a control grid: the witness changed so that the program's output is the concept's reading.
- Write an undefined outcome as such.
- When the divergence requires a parameter to be reassigned, reassign that parameter with `--assign`.
* comment:
    - The audit runs the same check.
- `uv run python scripts/run_dl.py witness <task_id>` reads the solver against `programs/witnesses/<task_id>.wit.json`, whose shape [Witness file](docs/handbook/solver-file.md#witness-file) gives.
- Run the audit again when the file is complete.
- `witness` reports a pair of cases that no witness separates. Resolve it by the first that applies, and put the resolution in the review.
    - A case never reads a `Choice` field: the choice point that field encodes stands under the other branches, and the type is reshaped to put it there.
    - The cases' clauses differ: build the witness that shows it.
    - Otherwise, the case that takes more non-concept branches leaves: by an `@ignore: derive` line when the runner holds it, and by an `impl_choice` that omits it when not.

### Simplify
- Express what the code claims with less code.
- The model, its parameterization, and its cases stay as they are.
- Simplify covers code that:
    - Reimplements what the lib provides.
    - Reads as implementation detail with no conceptual meaning.
    - Has repetition where a principled form exists.
    - Has unusual or needless indirection.

### Prune
- The text is the solver's header and comments.
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
    - An issue with a doc or tool that interfered with the pass.
    - An item carried over from an earlier pass's report, marked with the pass it came from.
        - Do not recheck it against the current runner, lib, or docs.
    - A fix or a problem in a file the pass does not edit, with the file, the line, and the fix it needs.
