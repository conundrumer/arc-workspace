+ index: headings
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

### Box readings
- A Box column is read as a cell with the `Position` alias, a translation with the `Offset` alias, or a rectangle, margin, or frame change with bare `Box`.
- A comment states a bare Box's reading where the name does not.
- A variable is named for its reading: `B` for a box, `V` for an offset, and `P_rel` for a cell read relative to a box.
- A box is not named `M`.
- "Frame" in a component's name means a frame of cells derived from data, as in `Frame2D`.
- The coordinate-frame sense is stated in prose and Position variable names.

## Header
- `@scene` is only included when `@claim` or `@relaxed` denotes it, the text of a `@rule` or `@approximated:` line depends on it, or a branch replaces it.

## Cases
- **Choice gloss.** The gloss of a choice is above its type, and nowhere else.
- **Other branches.** Every other branch has at least one `@witness` line.
- **Concept branch.** The concept branch is declared first in `Choice`, and in each field's type of a record-typed `Choice`.
- **Branch witness lines.** A witness's nested lines are under the first branch that has it, and a later branch has the `@witness` line alone.
    - A branch nested under a constructor's field states only what differs from the branch it is under.

## Params
- **Shared parameters.**
    - A parameter that every case reads is above the case markers.
    - A parameter that some case never reads goes under the marker of the cases that read it.
- **Derived data.** A clause inside Params writes no value as a literal.
- Facts are not column-aligned across a block.
- **Relative orientation.** If the family fixes an orientation value from another value, the stored form is relative: `Sense` via `turn` and `Axis` via `perp`.

## Types
- [Types](docs/handbook/solver-file.md#types) lists the types a solver may define, and any other type is banned.

## Program
- Program style applies to the Determine comp and to the program clauses other than the clauses of `impl_choice`, of the enumerators, and of the relations that only `impl_choice` and the enumerators read.
- The single-consumer hint also applies to relations in Params.
- The gloss of a relation that carries an `@ignore` directive is in a separate comment immediately above that directive.

### Bans
- **Literals.** Literals are banned.
    - The program may read `0` and `ZERO` directly.
    - It reads every other lib constant macro, all colors, and non-zero task-shape lengths, offsets, and gaps from Params.
- **Position destructure.** Destructuring a Position is banned.
    - Lib relations read a Position.
- **Arithmetic.** Arithmetic, raw aggregates, and `range` are banned.
    - **Bound comparisons.** A comparison of a distance against a bound is program style, is not arithmetic, and needs no lib relation.

### Idioms
- **Complement tests.** The test negates the relation of the values it excludes: `!params.bg(Col)` for non-bg.
- **Off-edge tests.** The test is `!dist(P, D, 0)`.
- **Narrowing.** When a clause binds an argument of a lib relation to a head column of a narrower type, it takes that type's `*_elem` atom.

### Layout
- [File structure](docs/handbook/solver-file.md#file-structure) gives the template, and a file takes its block order and layout from it.
- Related atoms share a line.
- If a line's atoms do not already state what it does, an inline `// ` comment states what the line does.
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
- **Proposal comps.** The program-style checks skip a proposal comp.
- A proposal comp with no entry is a hint.
    + deferred
- **Shared comp instances.** A comp instance is shared exactly when its case-specific versions differ only in the case name.
    - A comp instance stays per-case when one case derives a value and another reads it from Params, even when one derivation could feed every case.
