+ index: headings
* comment: when editing this doc
    - Write what File structure says by editing the template, and describe only what the template cannot explain.

# Solver file
- What each part of a solver file means.

## File structure
- A solver is one file, `<task_id>.dl`.
    ```
    // <task_id>
    // @draft
    // @keywords: <keywords from keywords.md>
    // @scene <slug>: <what every input contains, as the concept reads it>
    //  <continuation>
    // @rule <slug>: <what the output takes from the input>
    //     @approximated: <the rule the program runs>
    //     @witness <id>: <plausibility> <verdict>

    // <what the choice is>
    .type Locate =
        // @claim <rule or scene slug>
        BranchA {}
        // @scene <slug>: <what this branch changes in the claim, and where it is undefined>
        // @rule <slug>: <what this branch changes in the claim, and where it is undefined>
        // @rule <new slug>: <added claim, and where it is undefined>
        //     @witness <id>: <plausibility> <verdict>
        // @witness <id>: <plausibility> <verdict>
        //     @relaxed <slug of the scene claim this witness breaks>
        //     @reassigned <parameter changed for this witness>
        // @witness <id>: <plausibility> <verdict>
        //     @relaxed <slug of the scene claim this witness breaks>
      | BranchB {}

    // <what the choice is>
    .type Fill =
        // @claim <rule or scene slug>
        BranchC {}
        // @rule <slug>: <what this branch changes in the claim, and where it is undefined>
        //     @witness <id>: <plausibility> <verdict>
      | BranchD {}

    .type Choice = [l: Locate, f: Fill]

    .decl out(p: Position, col: Color, ch: Choice)

    .comp Params {
        // @derive <Proposer>: <plausibility> <verdict>
        //     @relaxed <slug of the scene claim this witness breaks>
        .decl bg(c: Color) bg(0).
        // <gloss, where the name does not say what it is>
        .decl recolor(c_fg: Color, c_fill: Color)
        recolor(3, 1).
        recolor(5, 4).

        // --- $BranchA ---
        ...

        // --- $BranchB ---
        ...
    }

    .init params = Params

    .decl locate_choice(l: Locate)
    locate_choice($BranchA()). locate_choice($BranchB()).

    .decl fill_choice(f: Fill)
    fill_choice($BranchC()). fill_choice($BranchD()).

    .decl impl_choice(ch: Choice)
    impl_choice([L, F]) :- locate_choice(L), fill_choice(F).

    .comp Parse<Key> { ... }
    .init parse = Parse<Unit>

    // shared program clauses

    // <gloss>
    // @claim <slug> <slug>
    .init shape = Components<Unit>

    // @store: <plausibility> <verdict>
    //     @relaxed <slug of the scene claim this witness breaks>
    .decl band(p: Position)

    // @store box: <plausibility> <verdict>
    .init outline = Outlines<Unit>

    // --- $BranchA ---
    out(..., [$BranchA(), F]) :- impl_choice([$BranchA(), F]), ...

    // --- $BranchB ---
    out(..., [$BranchB(), F]) :- impl_choice([$BranchB(), F]), ...

    .comp Determine { ... }
    ```

### Header
- `@scene` and `@rule` are in dependency order.
- `@keywords` carries the keywords any case claims.
- A `// review <kind>: <text>` line stands last in the header.
- Leave it as it is.
- A family sibling's header, omitting other fields:
    ```
    // <task_id>
    // @draft
    // @representative: <family's first-solved task id> <Case when the sibling has one case of its Choice>
    ```
- A witness under an `@approximated:` line is not `foreign`.
- Each case that runs the approximation has a witness on which its output is not the verdict's.
* comment
    - Precise reading: a case's output is not the verdict's when its output on the grid differs from the output the verdict denotes: the output of the name's model for a name in one of the [Witness file](docs/handbook/solver-file.md#witness-file) forms, every case's for `other`, no case's for `any`.

### Cases
- A case's model reads its output grids from `out` at that case, one grid per tiebreak resolution, and is undefined on an input where it reads no grid, or facts that describe no total grid.
- A case's base is its `Choice` value, its branch at each point the `Choice` encodes; a case is a base with a branch at each `@derive` and `@store` point its base reads.
- A case is witnessed when it is the concept case or stands for a branch's model, or when an input of the task or of the witness file shows it giving an output that no case taking only part of its non-concept branches gives, where undefined counts as an output.
    - The case that stands for a branch's model is that model where the model is a case, and otherwise the case that takes the branch and differs from the concept case at the fewest points.
    - Any other case that takes two branches on which every verdict is `concept` is not witnessed, unless every case that takes one of them also takes the other.
    - On every input of the task and of the witness file, every other case that is not witnessed gives the output of a witnessed case, so a run of the witnessed cases shows each Fit failure it has.
    - Every check, survey and count of `scripts/run_dl.py` runs and reports the witnessed cases alone.
- A branch's clauses are the clauses shared by its cases and absent from the other cases.
- A constructor stands for its branch alone, not for what another branch shares with it, and is named as the Analyze report names the branch.
- `@claim` under the concept branch's constructor denotes the header claim the choice point turns on, which each other branch's `@scene` or `@rule` line changes.
    - A case's reading of a claim is the header's claim with each of its branches' changes made.
