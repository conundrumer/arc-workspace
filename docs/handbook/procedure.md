+ document-size-budget: 30897
* comment: when editing this doc
    - Do not add notices about tooling when it would not change the reader's action or when the tooling already explains itself.

# Procedure
- The operations a pass runs, and what holds for every pass.

## Every pass
- **One operation at a time.** Finish each operation before you start the next.
- **Reading files and outputs.** Read the task with `cat data/tasks/<task_id>.json`, and each other file you need whole, apart from the lines that a command these documents give prints, with no other command piped or chained to the read, and the output of each `uv run python scripts/run_dl.py` command you run whole, piped to no other command.
    + xref: src/cli/main.py:main
    * comment: Passes that cut the `run_dl.py` output with a pipe missed lines they needed and ran the command again: tickets 10-489, 10-523, 10-594, 10-623, 10-637, 10-682, 10-747, 10-748 and 10-749, settled by 10-776.
- **Banned forms.** A claim that needs a form the program bans, where no lib relation states that part of it, has no set of clauses: write no comp for it. Where it is a claim of the concept case, give in the review, as a concept fault, the task, the claim, and the form it needs.
    * comment: The user's ruling, session 19c17548, 2026-10-15T23:34:30Z, on the choice "replaces the protocol with the line that a pass that needs a banned form reports a fault of the concept and writes no comp": "2 but leave proposals alone".
- **Reading `src/`.**
    - Do not read `src/` during a pass.
    - If you do, say why in the review, as a gap in the docs or the runner.
- **Corpus.**
    - Take a draft as no evidence for a claim about the corpus, which `grep -L '^// @draft' programs/solvers/*.dl` lists; `grep -l '^// @keywords:.*<keyword>' $(grep -L '^// @draft' programs/solvers/*.dl)` lists its solvers under a keyword.
        * comment: The Create and Analyze passes of tickets 10-117, 10-123, 10-131, 10-136, 10-138, 10-143, 10-156, 10-157, 10-236, 10-257, 10-260, 10-263, 10-267, 10-268, 10-273, 10-284, 10-290, 10-294, 10-300, 10-48 and 10-89 searched every solver, drafts included, for a precedent, such as task b2862040's pass, which printed the headers of the 83 solvers then under `enclose`, and the Create passes of 10-48 read the drafts 9ddd00f0, 6df30ad6, ad173014 and 2ccd9fef as examples.
        * comment: The user's words, session 0ca52415-5fed-4d06-a903-dc3db1aa6c7d, 2026-10-23T18:09:58Z: "there's a difference between reading and taking \"as evidence\". you can read other solvers but do not use the existence of things in draft solvers to make an argument".
- **Keywords.**
    - If no keyword in [Keywords](docs/handbook/keywords.md) fits, propose one in the review, and add it to the solver's `@keywords:` line.
    - If an existing keyword's gloss should change, propose it in the review.
    - If the solver's `@keywords:` line lists `induce`, judge by [Demonstrated choice](docs/handbook/solver-file.md#demonstrated-choice) whether the task is a nested task, and where it is, give the solver the case that section gives.
        + xref: src/checker/lint/form/header.py:check_demonstrated_choice, docs/handbook/solver-file.md#demonstrated-choice
        * comment: The Create pass on 2ccd9fef took `induce` from its gloss, did not follow the gloss's link to Demonstrated choice, and wrote no catalog case, as change ticket 4-47 records.

