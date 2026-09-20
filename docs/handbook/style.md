* comment: when editing this doc
    - Write in the indicative mood.
    - Use a nested list when each parallel item states a rule a reader can follow or break on its own.
    - Write File structure rules by editing the template, and describe only what the template cannot explain.

# Style
- The form and conventions of solver files.
- Solvers target the latest Souffle.

## Naming

### Identifiers
- Variables use a single letter with an optional digit suffix, or leading-capital snake_case.
- Macros: SCREAMING.
- Types: PascalCase.
- Relations: snake_case.

### Position frames
- A Position is named for its coordinate frame.
- **grid** — task input/output frame: `P_grid`. If input and output both appear in one clause, they are `P_grid_in` and `P_grid_out`.
- **tile** — tile-arrangement frame produced by `divide`. `P_tile`.
- **intile** — within a single tile. `P_intile`.
- **inner** — a region's own frame: `P_inner`.
- A Position takes the bare letter where no other frame shares the clause: `P`, then `Q` for a second position. A digit suffix tells apart two rows of one relation, as in `placed(D, P1, Q1), placed(D, P2, Q2)`, and the atom that binds each variable states the frame in its column names.
- `divide` and `tile_pos` name their formal parameters `p_outer` and `p_inner`. A solver binds them to `P_tile` and `P_intile` at the call site. An axis-only intermediate takes decomposition names such as `P_outer_v` and `P_inner_h`.
- When a decomposition's inner coordinate is also the output cell, the setup decides its name.
- **Fold.** A fold combines the tiles into one output tile. It names the output cell `P_grid_out` in consuming clauses and keeps `P_intile` in production clauses that decompose the input.
- **Select.** A select of one tile names it `P_intile`.
- **Crop.** A crop to a region's box, using `crop`, names it `P_inner`.
- **Overlay.** An overlay names the frame cell that it stacks onto: `P`, or `P_frame` when another frame shares the clause.

