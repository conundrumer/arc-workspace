# Style

How a `.dl` solver file looks.

## Variables

- Single letter (with optional digit suffix): `P`, `T`, `B`, `L`, `R`, `K`, `D`, `A`, `N`, `G`, `H`, `W`, `T1`, `C2`, etc.
- Multi-character: leading-capital snake_case. `Col`, `Idx`, `Sh`, `K_cyc`, `P_grid_in`.
- Macros: SCREAMING (constants register). `TOP`, `IDENTITY`, `ORIGIN`.
- Types: PascalCase. `Position`, `Color`, `Choice`.
- Relations: snake_case. `tile_pos`, `axis_of`.

## Position frames

Most rule bodies hold Positions in multiple frames at once. Name a Position by the frame it lives in.

- **grid** — task input/output frame. `P_grid`, `P_grid_in`, `P_grid_out`; suffix when input/output both appear in one rule.
- **tile** — tile-arrangement frame produced by `divide`. `P_tile`.
- **intile** — within a single tile. `P_intile`.

Formal parameters of `divide` and `tile_pos` are `p_outer` / `p_inner` — they describe the decomposition. Solvers bind to `P_tile` / `P_intile` at call sites. For axis-only intermediates (e.g. `divide`'s inner before composing with the perpendicular axis), use decomposition language: `P_inner_axis`, `P_outer_v`, `P_inner_h`.

## File structure

- One file per task (`<task_id>.dl`); multi-impl variants live in the same file, distinguished by an ADT `Choice` column on `out`.
- `#include "../lib.dl"` at top.
- `.comp Consts { ... }` declares task-wide data; `.init c = Consts` exposes it as `c.<rel>`.
- Inside Consts, `.init helpers = ConstsHelpers` makes shared helpers (`frame_pos`, `tile_pos`) available as `helpers.<rel>(...)` in data declarations. The body has no access.
- All task-wide data lives in Consts, e.g. orientation (Dirs, Axes), dimensions, gaps, mappings, frame data.

Skeleton:

```
// Doc header — describe task; if multi-impl, name variants.

#include "../lib.dl"

.type Choice = VariantA {} | VariantB {}   // multi-impl only; omit for single-impl

.comp Consts {
    // task-wide data declarations and facts
}

.init c = Consts

.decl in(p: Position, col: Color)
.input in(IO=stdin)

// body rules

.decl out(p: Position, col: Color, c: Choice)   // multi-impl only; omit `c` for single-impl
out(...) :- ...

.output out(IO=stdout)
```

## Body

- No literals — orientation (`TOP`, `LEFT`, `VERTICAL`, etc.), colors, or non-zero task-shape numbers (lengths, offsets, gaps). Body reads them from Consts via `c.<rel>(...)` and parameterizes. Hardcoded values fix the body to one variant of the task; pulling from Consts keeps it symmetric across the family.
- No Position destructure. Use lib primitives instead. Position is opaque; destructure hardcodes edge indices and breaks orientation invariance.
- Avoid arithmetic. If necessary, flag.
- Inline relations can't appear inside aggregators. Wrap in a non-inline relation when needed.

## Multi-atom rules

Head and `:-` on first line; body atoms on subsequent lines indented 4 spaces; related atoms grouped on one line; inline `// ` comment per line naming the group's role.

```
header_color(Idx, Col) :-
    in(P, Col),                                  // input cell
    c.header_dir(D), dist(P, D, 0),              // on the header edge
    c.across_dir(A_dir), dist(P, A_dir, Idx).    // index = across distance
```

Single-line form is fine for short rules (≤ ~80 chars).

## Alt Outputs

If the task JSON contains alts, they need to be represented as a `Choice`.

## Further reading

- `docs/souffle-undocumented.md` — Recent Souffle additions: user-defined aggregates and lattices. Consult when the built-in aggregators don't fit.