<!-- When editing this doc:
- Write in the indicative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed. -->

# Style

The form and conventions of solver files.

Solvers target the latest Souffle.

## Naming

### Identifiers

- Variables: a single letter with an optional digit suffix, or leading-capital snake_case.
- Macros: SCREAMING.
- Types: PascalCase.
- Relations: snake_case.

### Position frames

A Position is named for its coordinate frame.

- **grid** — task input/output frame: `P_grid`. If input and output both appear in one rule, `P_grid_in` and `P_grid_out`.
- **tile** — tile-arrangement frame produced by `divide`. `P_tile`.
- **intile** — within a single tile. `P_intile`.
- **inner** — a region's own frame: `P_inner`.

`divide` and `tile_pos` name their formal parameters `p_outer` / `p_inner`. A solver binds them to `P_tile` / `P_intile` at the call site. An axis-only intermediate takes decomposition language: `P_outer_v`, `P_inner_h`.

When a decomposition's inner coordinate is also the output cell, the setup decides its name.

- **Decompose-fold.** A decompose-fold names the output cell `P_grid_out` in the consuming rules, and keeps `P_intile` in the production rules that decompose the input.
- **Select or crop.** A select or crop names it `P_intile`: the cell is the extracted tile's interior.
- **Overlay.** An overlay names the frame cell that it stacks onto: bare `P`, or `P_frame` when another frame shares the rule.

## File structure

A solver is one file, `<task_id>.dl`.

```
// <task_id>
// concept: <keywords>
// shape: <keywords>
// Doc header — describe task and name cases.

#include "../lib.dl"

.type Choice = CaseA {} | CaseB {}

.comp Params {
    // --- shared ---
    .decl bg(c: Color) bg(0).
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

// shared program rules

.decl out(p: Position, col: Color, c: Choice)

// --- CaseA ---
out(..., $CaseA()) :- ...

// --- CaseB ---
out(..., $CaseB()) :- ...

.comp Determine { ... }
```

- `// concept:` carries the Setup and Prior keywords that some case of the file claims, and `// shape:` the Shape keywords, from `keywords.md`, separated by spaces.
- `// concept:` marks a family representative. A family sibling has `// family: <task_id>` in its place. That line points at the representative, the family's first-solved member. The sibling's header keeps only task-specific content.
- `// shape:` appears when a shape applies. The Parse comp and the Determine comp appear when there is one.

### Cases

A solver with one case has no `Choice`: no type, no case markers, no column on `out`.

- **Case markers.** Cases do not interleave: each case's Params and rules sit under its marker. Cases that share facts or rules sit under one marker naming them, `// --- Box, Erode ---`.
- **`impl_choice`.** The relation that enumerates the cases is `impl_choice`, its column `ch`, corpus-wide. A record-typed `Choice` gets one enumerator per field, named for the field's type (`.decl locate_choice(l: Locate)`). `impl_choice` holds whole `Choice` values, and appears when a rule reads one.

## Params

Params holds the parameterization and what derives from it. Each parameter is a relation, and its facts are its value. The program reads a parameter as `params.<rel>`.

- `.init helpers = ParamsHelpers` inside Params gives data declarations the shared helpers as `helpers.<rel>`. The program has no access.
- A task with an empty parameterization keeps the comp empty and the `.init` unchanged.
    - Write it as `.comp Params {}`.
- **Shared parameters.** Every case reads a parameter under the `shared` marker. A parameter one case never reads sits under that case's marker.
- **Derived data.** A rule inside Params derives a relation from parameters, and writes no value as a literal. The derived relation is not a parameter, and carries no determination relation.
    - **`@unit` literal.** A literal 1 stating a unit (a single row, one cell wide) stays in the rule, under an `// @unit: <what the 1 states>` comment on the rule's line. The linter flags a program literal regardless of `@unit`.
- Facts are not column-aligned across a block.
- **Redundant values.** If another parameter fixes a value, a Params rule derives that value from the parameter instead of storing it. If the family fixes an orientation value from another value, the stored form is relative (`Sense` via `turn`, `Axis` via `perp`).

## Types

A solver defines only these types:

- ADTs inside `Choice`: the type itself, a field of its record, or a field of one of its constructors.
- `TiebreakResolution` for alt outputs.
- Records that fill a generic comp's type params.

