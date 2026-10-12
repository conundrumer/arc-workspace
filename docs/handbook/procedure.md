* comment: when editing this doc
    - Do not add notices about tooling when it would not change the reader's action or when the tooling already explains itself.

# Procedure
- The operations a pass runs, and what holds for every pass.

## Every pass
- **One operation at a time.** Finish each operation before you start the next.
- **Reading files.** Read the task with `cat data/tasks/<task_id>.json`, and each other file you need whole, with no other command piped or chained to the read.
- **Lib protocol.** Apply [Lib addition protocol](docs/handbook/lib-protocol.md) where its trigger holds.
- **Source reading.**
    - Do not read `src/` during a pass.
    - If you do, say why in the review, as a gap in the docs or the runner.
- **Corpus.**
    - Take a draft as no evidence for a claim about the corpus.
- **Keywords.**
    - If no keyword in [Keywords](docs/handbook/keywords.md) fits, propose one in the review, and add it to the solver's `@keywords:` line.
    - If an existing keyword's gloss should change, propose it in the review.
    - If the solver's `@keywords:` line carries `induce`, judge by [Demonstrated choice](docs/handbook/solver-file.md#demonstrated-choice) whether the task is a nested task, and where it is, give the solver the case that section gives.
        * comment: The Create pass on 2ccd9fef took `induce` from its gloss, did not follow the gloss's link to Demonstrated choice, and wrote no catalog case, as change ticket 4-47 records.

