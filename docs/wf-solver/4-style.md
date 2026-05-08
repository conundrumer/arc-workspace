# Style

How a `.dl` solver file looks.

## File structure

- One file per task (`<task_id>.dl`); multi-impl variants live in the same file, distinguished by an ADT `Choice` column on `out`.
- `#include "../lib.dl"` at top.
- `.comp Consts { ... }` declares task-wide data; `.init c = Consts` exposes it as `c.<rel>`.
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
header_color(IDX, COL) :-
    in(P, COL),                                  // input cell
    c.header_dir(D), dist(P, D, 0),              // on the header edge
    c.across_dir(A_DIR), dist(P, A_DIR, IDX).    // index = across distance
```

Single-line form is fine for short rules (≤ ~80 chars).

## Alt Outputs

If the task JSON contains alts, they need to be represented as a `Choice`.