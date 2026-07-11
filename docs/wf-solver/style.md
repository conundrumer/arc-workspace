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

## File structure

- One file per task (`<task_id>.dl`); multi-impl cases live in the same file, distinguished by an ADT `Choice` column on `out`.
- First line: `// <task_id>`.
- `#include "../lib.dl"` at top.
- `.comp Consts { ... }` declares task-wide data; `.init c = Consts` exposes it as `c.<rel>`.
- Inside Consts, `.init helpers = ConstsHelpers` makes shared helpers (`frame_pos`, `tile_pos`) available as `helpers.<rel>(...)` in data declarations. The body has no access.
- All task-wide data lives in Consts, e.g. orientation (Dirs, Axes), dimensions, gaps, mappings, frame data.
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

.decl in(p: Position, col: Color)
.input in(IO=stdin)

// body rules

.decl out(p: Position, col: Color)
out(...) :- ...

.output out(IO=stdout)
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

.decl in(p: Position, col: Color)
.input in(IO=stdin)

// shared body rules

.decl out(p: Position, col: Color, c: Choice)

// --- CaseA ---
out(..., $CaseA()) :- ...

// --- CaseB ---
out(..., $CaseB()) :- ...

.output out(IO=stdout)
```

Cases are grouped under `// --- <name> ---` markers in both Consts and body — no interleaving across cases.

## Types

A solver defines types only for model coverage (`Choice` and the ADTs its cases carry) and for comp instantiation (records that fill a generic comp's type params).

## Body

- No literals: orientation (`DIR_T`, `DIR_L`, `AXIS_V`, etc.), colors, or non-zero task-shape numbers (lengths, offsets, gaps). The body reads them from Consts via `c.<rel>(...)` and parameterizes. Hardcoded values fix the body to one task in the family; values read from Consts keep it symmetric across the family.
    - Literals are fine inside a generic `.comp` written task-local; that is lib-shaped code rather than body, and the linter skips `.comp` blocks entirely.
- No Position destructure. Use lib primitives instead. Position is opaque; destructuring hardcodes edge indices and breaks orientation invariance.
- Avoid arithmetic. When arithmetic seems necessary, the lib needs a new primitive. Create that instead of writing arithmetic in the solver body.
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

## Inline cost

Lib primitives are `inline`: each call expands into the calling rule, and Souffle evaluates the expansion once per tuple. Work that is the same for every tuple is not hoisted. A deep primitive chain inside a rule that ranges over many cells can exceed the runner's 5s CPU budget per pair. Compute tuple-independent values, such as deltas derived from Consts data, in their own relation and join them. When a derived per-cell position must also be read backward, materialize it in a comp relation keyed by the cell (`Reframe.inner`); the indexed join replaces the inline chain.

## Alt outputs

If the task JSON contains alts, encode them as cases of `Choice` — one case per alt output.

## Souffle version

- Targets latest Souffle. All latest features are available.
- `docs/souffle-undocumented.md` — consult when the built-in aggregators do not fit.
