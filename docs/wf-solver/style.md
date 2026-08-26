# Style

How a `.dl` solver file looks.

`programs/lib.dl` defines shared types and primitives — self-explanatory.

## Variables

- Single letter (with optional digit suffix): `P`, `T`, `B`, `L`, `R`, `K`, `D`, `A`, `N`, `G`, `H`, `W`, `T1`, `C2`, etc.
- Multi-character: leading-capital snake_case. `Col`, `Idx`, `Sh`, `K_cyc`, `P_grid_in`.
- Macros: SCREAMING (constants register). `DIR_T`, `D4_ID`, `ORIGIN`.
- Types: PascalCase. `Position`, `Color`, `Choice`.
- Relations: snake_case. `tile_pos`, `axis_of`.

## Position frames

Most rule bodies hold Positions in multiple frames at once. Name a Position by the frame it lives in.

- **grid** — task input/output frame. `P_grid`, `P_grid_in`, `P_grid_out`; suffix when input/output both appear in one rule.
- **tile** — tile-arrangement frame produced by `divide`. `P_tile`.
- **intile** — within a single tile. `P_intile`.

Formal parameters of `divide` and `tile_pos` are `p_outer` / `p_inner`; they describe the decomposition. Solvers bind to `P_tile` / `P_intile` at call sites. For axis-only intermediates (e.g. `divide`'s inner before composing with the perpendicular axis), use decomposition language: `P_inner_axis`, `P_outer_v`, `P_inner_h`.

When a decomposition's inner coordinate is also the output cell, name it by the setup. A decompose-fold names the output cell `P_grid_out` in the consuming rules, and keeps `P_intile` in the production rules that decompose the input. A select or crop names it `P_intile`: the cell is the extracted tile's interior. An overlay names the frame cell it stacks onto — bare `P`, or `P_frame` when another frame shares the rule.

## File structure

- One file per task (`<task_id>.dl`); multi-impl cases live in the same file, distinguished by an ADT `Choice` column on `out`.
- First line: `// <task_id>`.
- Second line, exactly one of:
    - `// concept: <terms>` — family representative. Terms from `concepts.md`, separated by spaces, the union over cases: setup terms plus each case's prior term.
    - `// family: <task_id>` — family sibling: same body and Fit comp, fills differ. Points at the representative, the family's first-solved member. A sibling's header keeps only task-specific content.
- `#include "../lib.dl"` at top.
- `.comp Consts { ... }` declares task-wide data; `.init c = Consts` exposes it as `c.<rel>`.
- Inside Consts, `.init helpers = ConstsHelpers` makes shared helpers (`frame_pos`, `tile_pos`) available as `helpers.<rel>(...)` in data declarations. The body has no access.
- All task-wide data lives in Consts, e.g. orientation (Dirs, Axes), dimensions, gaps, mappings, frame data.
- A rule inside Consts derives from fact slots; a datum never sits as a literal in a rule body. A literal 1 stating a unit — a single row, one cell wide — stays in the rule, under an `// @unit: <what the 1 states>` comment on the rule's line. A derived relation carries no Fit relation.
- A datum lives in a shared slot when more than one case reads it and every task those cases both fit fills it the same under each; a fill some such task pulls apart is per-case data.
- A single-fact data declaration puts the fact on the decl line, one space after it. A multi-fact declaration puts the facts on the next line at the decl's indent. Facts are not column-aligned across a block.
- Store an orientation datum constrained by another as a relative value (`Sense` via `turn`, `Axis` via `perp`). A second absolute slot admits fills the family does not have; the relative form has one fill per member.

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

Cases are grouped under `// --- <name> ---` markers in both Consts and body — no interleaving across cases.

## Types

A solver defines types only for model coverage (`Choice` and the ADTs its cases carry) and for comp instantiation (records that fill a generic comp's type params).

## Body

- No literals: orientation (`DIR_T`, `DIR_L`, `AXIS_V`, etc.), colors, or non-zero task-shape numbers (lengths, offsets, gaps). The body reads them from Consts via `c.<rel>(...)` and parameterizes. Hardcoded values fix the body to one task in the family; values read from Consts keep it symmetric across the family.
    - Literals are fine inside a generic `.comp` written task-local; that is lib-shaped code rather than body, and the linter skips `.comp` blocks — except `Fit` and `Parse`, whose rules lint as body.
- No Position destructure. Use lib primitives instead. Position is opaque; destructuring hardcodes edge indices and breaks orientation invariance.
- Avoid arithmetic and raw aggregates. When they seem necessary, the lib needs a new primitive. Create that instead of writing them in the solver body.
- No `range`. It generates a number sequence; the body reads positions and extents through lib primitives.
- Complement tests negate the named case: `!c.bg(Col)` for non-bg.
- Write off-edge tests as `dist(P, D, K), K != 0`, not `K > 0`: the zero case is excluded by identity, not by order. `!dist(P, D, 0)` is unavailable: Souffle cannot negate an inline relation whose clause introduces variables.
- Inline relations cannot appear inside aggregators. Wrap in a non-inline relation when needed.

## Components

- Use a lib unit only when the task has its concept. Needing part of its computation is not a reason to use it. If only one step is needed, write it with primitives or a local rule.
- A new comp takes a `Key` type param; single-set sites key on `Unit` (`$U()`, in lib). An unkeyed comp forces duplication at the case boundary when a solver's cases share its pipeline: per-case `.init`s and dispatch rules that differ only in the case name.
    - "Differ only in the case name" bounds the sharing. A stage where cases differ in substance — one derives a value, one reads it from Consts — stays per-case, even when one derivation could feed every case.
- Instance-level parameters stay unkeyed: a relation whose value is part of the instance's identity, not per-key data (`DirFrame.dir`, `Ray.dir`). Key one only when a task varies it per key.

## Multi-atom rules

Head and `:-` on the first line; body atoms on subsequent lines indented 4 spaces; related atoms grouped on one line; an inline `// ` comment per line names the group's role.

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

Each branch must ground the head's variables on its own. A branch that takes a value the frame already derives binds it with `=` (`P_img = P`). Rules that share a head and a frame belong in one rule.

Branches are never choices: a rule does not range over choice tags through a disjunction.

## Inline cost

Lib primitives are `inline`: each call expands into the calling rule, and Souffle evaluates the expansion once per tuple. Work that is the same for every tuple is not hoisted. A deep primitive chain inside a rule that ranges over many cells can exceed the runner's 5s CPU budget per pair. Compute tuple-independent values, such as deltas derived from Consts data, in their own relation and join them. When a derived per-cell position must also be read backward, materialize it in a comp relation keyed by the cell (`Reframe.inner`); the indexed join replaces the inline chain.

## Fit

A solver that fits its Consts carries a `.comp Fit` after the body, under a `// --- fit ---` marker: one relation per fitted slot, with the slot's name and schema, derived from `ex_in` / `ex_out`. Fit relations that mirror no slot are helpers.

A slot gets a Fit relation when the fit plan (`fit-plan`) lists it under `write a Fit relation`, or by choice from the plan's over-budget section: there, pick whichever settling slots are simplest to fit until the product of the rest goes under the budget.

The runner checks each fitted slot against its Consts fill; `fit_diff` collects the rows the two sides do not share, and a nonempty `fit_diff` is a violation. Derived ids need only be stable across the solver's Ident slots, not equal to the stored ones.

Fit rules are body code: body style and the linter apply.

`ex_in` also carries the test inputs. A rule that keeps the candidates no example contradicts must range over examples with `ex_out` rows: the test example has no outputs, so it contradicts nothing.

## Parse

A `.comp Parse<Key>` holds a derivation the body and the Fit comp share; it sits before the body rules, under a `// --- parse ---` marker.

Parse rules are body code: body style and the linter apply.

## Runner contract

`in` is declared in `lib.dl`, and the runner appends the IO directives; of the IO surface, a solver declares only `out`.

`out` must be total over the expected output grid: a missing cell fails the variant.

## Alt outputs

If the task JSON contains alts, encode by kind:

- A `rule` alt is a rival model: a case of `Choice`, one case per alt output.
- A `tiebreak` alt marks interchangeable content the task leaves free. The
  solver enumerates the resolutions: `out` takes a trailing column typed
  `TiebreakResolution`, one value per valid resolution, and the runner
  accepts a pair iff the set of emitted grids equals the expected grid plus
  the alts. A tiebreak is two-way: the runner rejects a pair emitting more
  than two distinct grids. No data or rules name or steer the resolution
  values, and case coverage does not apply to the resolution column.

## Souffle version

- Targets latest Souffle. All latest features are available.
- `docs/souffle-undocumented.md` — consult when the built-in aggregators do not fit.
