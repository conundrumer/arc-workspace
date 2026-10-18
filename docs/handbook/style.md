+ index: headings
+ budget: 8200
* comment: when editing this doc
    - Use a nested list when each parallel item states a rule a reader can follow or break on its own.

# Style
- The conventions a solver file follows.
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
- A Position takes the bare letter where no other frame shares the clause: `P`, then `Q` for a second position.
- A digit suffix tells apart two rows of one relation, as in `placed(D, P1, Q1), placed(D, P2, Q2)`.
- The atom that binds each variable states the frame in its column names.
- `divide` and `tile_pos` name their formal parameters `p_outer` and `p_inner`.
- A solver binds them to `P_tile` and `P_intile` at the call site.
- An axis-only intermediate takes decomposition names such as `P_outer_v` and `P_inner_h`.
- When a decomposition's inner coordinate is also the output cell, the setup decides its name.
- **Fold.** A fold combines the tiles into one output tile.
    - It names the output cell `P_grid_out` in consuming clauses, and keeps `P_intile` in production clauses that decompose the input.
- **Select.** A select of one tile names it `P_intile`.
- **Crop.** A crop to a region's box, using `crop`, names it `P_inner`.
- **Overlay.** An overlay names the frame cell that it stacks onto: `P`, or `P_frame` when another frame shares the clause.

### Box roles
- A Box column takes the role of a cell with the `Position` alias, a translation with the `Offset` alias, or a rectangle, margin, or frame change with bare `Box`.
    + xref: src/solver/vocabulary.py:BOX
- A comment states a bare Box's role where the name does not.
- A variable is named for its role: `B` for a box, `V` for an offset, and `P_rel` for a cell relative to a box.
- A box is not named `M`.
- "Frame" in a component's name means a frame of cells derived from data, as in `Frame2D`.
- The coordinate-frame sense is stated in prose and Position variable names.

## Header
- `@scene` is only included when `@claim` or `@relaxed` denotes it, the text of a `@rule` or `@approximated:` line depends on it, or a branch replaces it.
    + xref: src/checker/lint/form/header.py:check_header

## Cases
- **Choice gloss.** The gloss of a choice is above its type, and nowhere else.
    + xref: src/checker/lint/form/case_type.py:check_gloss
- **Other branches.** Every other branch has at least one `@witness` line.
    + xref: src/checker/witness.py:check_branches_witnessed
- **Concept branch.** The concept branch is declared first in `Choice`, and in each field's type of a record-typed `Choice`.
    + xref: src/checker/lint/form/case_type.py:check_family_case, src/checker/lint/form/declared_types.py:check_unread_field
- **Branch witness lines.** A witness's nested lines are under the first branch that has it, and a later branch has the `@witness` line alone, with the plausibility and verdict of the witness's first `@witness` line.
    * comment: The rewording: ticket 9-892, the misread: the solvers of b190f7f5, b4a43f3b and c8b7cc0f each gave one witness one verdict under its first branch and another under a later one, and the coordinator, session 129de8fc, 2026-10-17T19:47:45Z, read this line as allowing it: "the rule I cited is about where a witness's nested lines stand, not about verdicts".
    - A branch nested under a constructor's field states only what differs from the branch it is under.

## Params
- **Shared parameters.**
    - A parameter that every case reads is declared above the case markers, and so are its facts when it has no case column.
    - A parameter that some case never reads goes under the marker of the cases that read it.
        + xref: src/solver/model.py:Unmarked, src/checker/lint/form/case_type.py:check_case_marker, src/checker/lint/form/sections.py:check_case_section, src/checker/lint/form/sections.py:check_case_section_read
- **Derived data.** A clause inside Params writes no value as a literal.
    + xref: src/checker/lint/bans.py:check_params_data
- Facts are not column-aligned across a block.
- **Relative orientation.** An orientation value that the family fixes from another value has no parameter of its own, and is derived from that value: a `Dir` through `turn`, with the `Sense` stored where the family varies it, and an `Axis` through `perp`.