## Every session
- **Cleanup.** When the user says `cleanup`, run [Simplify](#simplify), then [Prune](#prune).
    + xref: docs/handbook/procedure.md#simplify, docs/handbook/procedure.md#prune
- **Roles.**
    - Run `uv run python scripts/context.py role <role>`.
        + xref: src/handbook/context.py:role_text
    - Spawn the agent its first line states.
    - The prompt is the rest of its output, followed by the brief.

## Review items
- A pass that asks for a report and no review puts the items the operations route to the review in that report.
- A pass that asks for a review and no report puts the items the messages route to the report in that review.

## Operations

### Analyze
1. Read the task whole with `cat data/tasks/<task_id>.json`, with no other command piped or chained to it; a script you write may load the file.
    * comment:
        - The command and the rule on piping and chaining are here as well as under Every pass because the Analyze render does not include Every pass.
            + xref: docs/handbook/procedure.md#every-pass, prompts/agents/analyze.md
    - A pair's `alt` of kind `rule` is a second candidate, and of kind `tiebreak` a tiebreak.
2. Write the concept to `programs/reports/<task_id>/concept.md`, in this form:
    ```
    # <task_id>

    ## Concept
    - <what the task is an instance of, as one person would say it to another>

    ## Scene
    - `<slug>`: <what every input contains, as the concept interprets it>

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
    - Write it from your interpretation of the pairs alone, before you write any script.
    - Then check that it fits every pair.
        - Where a script of this pass needs what a lib component computes, read the component's interface, then call the component in place of rebuilding it: `lib_components.components` has a function of the same name for each component with no column of a type its caller declares, which runs the component on the rows it is given.
            + xref: src/lib_components/components.py
            - The function takes the component's type arguments, each a `Primitive` from `engine.program` or a `LibType` from `lib_components.components`, the grid size of each key as `sizes`, and the rows of each input relation by that relation's name, with each value of a `Position` or `Offset` column as `(row, column)`, and each other value in its lib form, which for a lib constant is the number its `#define` gives. It returns each output relation, whose `.rows` is its set of rows as tuples, and whose `.map()` and `.map_per_key()` give a relation that is a function of its leading columns as a dict.
                + xref: src/lib_components/components.py
                * comment: Analyze passes passed a cell as `(row, column)` for `Bbox`, offsets as `(dr, -dr, dc, -dc)` for `Components`, and a direction or axis value as `'$T'`, `'T'`, `('T',)` or `'DIR_T'` for `Ray`, `LexOrder` and `Gravity`, and each call failed: tickets 10-503, 10-558, 10-685, 10-941, 10-698 and 10-725.
            - `Components(Primitive.NUMBER, sizes={i: (h, w)}, node=[(i, (r, c)), ...]).label.map_per_key()` gives `{i: {(r, c): id}}` for each key `i`.
                + xref: src/lib_components/components.py
    - A scene claim fixes no task data.
        - A value a scene claim states that is task data is a parameter: name it in the claim, and list it with this task's value, under Parameters when the program reads its value and under Scene parameters otherwise.
3. Only after step 2 is complete, read the next steps: `cat .claude/analyze-next.md`.

### Analyze after the concept
1. Form every other branch.
    - A branch is stated by the slugs of the claims it replaces or adds, its parameters, and the inputs on which it is undefined.
    - A branch is formed whether or not another branch's model subsumes it, and whatever its witnesses' plausibility.
    - A branch that derives a parameter's value, or stores a value the program derives, is stated as that derivation or that stored value, and by the claim it replaces.
        - The `@derive` directive in [Params](docs/handbook/solver-file.md#params) states the values a parameter takes on an input under a `@derive` branch, and where that branch is undefined.
            + xref: docs/handbook/solver-file.md#params
    - Form them from these sources alone: the pairs, the headers of the solvers under `programs/solvers/`, the lib, the proposers, which [Proposers](prompts/agents/analyze-next.md#proposers) lists, probes over the pairs, and variant tasks.
        + xref: prompts/agents/analyze-next.md#proposers
        - `grep -l '^// @keywords:.*<keyword>' programs/solvers/*.dl` lists the solvers under a keyword, and `awk '/^$/{exit} 1' programs/solvers/<id>.dl` prints one solver's header.
        - A probe is a script you write under `work/task/<task_id>/` that runs an interpretation over grids and prints the outputs.
            - A probe whose interpretations are all written in Souffle, and that needs only each interpretation's output grid, can be a Souffle file under `work/task/<task_id>/`, its name starting with the task id, that declares a `Choice` with one constructor per interpretation, `impl_choice` containing each, and `out(p: Position, col: Color, ch: Choice)`. `uv run python scripts/run_dl.py grid <that file> <grid file>` prints each interpretation's output as a grid, one grid for the interpretations that give the same one.
                + xref: src/cli/grid.py:cmd_grid
                - Each interpretation in it instantiates the lib components it uses under instances of its own, and no key of a component instance holds an interpretation or a `Choice`.
            - A probe that needs a component's rows in the script, or would key one instance of a component by interpretation, calls the component through `lib_components.components`, once per interpretation where its inputs differ by interpretation.
                + xref: src/lib_components/components.py
    - Name each branch by a constructor name of its own, in the form [Witness file](docs/handbook/solver-file.md#witness-file) gives. The name says what the branch changes and contains no value of a parameter.
        + xref: docs/handbook/solver-file.md#witness-file
    - A claim considered and not formed as a branch goes under Not formed, with why.
2. Place each choice point at the concept or under a branch, as [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) states. A point whose branches' models differ, in an output or in where they are defined, stands at the concept. A point whose branches give one model under another point's concept branch stands under a branch of that point under which they differ.
    + xref: docs/handbook/principles.md#choice-points-and-open-parameters
    - For each two choice points where neither stands under a branch of the other, judge the model of each case that takes a non-concept branch at both.
        - State in one statement every such pair of points where each of those models applies the two branches' changes together.
        - For each other pair, state those models in one statement for the two points, and state on a line of its own the model of each case that statement does not give.
    - When that model is one branch's model alone, the other point's property does not exist with that branch, and [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) says where the point goes.
        + xref: docs/handbook/principles.md#choice-points-and-open-parameters
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
4. Write each witness step 3 gives to `programs/reports/<task_id>/witnesses.json` in the shape [Witness file](docs/handbook/solver-file.md#witness-file) gives, with an `assign` that reassigns each parameter whose value the assignment step 3 gives it changes, and, in each witness whose verdict is not `other`, each fitting branch in the group of the output the branch's model gives at that witness's assignment.
    + xref: docs/handbook/solver-file.md#witness-file
    * comment: Runs that read this step with no link looked for the witness file's shape in `witness --help` and in other tasks' witness files: tickets 10-354, 10-751 (run a690b8262f699d72a) and 10-771 (run ac50865438dc0b06d).
    * comment: An Analyze pass on a1aa0c1e read this step without the verdict clause and reported that its `other` witness `four-rungs` had no place for its fitting branches (console session `622904c2`, 2026-09-23).
    - `uv run python scripts/run_dl.py witness --file programs/reports/<task_id>/witnesses.json` checks the file's shape.
        + xref: src/cli/audit.py:cmd_witness
5. Write the report to `programs/reports/<task_id>/analyze.md`, in this form:

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
    - none
    ```

### Write
1. Read the Analyze files, one at a time: `programs/reports/<task_id>/concept.md`, `analyze.md`, and `witnesses.json`.
    - The concept file gives the concept case's claims, and `analyze.md` gives each branch's standing.
2. Write the solver (`programs/solvers/<task_id>.dl`), and copy `witnesses.json` to the witness file: `cp programs/reports/<task_id>/witnesses.json programs/witnesses/<task_id>.wit.json`.
    - Write the header's `@scene` and `@rule` lines from the concept file's claims, and `Params` from its Parameters section, under their names. The `@scene` line written from a claim gives the value of each parameter in its Scene parameters section that the claim reads.
    - A rule that `analyze.md` restates takes the restated text, and the concept file's text stands under it as its `@approximated:` line when the restated text has no relational form.
    - Each branch that `analyze.md` gives a witness, other than one that derives a parameter's value by a built-in derivation or, unless it is a lookup table, stores a value the program derives, is a constructor, named as `analyze.md` names it and nested as `analyze.md` nests its choice point.
        * comment: The Create pass on cb2d8a2c, agent a70c0a3f6c3d8b832, read this line as making the `analyze.md` branch `clearance_of=stored`, a table from a wall's mark count to its clearance, a `@store` line. The relation it derived for the table differs between inputs, so its `@store` case failed every pair but one, as ticket 17-80 records.
        - [Develop](#develop) step 4 gives which of the branches the line above leaves out you hold.
            + xref: docs/handbook/procedure.md#develop
    - A concept branch's constructor takes a name of your own, and so does the constructor of a branch `analyze.md` names in a form other than a constructor name, such as `<rel>=derived`. In the witness file, rewrite each name of that branch to that name.
    - An open parameter of `analyze.md`, unless [Principles](docs/handbook/principles.md) make it a choice point, is a `Params` relation with a fact per open value, and no constructor; its values are those of `analyze.md` where it gives them, whatever the concept file gives.
    - The cases are the combinations of those branches that fit, whether or not one case's model subsumes another's, and the run shows which fit, as a combination that does not fit is a witnessed case.
        * comment: The Create pass on b7955b3c read "which the run shows" without that inference: on `PASS (4 witnessed cases)` for a solver of 8 cases, it wrote a scratch script to learn whether the 4 other cases fit, as ticket 10-445 records.
    - A line of `analyze.md` that gives a `<property>` & `<property>` pair gives what each case that takes a non-concept branch at both points of that pair reads, and a `<branch>` & `<branch>` line under it gives what the case that takes both branches reads.
    - Leave the `Determine` comp for the Determine operation.

### Develop
1. Run the solver (`uv run python scripts/run_dl.py <task_id>`).
    + xref: src/cli/check.py:cmd_one
2. Iterate until it works and passes lint.
    - When a hint appears, judge it, and put that judgment in the review.
    - Flag performance issues in the review.
    - When a performance issue prevents the principled form, make a temporary workaround, marked with the `@workaround` directive.
3. Form as a branch each interpretation that an item under Not formed in `analyze.md` gives and that states one model, and add as cases the combinations that take it and meet Fit and Relational form.
    * comment: The Create pass on b9b7f026, agent a439e0b4a10625696, read this step as having it form the item "A rank among several holed rectangles", which names no order, and chose rank by cell count as branches, as ticket 10-507 records.
4. Hold as a branch each of these:
    - A built-in derivation that fits a parameter.
        + xref: src/checker/branches/checks.py:check_two_parameterizations
    - An interpretation that stores a derived value, where a `@store` line stands on that value or `store` prints one to add for it.
    - An interpretation that, unless it is a lookup table, stores a derived value and that `analyze.md` gives a witness, whatever `store` reports.
        * comment: The Create pass on cb2d8a2c, agent a70c0a3f6c3d8b832, read this item as well as the Write step 2 exception as making the `analyze.md` branch `clearance_of=stored`, a table from a wall's mark count to its clearance, a `@store` line, and rewrote it as a constructor after its `@store` case failed, as ticket 17-80 records.
5. Find and write the branches of step 4 with these:
    - `uv run python scripts/run_dl.py derive <task_id>` lists the built-in derivations that fit.
        + xref: src/checker/derive.py:survey_derive
    - `uv run python scripts/run_dl.py store <task_id>` lists the derived values that are the same on every input.
        + xref: src/checker/derived_constant.py:survey_derived_constant, src/checker/store/__init__.py:survey_store
    - Write the directive line each command prints, in the form the [`@derive`](docs/handbook/solver-file.md#params) or [`@store`](docs/handbook/solver-file.md#program) directive gives.
        + xref: docs/handbook/solver-file.md#params, docs/handbook/solver-file.md#program
    - Give each `@derive` or `@store` line the plausibility and verdict of the witness it records.
    - In the witness file, rewrite each name of the branch a `@derive` or `@store` line records to the name [Witness file](docs/handbook/solver-file.md#witness-file) gives that line.
        + xref: docs/handbook/solver-file.md#witness-file
    - A non-concept branch whose model is equivalent to that of a `@derive` or `@store` branch loses its constructor and gets no clauses of its own.
6. Run the audit (`uv run python scripts/run_dl.py audit <task_id>`) and resolve the findings.
    + xref: src/cli/audit.py:cmd_audit
    - A check the audit skips goes in the review as open.

### Determine
- Run the sweep (`uv run python scripts/run_dl.py sweep <task_id>`), and store a value it reports for a parameter beyond the stored values only for an open parameter, as [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) defines one, unless [Principles](docs/handbook/principles.md) make that parameter a choice point.
    + xref: src/checker/render/surveys.py:JUDGE_FREE, src/checker/sweep.py:survey_sweep, docs/handbook/principles.md#choice-points-and-open-parameters
    - Where it reports that a parameter's determination keeps fewer values than those at which the model fits every train pair, and the concept fixes that parameter's value, derive that value in the program, as [Stored or derived](docs/handbook/principles.md#stored-or-derived) gives a derivation.
        + xref: docs/handbook/principles.md#stored-or-derived
- Run the plan (`uv run python scripts/run_dl.py determination-plan <task_id>`).
    + xref: src/checker/determination_plan.py:survey_determination_plan
- When the plan lists actions and a different parameterization would give a simpler or more principled model, change the parameterization, run [Develop](#develop) again over the changed solver, and put the change in the review.
    + xref: docs/handbook/procedure.md#develop
- Otherwise, do the actions the plan lists.
- A derivation the determination repeats from the program moves into `Parse`, as [Parse](docs/handbook/solver-file.md#parse) states.
    + xref: docs/handbook/solver-file.md#parse

### Witness
- **Concept and branch claims.**
    - Write the `@witness` lines of the header and the branches, with each plausibility and verdict as `analyze.md` gives it, `@relaxed` for the scene claim it breaks, which rules out `ordinary`, and `@reassigned` for each parameter that the assignment it stands at changes.
        + xref: src/checker/lint/form/witnesses.py:check_witness, src/checker/witness.py:check_witness_lines, src/solver/annotations.py:WitnessLine
        * comment: The clause "which rules out `ordinary`" restates the plausibility definition, and a64e4611 Create needed it.
            + xref: docs/handbook/principles.md#witnesses
    - A witness of the concept case stands under the branch its verdict denotes, and with verdict `other` under an `@approximated:` line of the rule whose approximation disagrees on it.
        + xref: src/checker/lint/form/witnesses.py:check_witness
    - On a branch's witness with no `@reassigned` line, on which no open values disagree and no approximation disagrees with its rule, an `other` verdict identifies a problem with the concept case, and so does a verdict denoting that branch at `ordinary` plausibility; the concept case is fixed to give the judged output, the verdict becomes `concept`, and the fix goes in the review as a departure.
- **Divergence witness.**
    - Replace each name that has no case of the solver with names for the cases `witness` lists for it, or remove it when `witness` lists none, rewrite a `separates` text that mentions it, and remove a witness that then separates nothing.
    - Rewrite each name and each `assign` in a form the [Witness file](docs/handbook/solver-file.md#witness-file) does not give into one it gives, and remove each witness of a `@derive` or `@store` branch that duplicates the one `derive` or `store` records for that branch.
        + xref: docs/handbook/solver-file.md#witness-file
    - Rewrite the groups of every witness of the witness file: `uv run python scripts/run_dl.py record <task_id> --all`.
        + xref: src/cli/record.py:cmd_record_all
    - For a branch added in Develop, build the witness its `@witness` line needs.
    - Judge the plausibility and verdict of a witness you build, and put that judgment in the review.
- A branch dropped under a case condition goes in the review with the condition it fails, and for Relational form with why its claim has no relational form.
- For each approximated rule, state in the review why it has no relational form.
- When the approximation agrees with the rule on every input the generator produces, replace the rule's text with the approximation's and remove the `@approximated:` line.
- Record each witness you build with `uv run python scripts/run_dl.py record <task_id> <witness id> --separates "<its separates text>"`, with the grid on stdin.
    + xref: src/cli/record.py:cmd_record
    - For an `other` verdict, take the judged output from `uv run python scripts/run_dl.py grid <task_id>` on a control grid: the witness changed so that the program's output is the output the concept's claims give on the witness.
        + xref: src/cli/grid.py:cmd_grid
- When the divergence requires a parameter to be reassigned, reassign that parameter with `--assign`.
    + xref: src/cli/parser.py:parser
* comment:
    - The audit runs the same check.
- `uv run python scripts/run_dl.py witness <task_id>` reads the solver against `programs/witnesses/<task_id>.wit.json`, whose shape [Witness file](docs/handbook/solver-file.md#witness-file) gives.
    + xref: docs/handbook/solver-file.md#witness-file, src/cli/audit.py:cmd_witness
- Run the solver against `witnesses.json`: `uv run python scripts/run_dl.py witness <task_id> --file programs/reports/<task_id>/witnesses.json`.
    + xref: src/checker/witness.py:check_concept_output
    - A branch whose model's output differs from the one `witnesses.json` gives the branch is an error in the solver to fix, unless `witnesses.json` erred; then it goes in the review as a departure, with why.
        + xref: src/checker/witness.py:check_concept_output, docs/handbook/procedure.md#develop, docs/handbook/procedure.md#witness
    - Each other difference the run prints under a witness, and that no step of [Develop](#develop) through [Witness](#witness) requires, goes in the review as one departure.
        + xref: docs/handbook/procedure.md#develop, docs/handbook/procedure.md#witness
- Run the audit again when the witness file is complete.
    + xref: src/cli/audit.py:cmd_audit
- `witness` without `--file` reports a pair of cases that no witness separates. Resolve it by the first that applies, and put the resolution in the review.
    + xref: src/checker/case_conditions.py:check_equivalence
    - A case never reads a `Choice` field: the choice point that field encodes stands under the other branches, and the type is reshaped to put it there.
        + xref: src/checker/lint/form/declared_types.py:check_unread_field
    - The cases' clauses differ and some input separates them: build the witness that shows it.
        + xref: src/checker/witness_try.py:survey_witness_try
    - Otherwise the case fails Equivalence and leaves.
- `witness` without `--file` reports each case that no run shows defined and differing from another case. Resolve it by the first that applies, and put the resolution in the review.
    + xref: src/checker/case_conditions.py:check_subsumption
    - Some input, at some assignment of the parameters either case reads, shows the case defined and differing: build the witness that shows it, with `--assign` when it needs one, and the case meets Subsumption and stays.
    - Otherwise the case fails Subsumption and leaves.
    - A case or branch that leaves under Subsumption is not an error of `analyze.md`.
- The audit reports each fact a parameter's relation stores whose removal changes no output on any input of the task or of the witness file. Resolve it by the first that applies, and put the resolution in the review.
    + xref: src/cli/audit.py:cmd_audit
    - No reader of the concept could take the value the fact stores: the fact leaves that relation.
    - Some input, at some assignment of the other parameters, shows the fact's removal changing the output of a witnessed case: build the witness that shows it, with `--assign` when it needs one.
        * comment: "of a witnessed case" restates the solver file's line that every check runs the witnessed cases alone. The Create pass on ad38a9d0 built witnesses on which each removal changed only a case that is not witnessed, so the audit kept every finding, as ticket 10-88 records.
            + xref: docs/handbook/solver-file.md#cases
    - Otherwise the fact stays.

### Simplify
- Express what the code claims with less code.
    + xref: src/checker/lint/relations.py:check_dead, src/checker/lint/rewrites.py:check_subsumed_atom
- The model, its parameterization, and its cases stay as they are.
- Simplify covers code that:
    - Reimplements what the lib provides.
        + xref: src/checker/lint/comp_idiom.py:check_comp_idiom, src/checker/lint/idioms.py:check_lib_idiom
    - States implementation detail with no conceptual meaning.
    - Has repetition where a principled form exists.
        + xref: src/checker/lint/rewrites.py:check_subsumed_atom
    - Has unusual or needless indirection.
        + xref: src/checker/lint/relations.py:check_alias_inline, src/checker/lint/relations.py:check_negated_use, src/checker/lint/relations.py:check_pass_through, src/checker/lint/relations.py:check_chain_join
- Run `uv run python scripts/run_dl.py deletions <task_id>`.
    + xref: src/checker/deletions.py:survey_deletions
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
- Read the Analyze files `programs/reports/<task_id>/concept.md`, `analyze.md`, and `witnesses.json`, the latest report, which is the highest-numbered `programs/reports/<task_id>/refine-<n>.md` when one exists and `create.md` otherwise, the solver, and the witness file.
    * comment:
        - The Analyze files are listed here as well as in Write because the Refine render does not include Write.
            + xref: docs/handbook/procedure.md#write, prompts/agents/refine.md
- Run these in this order.
- **Overrides.** An override in your brief decides an item of that report. Apply each override, and quote it in the report where you apply it. Then run again each operation from [Develop](#develop) through [Witness](#witness) that applying the overrides touches.
    + xref: docs/handbook/procedure.md#develop, docs/handbook/procedure.md#witness
- **Departures.** Judge each departure and open item of that report, and each `## Fixes elsewhere` item on this task's files in another task's latest report (among the files `grep -l <task_id> programs/reports/*/create.md programs/reports/*/refine-*.md` prints, only the file that is its task's latest report, as the first line defines it), under the current docs, from the solver, the witness file, and the pairs; an item on an Analyze file is judged as a departure, and a `## Fixes elsewhere` item that holds is applied to the solver or the witness file.
    - Run the solver against `witnesses.json`, as [Witness](#witness) says.
        + xref: docs/handbook/procedure.md#witness
    - A departure holds when what it rests on is true and each case it adds or keeps meets every case condition, and each case it drops fails one in a `witness --every-case` run with that case restored. Restore its clauses with it.
        + xref: src/checker/case_conditions.py:check_case_conditions
        * comment: Read as the case put back in `impl_choice` alone, where the solver had no clauses for it, the line had a Refine pass on b25e450b see no finding for a dropped case: ticket 10-280.
    - Revert a departure that does not hold, make the solver follow the docs on each open item they decide, and run again each operation these changes and each applied fix touch.
        + xref: docs/handbook/procedure.md#develop, docs/handbook/procedure.md#witness
- **Checks.** Run the solver (`uv run python scripts/run_dl.py <task_id>`) and the audit (`uv run python scripts/run_dl.py audit <task_id>`), and handle what each reports as the operation from [Develop](#develop) through [Witness](#witness) that it belongs to says.
    + xref: docs/handbook/procedure.md#develop, docs/handbook/procedure.md#witness
- An overridden, reverted, or applied item, a `## Fixes elsewhere` item judged in the latest report, or an open item the docs decide, is not formed or judged again.

### Promote
- When the user says `promote` or `migrate` over an entry under `docs/wf-solver/proposals/`.
- Have the `handbook-expanded` agent write the change in your session's own tree, with that tree as the worktree its brief gives and the entry's path in its brief.
- On `promote`, the brief's items move the entry's plain relations into the module under `programs/lib/` whose file doc admits it, and update the solver that introduced them.
- On `migrate`, the brief gives one item for each of the entry's callers, which replaces the hand-written form there with the lib relation the entry became.
    - List in the review the callers the agent reports unfinished.

### Review
- Write the review as the record of the pass.

#### The items
- Include only:
    - A concept fault.
    - A judgment the session made.
    - An issue with a doc or tool that interfered with the pass or cost it effort.
    - An item kept from an earlier pass's report, marked with the pass it came from.
        - Do not recheck it against the current runner, lib, or docs, unless Reconcile judges it.
    - A fix or a problem in a file the pass does not edit, with the file, the line, and the fix it needs.