## Every session
- **Cleanup.** When the user says `cleanup`, run [Simplify](#simplify), then [Prune](#prune).
- **Roles.**
    - Run `uv run python scripts/context.py role <role>`.
    - Spawn the agent its first line states.
    - The prompt is the rest of its output, followed by the brief.

## Review items
- A pass that asks for a report and no review puts the items the operations route to the review in that report.
- A pass that asks for a review and no report puts the items the messages route to the report in that review.

## Operations

### Analyze
1. Read the task whole with `cat data/tasks/<task_id>.json`, with no other command piped or chained to it; a script you write may load the file.
    * comment:
        - The command and the rule on piping and chaining are here as well as under Every pass because the Analyze render does not carry Every pass.
    - A pair's `alt` of kind `rule` is a second candidate, and of kind `tiebreak` a tiebreak.
2. Write the concept to `work/task/<task_id>/concept.md`, in this form:
    ```
    # <task_id>

    ## Concept
    - <what the task is an instance of, as one person would say it to another>

    ## Scene
    - `<slug>`: <what every input contains, as the concept reads it>

    ## Rules
    - `<slug>`: <what the output takes from the input>

    ## Parameters
    - `<name>`: <its value, or each open value>
        - <what it holds, where the name does not say>

    ## Scene parameters
    - `<name>`: <its value, or each open value>
        - <what it holds, where the name does not say>
    ```
    - A slug is lowercase letters and digits, in words joined by single `-`.
    - Write it from your reading of the pairs alone, before you write any script.
    - Then check that it fits every pair.
        - Where a script of this pass needs what a lib component computes, read the component's interface, then call the component in place of rebuilding it: `lib_components.components` has a function of the same name for each component with no column of a type its caller declares, which runs the component on the rows it is given.
            - The function takes the component's type arguments, each a `Primitive` from `engine.program` or a `LibType` from `lib_components.components`, the grid size of each key as `sizes`, and the rows of each input relation by that relation's name, with a cell as `(row, column)`. It returns each output relation, whose `.rows` is its set of rows as tuples, and whose `.map()` and `.map_per_key()` give a relation that is a function of its leading columns as a dict.
            - `Components(Primitive.NUMBER, sizes={i: (h, w)}, node=[(i, (r, c)), ...]).label.map_per_key()` gives `{i: {(r, c): id}}` for each key `i`.
    - A scene claim fixes no task data.
        - A value a scene claim states that is task data is a parameter: name it in the claim, and list it with this task's value, under Parameters when applying the rules needs its value and under Scene parameters otherwise.
3. Only after step 2 is complete, read the next steps: `cat .claude/analyze-next.md`.

### Analyze after the concept
1. Form every other branch.
    - A branch is stated by the slugs of the claims it replaces or adds, its parameters, and the inputs on which it is undefined.
    - A branch is formed whether or not another branch's model subsumes it, and whatever its witnesses' plausibility.
    - A branch that derives a parameter's value, or stores a value the program derives, is stated as that derivation or that stored value, and by the claim it replaces.
        - The `@derive` directive in [Params](docs/handbook/solver-file.md#params) states the values a parameter takes on an input under a `@derive` branch, and where that branch is undefined.
    - Form them from these sources alone: the pairs, the headers of the solvers under `programs/solvers/`, the lib, the proposers in `programs/proposers.dl`, probes over the pairs, and variant tasks.
        - `grep -l '^// @keywords:.*<keyword>' programs/solvers/*.dl` lists the solvers under a keyword, and `awk '/^$/{exit} 1' programs/solvers/<id>.dl` prints one solver's header.
        - A probe is a script you write under `work/task/<task_id>/` that runs a reading over grids and prints the outputs.
            - A probe whose readings are all written in Souffle, and that needs only each reading's output grid, can be a Souffle file under `work/task/<task_id>/`, its name starting with the task id, that declares a `Choice` with one constructor per reading, `impl_choice` containing each, and `out(p: Position, col: Color, ch: Choice)`. `uv run python scripts/run_dl.py grid <that file> <grid file>` prints each reading's output as a grid, one grid for the readings that give the same one.
                - Each reading in it instantiates the lib components it uses under instances of its own, and no key of a component instance holds a reading or a `Choice`.
            - A probe that needs a component's rows in the script, or would key one instance of a component by reading, calls the component through `lib_components.components`, once per reading where its inputs differ by reading.
    - Name each branch by a constructor name of its own, in the form [Witness file](docs/handbook/solver-file.md#witness-file) gives. The name says what the branch changes and contains no value of a parameter.
    - A claim considered and not formed as a branch goes under Not formed, with why.
2. Place each choice point at the concept or under a branch, as [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) states. A point whose branches' models differ, in an output or in where they are defined, stands at the concept. A point whose branches give one model under another point's concept branch stands under a branch of that point under which they differ.
    - For each two choice points where neither stands under a branch of the other, judge the model of each case that takes a non-concept branch at both.
        - State in one statement every such pair of points where each of those models applies the two branches' changes together.
        - For each other pair, state those models in one statement for the two points, and state on a line of its own the model of each case that statement does not give.
    - When that model is one branch's model alone, the other point's property does not exist with that branch, and that section says where the point goes.
3. Judge each branch's standing.
    - The concept case: each witness with verdict `other` that no branch below lists, with the items below, and the rule restated as the generator applies it, which the concept file's rule approximates.
    - A branch that fails Fit: the pair it fails.
    - A branch that fits every pair: one of its witnesses, on which the branch's model is defined when such a witness exists, with:
        - its id in the witness file: the branch's name, for a branch that derives a parameter's value by a built-in derivation or stores a value the program derives, and a slug otherwise
        - the scene claim the witness breaks, when it breaks one
        - the assignment it stands at, when that is not the stored one
        - its plausibility and verdict
        - the invariant of the inputs it breaks, when its plausibility is below `ordinary`
    - A branch with no witness: why there is none.
4. Write each witness step 3 gives to `work/task/<task_id>/witnesses.json` in the witness file's shape, with an `assign` that reassigns each parameter whose value the assignment step 3 gives it changes, and, in each witness whose verdict is not `other`, each fitting branch in the group of the output the branch's model gives at that witness's assignment.
    * comment: On 2026-09-23, an Analyze pass on a1aa0c1e read this step without the verdict clause, and reported that `four-rungs`, a witness with verdict `other`, had no place for its fitting branches: agent `a12540b7d9e9d4aee` of console session `622904c2-70f8-4e98-830a-3863e040da52`.
    - `uv run python scripts/run_dl.py witness --file work/task/<task_id>/witnesses.json` checks the file's shape.
5. Write the report to `work/task/<task_id>/analyze.md`, in this form:

    ```
    # <task_id>

    ## Concept
    - <its standing, and what the steps after the concept found about it>

    ## Choice points
    - `<property>`
        - `concept`: <the concept branch>
        - `<branch>`: <its statement, as step 1 gives it>, <its standing>
            - `<property>`: <a choice point under this branch, in the same form, with this branch as its concept branch>
    - `<property>` & `<property>`, `<property>` & `<property>`: the two branches' changes applied together
    - `<property>` & `<property>`: <the model step 2 gives for the two points>
        - `<branch>` & `<branch>`: <the model of a case that line does not give>

    ## Open parameters
    - `<name>`: <its open values>, under `<branch>` when one branch alone reads it

    ## Not formed
    - <claim>: <why>

    ## Tickets filed
    - <the name of a file the pass wrote under `tickets/open/`>
    ```

### Write
1. Read the Analyze files, one at a time: `work/task/<task_id>/concept.md`, `analyze.md`, and `witnesses.json`.
    - The concept file gives the concept case's claims, and the Analyze report gives each branch's standing.
2. Write the solver (`programs/solvers/<task_id>.dl`), and copy the Analyze file to the witness file: `cp work/task/<task_id>/witnesses.json programs/witnesses/<task_id>.wit.json`.
    - Write the header's `@scene` and `@rule` lines from the concept file's claims, and `Params` from its Parameters section, under their names. The `@scene` line written from a claim gives the value of each parameter in its Scene parameters section that the claim reads.
    - A rule that report restates takes the restated text, and the concept file's text stands under it as its `@approximated:` line when the restated text has no relational form.
    - Each branch that report gives a witness, other than one that derives a parameter's value by a built-in derivation or stores a value the program derives, is a constructor, named as the report names it and nested as the report nests its choice point.
        - [Develop](#develop) step 4 gives which such branches you hold.
    - A concept branch's constructor takes a name of your own, and so does the constructor of a branch the report names in a form other than a constructor name, such as `<rel>=derived`. In the witness file, rewrite each name of that branch to that name.
    - An open parameter of that report, unless [Principles](docs/handbook/principles.md) make it a choice point, is a `Params` relation with a fact per open value, and no constructor; its values are the report's where it gives them, whatever the concept file gives.
    - The cases are the combinations of those branches that fit, which the run shows, whether or not one case's model subsumes another's.
    - A line of that report that gives a `<property>` & `<property>` pair gives what each case that takes a non-concept branch at both points of that pair reads, and a `<branch>` & `<branch>` line under it gives what the case that takes both branches reads.
    - Leave the `Determine` comp for the Determine operation.

### Develop
1. Run the solver (`uv run python scripts/run_dl.py <task_id>`).
2. Iterate until it works and passes lint.
    - When a hint appears, judge it, and put that judgment in the review.
    - Flag performance issues in the review.
    - When a performance issue prevents the principled form, make a temporary workaround, marked with the `@workaround` directive.
3. Form each claim under the Analyze report's Not formed as a branch, with each reading of an item that gives several as a claim of its own, and add as cases the combinations that take it and meet Fit and Relational form.
4. Hold as a branch each built-in derivation that fits a parameter, and each stored reading of a derived value, other than one that `store` reports on a single line as having no witness and on which no `@store` line stands.
    - `uv run python scripts/run_dl.py derive <task_id>` lists the built-in derivations that fit.
    - `uv run python scripts/run_dl.py store <task_id>` lists the derived values that are the same on every input.
    - Write the directive line each prints, in the form the [`@derive`](docs/handbook/solver-file.md#params) or [`@store`](docs/handbook/solver-file.md#program) directive gives, with the plausibility and verdict of the witness it records.
    - A non-concept branch whose model is equivalent to that of a `@derive` or `@store` branch loses its constructor and gets no clauses of its own.
5. Run the audit (`uv run python scripts/run_dl.py audit <task_id>`) and resolve the findings.
    - A check the audit skips goes in the review as open.

### Determine
- Run the sweep (`uv run python scripts/run_dl.py sweep <task_id>`), and store a value it reports for a parameter beyond the stored values only where the concept leaves that parameter's value free, as [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) defines an open parameter, unless [Principles](docs/handbook/principles.md) make that parameter a choice point.
- Run the plan (`uv run python scripts/run_dl.py determination-plan <task_id>`).
- When the plan lists actions and a different parameterization would give a simpler or more principled model, change the parameterization, run [Develop](#develop) again over the changed solver, and put the change in the review.
- Otherwise, do the actions the plan lists.
- A derivation the determination repeats from the program moves into `Parse`, as [Parse](docs/handbook/solver-file.md#parse) states.

### Witness
- **Concept and branch claims.**
    - Write the `@witness` lines of the header and the branches, with each plausibility and verdict as the Analyze report gives it, `@relaxed` for the scene claim it breaks, which rules out `ordinary`, and `@reassigned` for each parameter that the assignment it stands at changes.
        * comment: The clause "which rules out `ordinary`" restates the plausibility definition, and a64e4611 Create needed it.
    - A witness of the concept case stands under the branch its verdict denotes, and with verdict `other` under an `@approximated:` line of the rule whose approximation disagrees on it.
    - On a branch's witness with no `@reassigned` line, on which no open values disagree and no approximation disagrees with its rule, an `other` verdict identifies a problem with the concept case, and so does a verdict denoting that branch at `ordinary` plausibility; the concept case is fixed to give the judged output, the verdict becomes `concept`, and the fix goes in the review as a departure.
- **Divergence witness.**
    - Replace each name that has no case of the solver with names for the cases `witness` lists for it, or remove it when `witness` lists none, rewrite a `separates` text that mentions it, and remove a witness that then separates nothing.
    - Rewrite each name and each `assign` in a form the [Witness file](docs/handbook/solver-file.md#witness-file) does not give into one it gives, and remove each witness of a `@derive` or `@store` branch that duplicates the one `derive` or `store` records for that branch.
    - Rewrite the groups of every witness of the witness file: `uv run python scripts/run_dl.py record <task_id> --all`.
    - For a branch added in Develop, build the witness its `@witness` line needs.
    - Judge the plausibility and verdict of a witness you build, and put that judgment in the review.
- A branch dropped under a case condition goes in the review with the condition it fails, and for Relational form with why no set of clauses states its claim.
- For each approximated rule, state in the review why no set of clauses states it.
- When the approximation agrees with the rule on every input the generator produces, replace the rule's text with the approximation's and remove the `@approximated:` line.
- Record each witness you build with `uv run python scripts/run_dl.py record <task_id> <witness id> --separates "<its separates text>"`, with the grid on stdin.
    - For an `other` verdict, take the judged output from `uv run python scripts/run_dl.py grid <task_id>` on a control grid: the witness changed so that the program's output is the concept's reading.
- When the divergence requires a parameter to be reassigned, reassign that parameter with `--assign`.
* comment:
    - The audit runs the same check.
- `uv run python scripts/run_dl.py witness <task_id>` reads the solver against `programs/witnesses/<task_id>.wit.json`, whose shape [Witness file](docs/handbook/solver-file.md#witness-file) gives.
- Run the solver against the Analyze file: `uv run python scripts/run_dl.py witness <task_id> --file work/task/<task_id>/witnesses.json`.
    - A branch whose model's output differs from the one the Analyze file gives the branch is an error in the solver to fix, unless the Analyze file erred; then it goes in the review as a departure, with why.
    - Each other difference the run prints under a witness, and that no step of [Develop](#develop) through [Witness](#witness) requires, goes in the review as one departure.
- Run the audit again when the witness file is complete.
- `witness` without `--file` reports a pair of cases that no witness separates. Resolve it by the first that applies, and put the resolution in the review.
    - A case never reads a `Choice` field: the choice point that field encodes stands under the other branches, and the type is reshaped to put it there.
    - The cases' clauses differ and some input separates them: build the witness that shows it.
    - Otherwise the case fails Equivalence and leaves.
- `witness` without `--file` reports each case that no run shows defined and differing from another case. Resolve it by the first that applies, and put the resolution in the review.
    - Some input, at some assignment of the parameters either case reads, shows the case defined and differing: build the witness that shows it, with `--assign` when it needs one, and the case meets Subsumption and stays.
    - Otherwise the case fails Subsumption and leaves.
    - A case or branch that leaves under Subsumption is not an error of the Analyze report.
- The audit reports each fact a parameter's relation stores whose removal changes no output on any input of the task or of the witness file. Resolve it by the first that applies, and put the resolution in the review.
    - No reader of the concept could take the value the fact stores: the fact leaves that relation.
    - Some input, at some assignment of the other parameters, shows the fact's removal changing the output of a witnessed case: build the witness that shows it, with `--assign` when it needs one.
        * comment: "of a witnessed case" restates the solver file's line that every check runs the witnessed cases alone. The Create pass on ad38a9d0 built witnesses on which each removal changed only a case that is not witnessed, so the audit kept every finding, as ticket 10-88 records.
    - Otherwise the fact stays.

### Simplify
- Express what the code claims with less code.
- The model, its parameterization, and its cases stay as they are.
- Simplify covers code that:
    - Reimplements what the lib provides.
    - Reads as implementation detail with no conceptual meaning.
    - Has repetition where a principled form exists.
    - Has unusual or needless indirection.
- Run `uv run python scripts/run_dl.py deletions <task_id>`.
- Run the solver after simplifying.

### Prune
- The text is the solver's header and comments.
- The reader is a future session that needs to understand the solver and its model hypothesis.
- Cut everything that does not serve that reader, exhaustively, from unnecessary words to irrelevant ideas.
- Judge necessity from the artifact alone, not from the session that built it.
- Prune text copied from prior solvers like new text.
- Keep the prose plain.
- Do not compress it into a telegraphic style.

### Reconcile
- Read the Analyze files `work/task/<task_id>/concept.md`, `analyze.md`, and `witnesses.json`, the latest report, which is the highest-numbered `work/task/<task_id>/refine-<n>.md` when one exists and `create.md` otherwise, the solver, and the witness file.
    * comment:
        - The Analyze files are listed here as well as in Write because the Refine render does not carry Write.
- Run these in this order.
- **Overrides.** An override in your brief decides an item of that report. Apply each override, and quote it in the report where you apply it. Then run again each operation from [Develop](#develop) through [Witness](#witness) that applying the overrides touches.
- **Departures.** Judge each departure and open item of that report, and each `## Fixes elsewhere` item on this task's files in another task's latest report (`grep -l <task_id> work/task/*/create.md work/task/*/refine-*.md`), under the current docs, from the solver, the witness file, and the pairs; an item on an Analyze file is judged as a departure, and a `## Fixes elsewhere` item that holds is applied to the solver or the witness file.
    - Run the solver against the Analyze file, as [Witness](#witness) says.
    - A departure holds when what it rests on is true and each case it adds or keeps meets every case condition, and each case it drops fails one in a `witness --every-case` run with that case restored.
    - Revert a departure that does not hold, make the solver follow the docs on each open item they decide, and run again each operation these changes and each applied fix touch.
- **Checks.** Run the solver (`uv run python scripts/run_dl.py <task_id>`) and the audit (`uv run python scripts/run_dl.py audit <task_id>`), and handle what each reports as the operation from [Develop](#develop) through [Witness](#witness) that it belongs to says.
- An overridden, reverted, or applied item, a `## Fixes elsewhere` item judged in the latest report, or an open item the docs decide, is not formed or judged again.

### Promote
- When the user says `promote` or `migrate` over an entry under `docs/wf-solver/proposals/`.
- Have the `handbook-expanded` agent write the change in your session's own tree, with that tree as the worktree its brief gives and the entry's path in its brief.
- On `promote`, the brief's items move the plain relations or proposal comp into the module under `programs/lib/` whose file doc admits it, and update the solver that introduced the proposal.
- On `migrate`, the brief gives one item for each of the entry's callers, which replaces the hand-written form there with the lib relation the entry became.
    - List in the review the callers the agent reports unfinished.

### Review
- Write the review as the record of the pass.

#### The items
- Include only:
    - A lib operation to promote.
    - A judgment the session made.
    - An issue with a doc or tool that interfered with the pass or cost it effort.
    - An item carried over from an earlier pass's report, marked with the pass it came from.
        - Do not recheck it against the current runner, lib, or docs, unless Reconcile judges it.
    - A fix or a problem in a file the pass does not edit, with the file, the line, and the fix it needs.
