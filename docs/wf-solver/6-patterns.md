# Patterns

Patterns observed across `.dl` solvers. Distinct from `4-style.md` (rules every solver follows).

This list is descriptive, not prescriptive — the `.dl` files are the source of truth. It exists so future sessions can scan what's been used.

## Multiple modeling forms via ADT `Choice`

Multiple models live in one solver file as variants of an ADT `Choice` column on `out`. Variants can be more than two, may carry their own per-variant data, and may nest (a variant's data can itself be an ADT). Each variant fires its own rules; the runner emits each as a candidate.

```
.type Choice = VariantA {} | VariantB {}

.decl out(p: Position, col: Color, c: Choice)
out(P, COL, $VariantA()) :- ...
out(P, COL, $VariantB()) :- ...
```

See `fafffa47.dl`, `bd4472b8.dl`, `68b67ca3.dl`.

## `GRID_HxW` for grid data

Runner-side cpp codegen lets `.dl` files declare 2D grids of values literally; the macro emits position-keyed facts in row-major order. Color grids, label grids, transform grids — any per-cell data.

```
.decl template(p: Position, col: Color)
GRID_3x3(template,
    1, 2, 1,
    2, 0, 2,
    1, 2, 1)
```

See `833966f4.dl`, `ca8de6ea.dl`, `e9afcf9a.dl`, `68b67ca3.dl`.

## Set-keyed relations via parent/child tables

A relation keyed by a multiset of members declares as two tables glued by an `eid`: parent holds `(eid, out-fields)`, child holds `(eid, member-fields)`. The match uses the count-trick — an entry fires when the count of matched members equals the entry's total member count. Used for combine tables where member order doesn't matter.

```
.decl combine_member(eid: number, p_outer: Position, c: Color)
.decl combine_out(eid: number, c_out: Color)

combine_member(0, [0,1,0,0], 0). combine_member(0, [1,0,0,0], 0). combine_out(0, 2).
combine_member(1, [0,1,0,0], 9). combine_member(1, [1,0,0,0], 0). combine_out(1, 0).

out(O, C_OUT) :-
    c.combine_out(EID, C_OUT),
    N = count : { c.combine_member(EID, _, _) },
    N = count : { c.combine_member(EID, P_O, C),
                  decompose(P_IN, P_O, O), in(P_IN, C) }.
```

See `fafffa47.dl`.

## Bidirectional mapping via positive recursion

A symmetric relation declared one direction, plus `mapping(B, A) :- mapping(A, B)` for closure.

```
.decl mapping(c_from: Color, c_to: Color)
mapping(5, 8).
mapping(B, A) :- mapping(A, B).
```

See `d511f180.dl`.

## 1D `divide` composed to 2D

`divide` along V and H separately, composed via `compose`, gives 2D decomposition.

```
divide(P, VERTICAL,   NV, GV, P_OV, P_IV),
divide(P, HORIZONTAL, NH, GH, P_OH, P_IH),
compose(P_OV, P_OH, P_OUTER),
compose(P_IV, P_IH, P_INNER).
```

For 1D use where the full 2D inner position is needed, the perpendicular component is recovered via `split + compose`:

```
divide(P, A, N, 0, P_O, P_I_AXIS),
split(P, A, _, ACROSS),
compose(P_I_AXIS, ACROSS, P_INNER).
```

See `fafffa47.dl`'s `$Div` decompose.
