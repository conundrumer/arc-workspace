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

Formal parameters of `divide` and `tile_pos` are `p_outer` / `p_inner` — they describe the decomposition. Solvers bind to `P_tile` / `P_intile` at call sites. For axis-only intermediates (e.g. `divide`'s inner before composing with the perpendicular axis), use decomposition language: `P_inner_axis`, `P_outer_v`, `P_inner_h`.

## File structure

- One file per task (`<task_id>.dl`); multi-impl cases live in the same file, distinguished by an ADT `Choice` column on `out`.
- First line: `// <task_id>`.
- `#include "../lib.dl"` at top.
- `.comp Consts { ... }` declares task-wide data; `.init c = Consts` exposes it as `c.<rel>`.
- Inside Consts, `.init helpers = ConstsHelpers` makes shared helpers (`frame_pos`, `tile_pos`) available as `helpers.<rel>(...)` in data declarations. The body has no access.
- All task-wide data lives in Consts, e.g. orientation (Dirs, Axes), dimensions, gaps, mappings, frame data.

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

## Body

- No literals — orientation (`DIR_T`, `DIR_L`, `AXIS_V`, etc.), colors, or non-zero task-shape numbers (lengths, offsets, gaps). Body reads them from Consts via `c.<rel>(...)` and parameterizes. Hardcoded values fix the body to one task in the family; pulling from Consts keeps it symmetric across the family.
    - Literals are fine inside a generic `.comp` written task-local — lib-shaped code, not body; the linter skips `.comp` blocks wholesale.
- No Position destructure. Use lib primitives instead. Position is opaque; destructure hardcodes edge indices and breaks orientation invariance.
- Avoid arithmetic. If necessary, that's a sign the lib needs a new primitive. Create that instead of having arithmetic in the solver body.
- Complement tests negate the named case: `!c.bg(Col)` for non-bg.
- Off-edge tests spell `dist(P, D, K), K != 0`, not `K > 0` — the zero case is refused by identity, not order. `!dist(P, D, 0)` is unavailable: Souffle can't negate an inline relation whose clause introduces variables.
- Inline relations can't appear inside aggregators. Wrap in a non-inline relation when needed.

## Components

- A new comp takes a `Key` type param; single-set sites key on `Unit` (`$U()`, in lib). An unkeyed comp shatters at the case boundary when a solver's cases share its pipeline: per-case `.init`s and dispatch rules differing only in the case name.
- Instance-level parameters stay unkeyed — a relation whose value is the instance's identity, not per-key data (`DirFrame.dir`, `Ray.dir`). Key one only when a task varies it per key.

## Multi-atom rules

Head and `:-` on first line; body atoms on subsequent lines indented 4 spaces; related atoms grouped on one line; inline `// ` comment per line naming the group's role.

```
header_color(Idx, Col) :-
    in(P, Col),                                  // input cell
    c.header_dir(D), dist(P, D, 0),              // on the header edge
    c.across_dir(A_dir), dist(P, A_dir, Idx).    // index = across distance
```

Single-line form is fine for short rules (≤ ~80 chars).

## Alt outputs

If the task JSON contains alts, encode them as cases of `Choice` — one case per alt output.

## Souffle version

- Targets latest Souffle. All latest features are available.
- `docs/souffle-undocumented.md` — Recent Souffle additions: user-defined aggregates and lattices. Consult when the built-in aggregators don't fit.