## Types
- [Types](docs/handbook/solver-file.md#types) lists the types a solver may define, and any other type is banned.
    + xref: src/checker/lint/form/declared_types.py:check_banned_type, docs/handbook/solver-file.md#types

## Program
- Program style applies to the Determine comp and to the program clauses other than the clauses of `impl_choice`, of the enumerators, and of the relations that only `impl_choice` and the enumerators read.
- The single-consumer hint also applies to relations in Params.
    + xref: src/checker/lint/relations.py:check_single_consumer
- The gloss of a relation that has an `@ignore` directive is in a separate comment immediately above its `@ignore` lines.
    + xref: src/checker/lint/__init__.py:check_lint

### Bans
- **Literals.** Literals are banned.
    + xref: src/checker/lint/bans.py:check_orientation_literal, src/checker/lint/bans.py:check_nonzero_literal
    - The program may read `0` and `ZERO` directly.
        + xref: src/checker/lint/bans.py:check_nonzero_literal
    - It may write `nil` in an `OpenValue` field or a `DemonstratedRule` column.
    - It reads every other lib constant macro, all colors, and non-zero task-shape lengths, offsets, and gaps from Params.
        + xref: src/checker/lint/bans.py:check_orientation_literal
- **Position destructure.** Destructuring a Position is banned.
    - Lib relations read a Position.
- **Arithmetic.** Arithmetic, raw aggregates, and `range` are banned.
    + xref: src/checker/lint/bans.py:check_arithmetic, src/checker/lint/bans.py:check_range, src/checker/lint/bans.py:check_raw_aggregate, src/checker/lint/rewrites.py:check_argmax
    - **Bound comparisons.** A comparison of a distance against a bound is program style, is not arithmetic, and needs no lib relation.
- **`ord` and `as`.** `ord` and the `as` cast are banned.
    + xref: src/checker/lint/bans.py:check_ord
    - The lib comp `IdentOf` gives a value its `Ident`.
        + xref: src/checker/lint/bans.py:check_ord
- **Recursion.** Recursion is banned in every clause of the solver: a clause reads no relation of its own stratum.
    + xref: src/checker/lint/recursion.py:check_recursion
    - A closure is an instance of a lib construction.
        + xref: src/checker/lint/recursion.py:check_recursion
    - A clause that defines the `step`, `skip` or `take` input of a `Take` instance may read that instance's relations through an atom whose every variable another atom of the clause grounds.
        + xref: src/checker/lint/recursion.py:check_recursion

### Idioms
- **Complement tests.** The test negates the relation of the values it excludes: `!params.bg(Col)` for non-bg.
    + xref: src/checker/lint/rewrites.py:check_named_complement, src/checker/lint/rewrites.py:check_negated_value
- **Off-edge tests.** The test is `!dist(P, D, 0)`.
- **Narrowing.** When a clause binds an argument of a lib relation to a head column of a narrower type, it takes that type's `*_elem` atom.
    + xref: src/checker/lint/idioms.py:check_domain_enumerator

### Layout
- [File structure](docs/handbook/solver-file.md#file-structure) gives the template, and a file takes its block order and layout from it.
    + xref: src/checker/lint/style.py:check_decl_placement, docs/handbook/solver-file.md#file-structure
- Related atoms share a line.
- If a line's atoms do not already state what it does, an inline `// ` comment states what the line does.
    ```
    header_color(Idx, Col) :-
        in(P, Col),                                       // input cell
        params.header_dir(D), dist(P, D, 0),              // on the header edge
        params.across_dir(A_dir), dist(P, A_dir, Idx).    // index = across distance
    ```
- **Single-line form.** The single-line form is fine for short clauses (≤ ~80 chars).
    + xref: src/checker/lint/bans.py:check_long_clause

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
    + xref: src/checker/lint/rewrites.py:check_choice_tag, src/checker/lint/subexpr.py:check_common_subexpr
- A clause does not range over choice tags through a disjunction.
    + xref: src/checker/lint/rewrites.py:check_cross_choice

## Components
- **Shared comp instances.** A comp instance is shared exactly when its case-specific versions differ only in the case name.
    + xref: src/checker/lint/form/components.py:check_parse_unshared_with_determine
    - A comp instance stays per-case when one case derives a value and another reads it from Params, even when one derivation could feed every case.