### Box readings
- A Box column is read as a cell with the `Position` alias, a translation with the `Offset` alias, or a rectangle, margin, or frame change with bare `Box`. A comment states a bare Box's reading where the name does not.
- A variable is named for its reading: `B` for a box, `V` for an offset, and `P_rel` for a cell read relative to a box. `M` does not name a box.
- "Frame" in a component's name means a frame of cells derived from data, as in `Frame2D`. The coordinate-frame sense is stated in prose and Position variable names.

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
        // @scene <slug>: <replacement claim>
        // @rule <slug>: <replacement claim>
        // @rule <new slug>: <added claim>
        //     @approximated: <the rule the program runs>
        //     @witness <id>: <plausibility> <verdict>
        // @witness <id>: <plausibility> <verdict>
        //     @relaxed <slug of the scene claim this witness breaks>
        //     @reassigned <parameter changed for this witness>
        // @witness <id>: <plausibility> <verdict>
        //     @relaxed <slug of the scene claim this witness breaks>
      | CaseB {}

    .decl out(p: Position, col: Color, ch: Choice)

    .comp Params {
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

    // --- CaseA ---
    out(..., $CaseA()) :- ...

    // --- CaseB ---
    out(..., $CaseB()) :- ...

    .comp Determine { ... }
    ```

### Header
- `@scene` is only included when `@claim` or `@relaxed` names it, the text of a `@rule` or `@approximated:` line depends on it, or a branch replaces it.
- `@scene` and `@rule` are in dependency order.
- A witness under an `@approximated:` line is not `foreign`, and each case that runs the approximation has one on which its output is not the verdict's.
* comment
    - Precise reading: a case's output is not the verdict's when its output on the grid differs from the output the verdict names: the concept case's for `concept`, the output of the case that takes the named branch and the concept branch elsewhere for a branch's name, every case's for `other`, no case's for `any`.
- A family sibling's header, omitting other fields:
    ```
    // <task_id>
    // @draft
    // @representative: <family's first-solved task id> <Case when the sibling has one case of its Choice>
    ```

### Cases
- A solver with one case has no `Choice`, case markers, or case column on `out`.
- **Case markers.** Cases do not interleave: each case's Params and clauses are under its marker. Cases that share facts or clauses are under one marker naming them, `// --- Box, Erode ---`. A marker may fix a constructor's fields, `// --- Derive(g=Iso) ---`, for the part of that case where the field is that branch; the comma still separates cases.
- **Concept branch.** The concept branch is declared first in `Choice`, and in each field's type of a record-typed `Choice`.
- **Choice gloss.** The gloss of the choice is above `.type Choice` and nowhere else.
- **Other branches.** Every other branch has at least one `@witness` line. A witness's nested lines are under the first branch that has it, and a later branch has the `@witness` line alone.
    - A branch nested under a constructor's field states only what differs from the branch it is under.
- **`impl_choice`.** The relation that enumerates the cases is `impl_choice`, and its column is `ch`. A record-typed `Choice` gets one enumerator per field, named for the field's type, as in `.decl locate_choice(l: Locate)`. `impl_choice` contains whole `Choice` values and appears when a clause reads one.

## Params
- Params contains the parameterization and what derives from it. The program reads a parameter as `params.<rel>`.
- `.init helpers = ParamsHelpers` gives the declarations inside Params the shared helpers as `helpers.<rel>`. The program has no access.
- **Empty parameterization.** A task with an empty parameterization keeps the comp empty and the `.init` unchanged: `.comp Params {}`.
- **Shared parameters.**
    - A parameter that every case reads is above the case markers.
    - A parameter that some case never reads goes under the marker of the cases that read it.
- **Derived data.** A clause inside Params writes no value as a literal. A derived relation has no determination relation.
    - **`@singleton-axis` literal.** A structure that extends along one axis is written in a two-axis type, and the other axis takes a literal `1`. The clause containing that literal ends with `// @singleton-axis: <what the structure is>`. The linter flags a program literal regardless of the comment.
- Facts are not column-aligned across a block.
- **Relative orientation.** If the family fixes an orientation value from another value, the stored form is relative: `Sense` via `turn` and `Axis` via `perp`.

## Types
- A solver may define:
    - an ADT in `Choice`, in one of these places:
        - as `Choice` itself
        - as the type of a field in the `Choice` record
        - as the type of a field in a `Choice` constructor
    - `TiebreakResolution` for alt outputs
    - a record used as a type argument of a generic comp
- Any other type is banned.

## Program
- Program style applies to the program clauses and the Determine comp. The single-consumer hint also applies to relations in Params.
- **`@allow` directive.** A relation kept despite the lint's single-consumer hint has `// @allow: single-consumer — <reason>` on the line immediately above its declaration. Put the relation's gloss in a separate comment immediately above the directive. The hint does not fire on the relation.
- **`@workaround` directive.** A temporary workaround is under a `// @workaround: <the principled form it stands in for>` line.
- **`@claim` directive.** At program scope or inside `Parse`, an instance of a component without an `@construction` mark has the directive, one line per instance, naming the claims the instance serves. Each slug names a claim in the solver's header. In a family sibling, that claim belongs to the representative's header.

### Bans
- **Literals.** Literals are banned. The program may read `0` and `ZERO` directly; it reads every other lib constant macro, all colors, and non-zero task-shape lengths, offsets, and gaps from Params.
- **Position destructure.** Destructuring a Position is banned. Lib relations read a Position.
- **Arithmetic.** Arithmetic, raw aggregates, and `range` are banned.
    - **Bound comparisons.** A comparison of a distance against a bound is program style, is not arithmetic, and needs no lib relation.

### Idioms
- **Complement tests.** The test negates the named case: `!params.bg(Col)` for non-bg.
- **Off-edge tests.** The test is `!dist(P, D, 0)`.
- **Narrowing.** When a clause binds an argument of a lib relation to a head column of a narrower type, it takes that type's `*_elem` atom.
- **Aggregators.** Inline relations cannot appear inside aggregators. A non-inline relation wraps one when needed.

### Layout
- Related atoms share a line. If a line's atoms do not already state its role, an inline `// ` comment names that role.
    ```
    header_color(Idx, Col) :-
        in(P, Col),                                       // input cell
        params.header_dir(D), dist(P, D, 0),              // on the header edge
        params.across_dir(A_dir), dist(P, A_dir, Idx).    // index = across distance
    ```
- **Single-line form.** The single-line form is fine for short clauses (≤ ~80 chars).

### Disjunction
- A disjunction is conditional branching inside one derivation: the shared frame stated once, then branches split on a test.
    ```
    render(P, Col) :-
        in(P, _), params.side(K), divide_by_size_2d(P, K, 0, P_tile, _),
        ( tile_ink(P_tile, Col)                 // inked tile: one atom tests, grounding Col
        ; !tile_ink(P_tile, _), params.bg(Col)  // blank tile: the test, then Col
        ).
    ```
- Each branch must ground the head's variables on its own.
- A branch that takes a value that the frame already derives binds it with `=`.
- Clauses that share a head and a frame belong in one clause.
- A clause does not range over choice tags through a disjunction.

## Components
- **Proposal comps.** A comp outside `Params`, `Determine`, and `Parse` is lib code, and a solver writes one only as a proposal comp, per lib-protocol.md. Program-style checks skip proposal comps, and a proposal comp with no entry is flagged.
- **Keys.** Every comp but `Params` and `Determine` takes a `Key` type param.
    - Keyed relations share the key across cases.
    - Single-set sites key on `Unit`.
    - **Shared comp instances.** A comp instance is shared exactly when its case-specific versions differ only in the case name.
        - A comp instance stays per-case when one case derives a value and another reads it from Params, even when one derivation could feed every case.
- **Instance-level inputs.**
    - An input that is the same across cases is part of the instance's identity and takes no key.
    - An input that varies per case is per-key data and keys the comp by `Choice`.
- **Nested comps.** A nested comp's outputs are read through the instance path.

## Parse
- A `.comp Parse<Key>` contains a derivation that the program and the Determine comp share.

## Determination
- `Determine` contains the determination as one relation per determined parameter, with the parameter's name and schema, derived from `ex_in` and `ex_out`.
- A determination relation that mirrors no parameter is a helper and takes no parameter's name.
- When several determined parameters use an Ident for the same entity, their determination relations derive the same id for that entity. The derived id need not equal the stored id.
- **Test inputs.** A clause that keeps the parameter values that no example contradicts ranges over examples with `ex_out` rows.

## Alt outputs
- A task JSON may give a pair alternate outputs in an alt, whose `kind` names how the outputs differ.
- An alt with kind `rule` gives the pair a second candidate.
- An alt with kind `tiebreak` gives resolutions within one candidate. The solver enumerates them through a trailing `out` column of type `TiebreakResolution`.
