# Patterns

Patterns observed across `.dl` solvers. Distinct from `4-style.md` (rules every solver follows).

This list is descriptive, not prescriptive — the `.dl` files are the source of truth. It exists so future sessions can scan what's been used.

## Multiple modeling forms via ADT `Choice`

Multiple models live in one solver file as variants of an ADT `Choice` column on `out`. Variants can be more than two, may carry their own per-variant data, and may nest (a variant's data can itself be an ADT). Each variant fires its own rules; the runner emits each as a candidate.

```
.type Choice = VariantA {} | VariantB {}

.decl out(p: Position, col: Color, c: Choice)
out(P, Col, $VariantA()) :- ...
out(P, Col, $VariantB()) :- ...
```

## `GRID_HxW` for grid data

Runner-side cpp codegen lets `.dl` files declare 2D grids of values literally; the macro emits position-keyed facts in row-major order. Color grids, label grids, transform grids — any per-cell data.

```
.decl template(p: Position, col: Color)
GRID_3x3(template,
    1, 2, 1,
    2, 0, 2,
    1, 2, 1)
```

## Set-keyed relations via parent/child tables

A relation keyed by a multiset of members declares as two tables glued by an `eid`: parent holds `(eid, out-fields)`, child holds `(eid, member-fields)`. The match uses the count-trick — an entry fires when the count of matched members equals the entry's total member count. Used for combine tables where member order doesn't matter.

```
.decl combine_member(eid: number, p_outer: Position, c: Color)
.decl combine_out(eid: number, c_out: Color)

combine_member(0, [0,1,0,0], 0). combine_member(0, [1,0,0,0], 0). combine_out(0, 2).
combine_member(1, [0,1,0,0], 9). combine_member(1, [1,0,0,0], 0). combine_out(1, 0).

out(P_grid_out, Col_out) :-
    c.combine_out(Eid, Col_out),
    N = count : { c.combine_member(Eid, _, _) },
    N = count : { c.combine_member(Eid, P_tile, C),
                  decompose(P_grid_in, P_tile, P_grid_out, _), in(P_grid_in, C) }.
```

## Bidirectional mapping via positive recursion

A symmetric relation declared one direction, plus `mapping(B, A) :- mapping(A, B)` for closure.

```
.decl mapping(c_from: Color, c_to: Color)
mapping(5, 8).
mapping(B, A) :- mapping(A, B).
```

## 1D `divide` composed to 2D

`divide` along V and H separately, composed via `compose`, gives 2D decomposition.

```
divide(P_grid, VERTICAL,   Nv, Gv, P_outer_v, P_inner_v),
divide(P_grid, HORIZONTAL, Nh, Gh, P_outer_h, P_inner_h),
compose(P_outer_v, P_outer_h, P_tile),
compose(P_inner_v, P_inner_h, P_intile).
```
