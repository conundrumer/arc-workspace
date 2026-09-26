+ index: headings
* comment: when editing this doc
    - Write in the indicative mood.
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
    .type Choice =
        // @claim <rule or scene slug>
        CaseA {}
        // @scene <slug>: <what this branch changes in the claim, and where it is undefined>
        // @rule <slug>: <what this branch changes in the claim, and where it is undefined>
        // @rule <new slug>: <added claim, and where it is undefined>
        //     @witness <id>: <plausibility> <verdict>
        // @witness <id>: <plausibility> <verdict>
        //     @relaxed <slug of the scene claim this witness breaks>
        //     @reassigned <parameter changed for this witness>
        // @witness <id>: <plausibility> <verdict>
        //     @relaxed <slug of the scene claim this witness breaks>
      | CaseB {}

    .decl out(p: Position, col: Color, ch: Choice)

    .comp Params {
        // @derive <Proposer>: <plausibility> <verdict>
        //     @relaxed <slug of the scene claim this witness breaks>
        .decl bg(c: Color) bg(0).
        // <gloss, where the name does not say what it is>
        .decl recolor(c_fg: Color, c_fill: Color)
        recolor(3, 1).
        recolor(5, 4).

        // --- CaseA ---
        ...

        // --- CaseB ---
        ...
    }

    .init params = Params

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

    // --- CaseA ---
    out(..., $CaseA()) :- ...

    // --- CaseB ---
    out(..., $CaseB()) :- ...

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
    - Precise reading: a case's output is not the verdict's when its output on the grid differs from the output the verdict denotes: the concept case's for `concept`, the output of the case that takes the verdict's branch and the concept branch elsewhere for a branch's name, every case's for `other`, no case's for `any`.

### Cases
- A case's model reads its output grids from `out` at that case, one grid per tiebreak resolution, and is undefined on an input where a grid's facts give two frame sizes.
- A branch's clauses are the clauses shared by its cases and absent from the other cases.
- A constructor denotes only its branch's reading, not a reading another branch shares, and is named for its branch, the branch's slug in CamelCase: `bbox-region` gives `BboxRegion`.
- `@claim` under the concept branch's constructor denotes the header claim the choice point turns on, which each other branch's `@scene` or `@rule` line changes.
    - A case's reading of a claim is the header's claim with each of its branches' changes made.