- A solver with one case has no `Choice`, case markers, or case column on `out`.
- **Case markers.** Cases do not interleave: each case's Params and clauses are under its marker.
    - Cases that share facts or clauses are under one marker listing names whose cases they are, in the forms the [Witness file](docs/handbook/solver-file.md#witness-file) gives, `// --- $Box, $Erode ---`.
    - The comma separates names.
- **`impl_choice`.** The relation that enumerates the cases is `impl_choice`, and its column is `ch`.
    - A record-typed `Choice` gets one enumerator per field a clause enumerates, named for the field's type.
    - For a record-typed `Choice`, `impl_choice` excludes each combination of the fields that is not a case, and appears when a clause reads it or when the cases are not every combination of the fields.

## Params
- Params contains the parameterization and what derives from it.
- The program reads a parameter as `params.<rel>`.
- `.init helpers = ParamsHelpers` gives the declarations inside Params the shared helpers as `helpers.<rel>`.
    - The program has no access to those helpers.
- A case stores its base's values of each open parameter it stores, and those are that parameter's open values under the case of that base that takes the concept branch at every `@derive` and `@store` point.
    - Of a parameter whose value is a set of rows, a case stores one set.
- **Case column.** Where the cases that read a relation in Params store different values of it, the relation takes a case column in the form of `out`'s, and each fact's case column is the `Choice` value of the case that stores the fact.
    - Each of its facts stands under the marker of the case its case column holds.
- **Empty parameterization.** A task with an empty parameterization keeps the comp empty and the `.init` unchanged: `.comp Params {}`.
- **`@singleton-axis` literal.** A structure that extends along one axis is written in a two-axis type, and the other axis takes a literal `1`.
    - The clause containing that literal ends with `// @singleton-axis: <what the structure is>`.
- **`@derive` directive.** The line is a branch of a choice point on the parameter, at which each case whose base reads the parameter takes a branch and whose concept branch is the stored parameter, with the parameter's value derived by the built-in derivation the line's `<Proposer>` selects; lines on one parameter are branches of one point, and the cases that take one of them are cases of the solver.
    - In a run on an input, a pair's or a witness's, the parameter takes the values the derivation gives on that input alone, with `ex_out` empty; where it gives none, every case that takes the branch is undefined on that input.
    - The verdict `derived` denotes that branch, beside the verdicts a `@witness` line takes, and its witness's id is the branch's name; a further witness of the branch is in the witness file, and the solver has no `@witness` line for it.
    - `// @ignore: derive — <reason>` above the parameter records that every derivation of it fails a case condition, Fit, Equivalence or Subsumption, and no case takes a derived branch of it.
    - `// @ignore: derive <Proposer> — <reason>` above the parameter records the same for the one derivation `<Proposer>` selects.
    - `// @ignore: derive <name> — <reason>` under a `@derive` line records that the cases of `<name>` that take the line's branch fail a case condition, and none of them is a case of the solver.

## Types
- A solver may define:
    - an ADT in `Choice`, in one of these places:
        - as `Choice` itself
        - as the type of a field in the `Choice` record
        - as the type of a field in one or more constructors in `Choice`
    - `TiebreakResolution` for alt outputs
    - `DemonstratedChoice`, per [Demonstrated choice](docs/handbook/solver-file.md#demonstrated-choice)
    - a record used as a type argument of a generic comp

## Program
- **`@ignore` directive.** A relation kept despite a hint has `// @ignore: <category> — <reason>` on the line immediately above its declaration, with the category the hint gives.
    - The hint does not fire on the relation.
    - Above a `.init`, `// @ignore <relation>: <category> — <reason>` dismisses that one relation of the instance, and the bare form dismisses every relation of it.
- **`@store` directive.** The relation, or the instance's relation the line names, has one value on every input, and the line is a branch of a choice point on it, at which each case whose base reads the relation takes a branch and whose concept branch is the derived relation, with the relation's value stored per case; the cases that take that branch are cases of the solver.
    - The verdict `stored` denotes that branch, beside the verdicts a `@witness` line takes, with the branch's witnesses named and placed as a `@derive` branch's are; `// @ignore: store — <reason>` and `// @ignore: store <name> — <reason>` record what the `@ignore: derive` forms record.
- **`@workaround` directive.** A temporary workaround is under a `// @workaround: <the principled form it stands in for>` line.
- **`@claim` directive.** At program scope or inside `Parse`, an instance of a component without an `@construction` mark has the directive, one line per instance, listing the claims the instance serves.
    - Each slug denotes a claim.
    - In a family sibling, that claim belongs to the representative's header.

## Components
- **Keys.** Every comp but `Params` and `Determine` takes a `Key` type param.
    - Keyed relations share the key across cases.
    - Single-set sites key on `Unit`.
- **Instance-level inputs.**
    - An input that is the same across cases is part of the instance's identity and takes no key.
    - An input that varies per case is per-key data and keys the comp by the `Choice` fields it varies with.
- **Nested comps.** A nested comp's outputs are read through the instance path.
- **Proposal comps.** A comp outside `Params`, `Determine`, and `Parse` is lib code, and a solver writes one only as a proposal comp, per [Lib addition protocol](docs/handbook/lib-protocol.md).

## Parse
- A `.comp Parse<Key>` contains a derivation that the program and the Determine comp share.

## Determination
- `Determine` contains the determination as one relation per determined parameter, with the parameter's name and schema, derived from `ex_in` and `ex_out`.
- The determination relation of a parameter with a case column gives the rows of every case.
- A determination relation that mirrors no parameter is a helper and takes no parameter's name.
- A derived relation has no determination relation.
- When several determined parameters use an Ident for the same entity, their determination relations derive the same id for that entity. The derived id need not equal the stored id.
- **Test inputs.** A clause that keeps the parameter values that no example contradicts ranges over examples with `ex_out` rows.

## Alt outputs
- A task JSON may give a pair alternate outputs in an alt, whose `kind` states how the outputs differ.
- An alt with kind `rule` gives the pair a second candidate.
- An alt with kind `tiebreak` gives resolutions within one candidate.
- The solver enumerates a tiebreak's resolutions through a trailing `out` column of type `TiebreakResolution`.
- No parameter stores the resolution values.
- No clause treats one resolution differently from another.

## Demonstrated choice
- `DemonstratedChoice` is the `Demonstrated` type argument of a `DemonstrationConsistency` instance.
- Its constructors name the rules the input may demonstrate.
- The rule that applies to an input is a rule for which the instance's `consistent` relation holds on a demonstrated pair of that input, and no parameter stores it.
- An ADT whose constructors are joined to predictions with no demonstration selecting among them is a disjunction, and is written as one.

## Witness file
- `programs/witnesses/<task_id>.wit.json` holds the witnesses the solver's cases are pinned to.
    ```
    { "id": <task_id>,
      "witnesses": [{
        "id": string,                            // unique within this file
        "separates": string,                     // the feature of the input on which the models differ, and each model's output
        "input": Grid,
        "assign": {<parameter>: Fact[] | Grid | {"grid": Grid, "anchor": [row, col]}},  // the parameters the witness reassigns, which may include a `@store` line's relation
        "output": Group[]                        // when the verdict is not other: one group per distinct output
                | Grid                           // when the verdict is other: the annotator's judged output
      }] }

    Group: { "cases": <name>[],           // the fewest names whose cases together are exactly the cases that give this output; in work/task/<task_id>/witnesses.json, the branches whose models give it
             "grid": Grid | Grid[] | null }  // null for undefined; a list of the grids the cases give, one per tiebreak resolution, when they give more than one
    Grid: number[][]                      // rows of colors
    Fact: Arg[]                           // the arguments of one fact
    Arg: number | string | Arg[]
    ```
- Use a string for a lib constant and a list for a record. Write a constructor with no arguments as a string, such as `"$Anchor"`.
- An `assign` of a relation in [Params](docs/handbook/solver-file.md#params) or of a `@store` line's relation gives its facts without their case part, and every case reads those facts at its own value of the part left out. For a relation in Params, it leaves out the relation's case column. For a `@store` line's relation, it leaves out each column whose type is an ADT in `Choice` or a record built only of such ADTs, and writes a record column that has such fields beside others as the list, in order, of the others. Its key for the relation of a `@store` line above an `.init` is `<instance>.<relation>`.
- [`GRID_HxW` for grid data](docs/handbook/patterns.md#grid_hxw-for-grid-data) states the form of a stored grid.
    - For a parameter that a `GRID_STAMP_HxW` or `GRID_STAMP_SPARSE_HxW` call stores, a grid of the call's size is read as a picture with the `@` on the cell that carries it in the call's layout, and `{"grid": Grid, "anchor": [row, col]}` is read as a picture of any size with the `@` on the cell at that row and column, counted from 0.
- A `<name>` fixes the branch at some choice points, in one of these forms. Its model takes the fixed branches and the concept branch at every other point it takes; its cases are the cases of the solver that take the fixed branches ([Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) states both for one branch). A `@witness` verdict denotes its model; a case marker and an `@ignore: derive` or `@ignore: store` line denote its cases.
    - `concept`: the concept branch at every point the `Choice` encodes, the concept base; alone, its model and its one case are the concept case
    - a constructor's name with its prefix, such as `$Alt`: that branch at each point where the constructor stands, for a nested constructor too, whether or not `impl_choice` contains its model
    - `<name> & <name>`: what each fixes
    - `<param>=<Proposer>`, `<rel>=stored`, `<rel>=derived` and `<param>=stored`, each read as a constructor's name: the branch that the `@derive` line on `<param>` with that `<Proposer>` is; the branch that the `@store` line on `<rel>` is; the branch of `<rel>`'s point in which the solver's clauses derive its value; and the branch of `<param>`'s choice point in which its value is stored per case
        - A `<Proposer>` is a component of [proposers.dl](programs/proposers.dl).