Any other type is banned.

## Program

Program style and the linter apply to the program rules, the Determine comp, and the Parse comp.

### Bans

- **Literals.** Literals outside proposal comps are banned. The program reads these from Params:
    - orientation: every lib constant macro but `ORIGIN`
    - colors
    - non-zero task-shape numbers: lengths, offsets, gaps
- **Position destructure.** Position destructure is banned. Lib primitives read Position.
- **Arithmetic.** Arithmetic, raw aggregates, and `range` are banned.
    - **Bound comparisons.** A comparison of a distance against a bound is program style, not arithmetic, and needs no primitive.

### Idioms

- **Complement tests.** Complement tests negate the named case: `!params.bg(Col)` for non-bg.
- **Off-edge tests.** An off-edge test is `dist(P, D, K), K != 0`, not `K > 0`. `!dist(P, D, 0)` is unavailable: Souffle cannot negate an inline relation whose clause introduces variables.
- **Narrowing.** When a rule binds an argument of a lib primitive to a head column of a narrower type, it takes that type's `*_elem` atom.
- **Aggregators.** Inline relations cannot appear inside aggregators. A non-inline relation wraps one when needed.

### Layout

Related atoms share a line. If a line's atoms do not already state its role, an inline `// ` comment names that role.

```
header_color(Idx, Col) :-
    in(P, Col),                                       // input cell
    params.header_dir(D), dist(P, D, 0),              // on the header edge
    params.across_dir(A_dir), dist(P, A_dir, Idx).    // index = across distance
```

**Single-line form.** The single-line form is fine for short rules (≤ ~80 chars).

### Disjunction

A disjunction is conditional branching inside one derivation: the shared frame stated once, then branches split on a test.

```
render(P, Col) :-
    in(P, _), params.side(K), divide_by_size_2d(P, K, 0, P_tile, _),
    ( tile_ink(P_tile, Col)                 // inked tile: one atom tests and grounds Col
    ; !tile_ink(P_tile, _), params.bg(Col)  // blank tile: the test, then Col
    ).
```

- Each branch must ground the head's variables on its own.
- A branch that takes a value that the frame already derives binds it with `=`.
- Rules that share a head and a frame belong in one rule.
- A rule does not range over choice tags through a disjunction.

## Components

- **Proposal comps.** A comp outside `Params`, `Determine`, and `Parse` is lib code. A solver writes one only as a proposal comp, which has an entry under `docs/wf-solver/proposals/` per the lib addition protocol. The linter skips every comp but `Determine` and `Parse`, and flags a proposal comp with no entry.
- **Keys.** A comp other than `Params` and `Determine` takes a `Key` type param, and keyed relations share it across cases. Single-set sites key on `Unit`.
    - **Shared stages.** A stage is shared when, and only when, its case-specific versions differ in nothing but the case name. If cases differ in substance (one derives a value, one reads it from Params), that stage stays per-case, even when one derivation could feed every case.
- **Instance-level inputs.** An input that is the same across cases is part of the instance's identity, and takes no key. An input that varies per case is per-key data, and the comp is keyed by `Choice`.
- **Nested comps.** A nested comp's outputs are read through the instance path.

## Parse

A `.comp Parse<Key>` contains a derivation that the program and the Determine comp share.

## Determination

`Determine` holds the determination: one relation per determined parameter, with the parameter's name and schema, derived from `ex_in` / `ex_out`.

- Determination relations that mirror no parameter are helpers. The runner pairs determination relations to parameters by name, so a helper must not take a parameter's name.
- Derived ids need only be stable across the solver's Ident parameters, not equal to the stored ones.
- **Test inputs.** A rule that keeps the candidates that no example contradicts ranges over examples with `ex_out` rows.

## Alt outputs

Alts in the task JSON are encoded by kind:

- A `rule` alt is a peer model: a case of `Choice`, one case per alt output.
- A `tiebreak` alt marks interchangeable content that the task leaves free.
    - The solver enumerates the resolutions: `out` takes a trailing column typed `TiebreakResolution`, one value per valid resolution.
    - No data or rules name or steer the resolution values, and case coverage does not apply to the resolution column.