- A solver with one case has no `Choice`, case markers, or case column on `out`.
- **Case markers.** Cases do not interleave: each case's Params and clauses are under its marker.
    - Cases that share facts or clauses are under one marker listing their names in the forms the [Witness file](docs/handbook/solver-file.md#witness-file) gives, `// --- Box, Erode ---`.
    - A marker may fix a constructor's fields, `// --- Derive(g=Iso) ---`, for the part of that case where the field is that branch.
    - The comma still separates cases.
- **`impl_choice`.** The relation that enumerates the cases is `impl_choice`, and its column is `ch`.
    - A record-typed `Choice` gets one enumerator per field a clause enumerates, named for the field's type, as in `.decl locate_choice(l: Locate)`.
    - `impl_choice` contains whole `Choice` values, for a record, as a clause over the enumerators that excludes each combination that is not a case, and it appears when a clause reads one or when the cases are not every combination of the fields.

## Params
- Params contains the parameterization and what derives from it.
- The program reads a parameter as `params.<rel>`.
- `.init helpers = ParamsHelpers` gives the declarations inside Params the shared helpers as `helpers.<rel>`.
    - The program has no access to those helpers.
- **Empty parameterization.** A task with an empty parameterization keeps the comp empty and the `.init` unchanged: `.comp Params {}`.
- **`@singleton-axis` literal.** A structure that extends along one axis is written in a two-axis type, and the other axis takes a literal `1`.
    - The clause containing that literal ends with `// @singleton-axis: <what the structure is>`.
- **`@derive` directive.** The line is a branch of a choice point on the parameter, which stands under the branches that read it, with the parameter's value derived by the built-in derivation the line's `<Proposer>` selects; lines on one parameter are branches of one point, and the runner holds the cases that take one of them.
    - The verdict `derived` denotes that branch, beside the verdicts a `@witness` line takes, and its witness's id is the branch's name; a further witness of the branch is in the witness file, and the solver has no `@witness` line for it.
    - `// @ignore: derive — <reason>` in its place records that the branch failed Equivalence or Subsumption, and the runner then holds no case that takes it; `// @ignore: derive <name> — <reason>` under the `@derive` line records that for each case that takes the branch and every branch whose name `<name>` contains.

## Types
- A solver may define:
    - an ADT in `Choice`, in one of these places:
        - as `Choice` itself
        - as the type of a field in the `Choice` record
        - as the type of a field in one or more constructors in `Choice`
    - `TiebreakResolution` for alt outputs
    - a record used as a type argument of a generic comp

## Program
- **`@ignore` directive.** A relation kept despite a finding has `// @ignore: <category> — <reason>` on the line immediately above its declaration, with the category the finding gives.
    - The finding does not fire on the relation.
    - Above a `.init`, `// @ignore <relation>: <category> — <reason>` dismisses that one relation of the instance, and the bare form dismisses every relation of it.
- **`@store` directive.** The relation, or the instance's relation the line names, has one value on every input, and the line is a branch of a choice point on it, which stands under the branches that read it, with the relation's value stored per case; the runner holds the cases that take that branch.
    - The verdict `stored` denotes that branch, beside the verdicts a `@witness` line takes, with the branch's witnesses named and placed as a `@derive` branch's are; `// @ignore: store — <reason>` and `// @ignore: store <name> — <reason>` record what the `@ignore: derive` forms record.
- **`@workaround` directive.** A temporary workaround is under a `// @workaround: <the principled form it stands in for>` line.
- **`@claim` directive.** At program scope or inside `Parse`, an instance of a component without an `@construction` mark has the directive, one line per instance, listing the claims the instance serves.
    - Each slug denotes a claim in the solver's header.
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

## Witness file
- `programs/witnesses/<task_id>.wit.json` holds the witnesses the solver's cases are pinned to.
    ```
    { "id": <task_id>,
      "witnesses": [{
        "id": string,                            // unique within this file
        "separates": string,                     // models separated by this input
        "input": Grid,
        "assign": {<parameter>: Fact[] | Grid},  // the parameters the witness reassigns
        "output": Group[]                        // when the verdict is not other: one group per distinct output
                | Grid                           // when the verdict is other: the annotator's judged output
      }] }

    Group: { "cases": <name>[],           // the solver's cases that give this output
             "grid": Grid | null }        // null for undefined
    Grid: number[][]                      // rows of colors
    Fact: Arg[]                           // the arguments of one fact
    Arg: number | string | Arg[]
    ```
- Use a string for a lib constant and a list for a record.
- [`GRID_HxW` for grid data](docs/handbook/patterns.md#grid_hxw-for-grid-data) states the form of a stored grid.
- A `<name>` denotes one model, in one of these forms:
    - `concept`: the concept case
    - a constructor's name, such as `Alt`: that branch's model, for a nested constructor too, whether or not `impl_choice` contains its case
        - A constructor that stands at more than one place denotes its first, and `<parent> & <name>` denotes it at another.
    - a branch's slug, such as `bbox-region`: the constructor named for it, as [Cases](docs/handbook/solver-file.md#cases) states
    - `<name> & <name>`: the case with those branches
    - `<param>=<Proposer>`, `<rel>=stored` and `<param>=stored`, each read as a constructor's name: the branch that the `@derive` line on `<param>` with that `<Proposer>` is; the branch that the `@store` line on `<rel>` is; and the branch of `<param>`'s choice point in which its value is stored per case
