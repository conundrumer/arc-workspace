# Style

The form and conventions of solver files, and the constraints and limitations of the tooling.

`programs/lib.dl` defines shared types and primitives.

## Variables

- Single letter (with optional digit suffix): `P`, `T`, `B`, `L`, `R`, `K`, `D`, `A`, `N`, `G`, `H`, `W`, `T1`, `C2`, etc.
- Multi-character: leading-capital snake_case. `Col`, `Idx`, `Sh`, `K_cyc`, `P_grid_in`.
- Macros: SCREAMING (constants register). `DIR_T`, `D4_ID`, `ORIGIN`.
- Types: PascalCase. `Position`, `Color`, `Choice`.
- Relations: snake_case. `tile_pos`, `axis_of`.

## Position frames

Most rule bodies hold Positions in multiple frames at once. A Position is named for its coordinate frame.

- **grid** — task input/output frame: `P_grid`. If input and output both appear in one rule, `P_grid_in` and `P_grid_out`.
- **tile** — tile-arrangement frame produced by `divide`. `P_tile`.
- **intile** — within a single tile. `P_intile`.

Formal parameters of `divide` and `tile_pos` are `p_outer` / `p_inner`. They describe the decomposition. Solvers bind to `P_tile` / `P_intile` at call sites. An axis-only intermediate takes decomposition language: `P_inner_axis`, `P_outer_v`, `P_inner_h` (e.g. `divide`'s inner before composing with the perpendicular axis).

When a decomposition's inner coordinate is also the output cell, the setup names it. A decompose-fold names the output cell `P_grid_out` in the consuming rules, and keeps `P_intile` in the production rules that decompose the input. A select or crop names it `P_intile`: the cell is the extracted tile's interior. An overlay names the frame cell that it stacks onto: bare `P`, or `P_frame` when another frame shares the rule.

## File structure

One file per task (`<task_id>.dl`). Multi-impl cases go in that same file, distinguished by an ADT `Choice` column on `out`. The header lines are consecutive at the top of the file. The file has these parts in order:

1. `// <task_id>`
2. Exactly one of:
    - `// concept: <terms>` — family representative. Terms from `concepts.md`, separated by spaces, the union over cases: every term whose claim some case makes.
    - `// family: <task_id>` — family sibling: same body and Fit comp, fills may differ. Points at the representative, the family's first-solved member. A sibling's header keeps only task-specific content.
3. `// shape: <terms>`, when one applies — task shape terms from `shapes.md`.
4. `#include "../lib.dl"`
5. `.comp Consts { ... }`, which declares task-wide data, then `.init c = Consts`, which exposes it as `c.<rel>`.
6. The Parse comp, when there is one.
7. The body rules, ending with `out`.
8. The Fit comp, when there is one.

Consts:

- Inside Consts, `.init helpers = ConstsHelpers` makes shared helpers (`frame_pos`, `tile_pos`) available as `helpers.<rel>(...)` in data declarations. The body has no access.
- Consts holds all task-wide data: orientation (Dirs, Axes), dimensions, gaps, mappings, frame data.
- A task with no task-wide data keeps the comp empty (`.comp Consts {}`), the `.init` unchanged.
- A rule inside Consts derives from fact slots. It does not write a datum as a literal. A literal 1 stating a unit (a single row, one cell wide) stays in the rule, under an `// @unit: <what the 1 states>` comment on the rule's line. This exception applies only inside Consts: the linter flags a body literal regardless of `@unit`. A derived relation carries no Fit relation.
- A single-fact data declaration puts the fact on the decl line, one space after it. A multi-fact declaration puts the facts on the next line at the decl's indent. Facts are not column-aligned across a block.
- If another slot fixes a datum, a Consts rule derives that datum from the slot instead of storing it (a stored Position fixes its frame's extents, read with `axis_dim`). If the family fixes an orientation datum from another datum, the stored form is relative (`Sense` via `turn`, `Axis` via `perp`).

Skeleton (single-impl):

```
// <task_id>
// Doc header — describe task.

#include "../lib.dl"

.comp Consts {
    // task-wide data declarations and facts
}

.init c = Consts

// body rules

.decl out(p: Position, col: Color)
out(...) :- ...
```

Skeleton (multi-impl):

```
// Doc header — describe task and name cases.

#include "../lib.dl"

.type Choice = CaseA {} | CaseB {}

.comp Consts {
    // --- shared ---
    ...

    // --- CaseA ---
    ...

    // --- CaseB ---
    ...
}

.init c = Consts

// shared body rules

.decl out(p: Position, col: Color, c: Choice)

// --- CaseA ---
out(..., $CaseA()) :- ...

// --- CaseB ---
out(..., $CaseB()) :- ...
```

Cases are grouped under `// --- <name> ---` markers in both Consts and body, with no interleaving across cases.

## Types

A solver defines only these types: ADTs inside `Choice` (the type itself, a factor, or a constructor field), and records that fill a generic comp's type params. Any other type is banned.

## Body

- Literals are banned: orientation (every lib constant macro but `ORIGIN`), colors, or non-zero task-shape numbers (lengths, offsets, gaps). The body reads them from Consts via `c.<rel>(...)` and uses them as parameters.
    - Literals are fine inside a proposal comp only. A proposal comp is lib code associated with an entry in `docs/wf-solver/proposals/`. The linter skips every comp except `Fit` and `Parse`. It flags a comp with no entry.
- Position destructure is banned. Position is opaque. Lib primitives read it.
- Arithmetic and raw aggregates are banned.
- `range` is banned. It generates a number sequence. The body reads positions and extents through lib primitives.
- Complement tests negate the named case: `!c.bg(Col)` for non-bg.
- An off-edge test is `dist(P, D, K), K != 0`, not `K > 0`: the zero case is excluded by identity, not by order. `!dist(P, D, 0)` is unavailable: Souffle cannot negate an inline relation whose clause introduces variables.
- When a rule binds a union-typed lib parameter (`Axis4`, `Dir8`, `D4` over `C4`) to a narrower head column, it takes the member's `*_elem` atom (`axis_elem(A), same_line(A, P, Q)`).
- A comparison of a distance against a bound is body form, not arithmetic: `dist(P, D, K), K < N` states the cells within N of edge D, and needs no primitive.
- Inline relations cannot appear inside aggregators. A non-inline relation wraps one when needed.

## Components

- A comp outside `Consts`, `Fit`, and `Parse` is lib code: a solver writes one only as a proposal comp (lib-protocol.md). Keyed relations share it across cases. A lib or proposal comp takes a `Key` type param. Single-set sites key on `Unit` (`$U()`, in lib). If a solver's cases share its pipeline, an unkeyed comp forces duplication at the case boundary: per-case `.init`s and dispatch rules that differ only in the case name.
    - If the case-specific versions differ in anything besides the case name, that stage is not shared. If cases differ in substance (one derives a value, one reads it from Consts), that stage stays per-case, even when one derivation could feed every case.
- Instance-level parameters stay unkeyed: a relation whose value is part of the instance's identity, not per-key data. If a task does not vary an instance-level parameter per key, that parameter takes no key. A parameter that varies per case is per-key data: the comp is keyed by `Choice`.
- A nested comp's outputs are read through the instance path (`parse.box.margin(...)`).

## Multi-atom rules

- Head and `:-` on the first line.
- Body atoms on subsequent lines, indented 4 spaces, with related atoms grouped on one line.
- If a line's atoms do not already state its role, an inline `// ` comment names that role.

```
header_color(Idx, Col) :-
    in(P, Col),                                  // input cell
    c.header_dir(D), dist(P, D, 0),              // on the header edge
    c.across_dir(A_dir), dist(P, A_dir, Idx).    // index = across distance
```

The single-line form is fine for short rules (≤ ~80 chars).

## Disjunction

A disjunction is conditional branching inside one derivation: the shared frame stated once, then branches split on a test.

```
render(P, Col) :-
    in(P, _), c.side(K), divide_by_size_2d(P, K, 0, P_tile, _),
    ( tile_ink(P_tile, Col)            // inked tile
    ; !tile_ink(P_tile, _), c.bg(Col)  // blank tile
    ).
```

Each branch must ground the head's variables on its own. A branch that takes a value that the frame already derives binds it with `=` (`P_img = P`). Rules that share a head and a frame belong in one rule.

Branches are never choices: a rule does not range over choice tags through a disjunction.

## Fit

A solver that fits its Consts includes a `.comp Fit` after the body, under a `// --- fit ---` marker: one relation per fitted slot, with the slot's name and schema, derived from `ex_in` / `ex_out`. Fit relations that mirror no slot are helpers. The runner pairs Fit relations to slots by name, so a helper must not take a slot's name.

The runner checks each fitted slot against its Consts fill. `fit_diff` collects the rows that the two sides do not share. A nonempty `fit_diff` is a violation. Derived ids need only be stable across the solver's Ident slots, not equal to the stored ones.

Fit rules are body code: body style and the linter apply.

`ex_in` also carries the test inputs. The test example has no outputs, so it contradicts nothing. A rule that keeps the candidates that no example contradicts must therefore range over examples with `ex_out` rows.

## Parse

A `.comp Parse<Key>` contains a derivation that the body and the Fit comp share. It goes before the body rules, under a `// --- parse ---` marker.

Parse rules are body code: body style and the linter apply.

## Runner contract

`in` is declared in `lib.dl`, and the runner appends the IO directives. A solver declares only `out` from the IO surface.

`out` must be total over the expected output grid. If a cell is missing, the variant fails.

## Alt outputs

Alts in the task JSON are encoded by kind:

- A `rule` alt is a rival model: a case of `Choice`, one case per alt output.
- A `tiebreak` alt marks interchangeable content that the task leaves free. The solver enumerates the resolutions: `out` takes a trailing column typed `TiebreakResolution`, one value per valid resolution. The runner accepts a pair iff the set of emitted grids equals the expected grid plus the alts. A tiebreak allows only two distinct grids. If a pair emits more, the runner rejects it. No data or rules name or steer the resolution values, and case coverage does not apply to the resolution column.

## Souffle version

- Targets latest Souffle. All latest features are available.
- When the built-in aggregators do not fit, `docs/souffle-undocumented.md` is the reference.
