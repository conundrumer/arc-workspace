# Patterns

Patterns observed across `.dl` solvers. Distinct from `4-style.md` (rules every solver follows).

This list is descriptive, not prescriptive — the `.dl` files are the source of truth. It exists so future sessions can scan what's been used.

## Multiple modeling forms via ADT `Choice`

Multiple models live in one solver file as cases of an ADT `Choice` column on `out`. Cases can be more than two, may carry their own per-case data, and may nest (a case's data can itself be an ADT). Each case fires its own rules; the runner emits each as a candidate.

```
.type Choice = CaseA {} | CaseB {}

.decl out(p: Position, col: Color, c: Choice)
out(P, Col, $CaseA()) :- ...
out(P, Col, $CaseB()) :- ...
```

Use a record-typed `Choice` when cases compose from independent parts:

```
.type Detect = PairExist {} | Count {}
.type Stage  = PerCell {} | SliceMap {}
.type Choice = [detect: Detect, stage: Stage]

.decl out(p: Position, col: Color, c: Choice)
out(P, Col, [$PairExist(), $PerCell()]) :- ...
out(P, Col, [$Count(),     $SliceMap()]) :- ...
```

Use a sum directly to enumerate cases when only specific combinations exist.

## `GRID_HxW` for grid data

Runner-side cpp codegen lets `.dl` files declare 2D grids of values literally; the macro emits position-keyed facts in row-major order. Color grids, label grids, transform grids — any per-cell data.

```
.decl template(p: Position, col: Color)
GRID_3x3(template,
    1, 2, 1,
    2, 0, 2,
    1, 2, 1)
```

## `GRID_HxW` with multi-pattern eid-keying

Multiple visual patterns (each a distinct `GRID_HxW`) joined to a shared eid-keyed relation via derive rules.

```
.decl p0(p: Position, col: Color)
GRID_3x3(p0, 0,1,0, 1,1,1, 0,1,0)

.decl p1(p: Position, col: Color)
GRID_3x3(p1, 1,0,1, 0,0,0, 1,0,1)

.decl pattern_member(eid: number, p: Position, col: Color)
pattern_member(0, P, C) :- p0(P, C), C != 0.
pattern_member(1, P, C) :- p1(P, C), C != 0.

.decl pattern_out(eid: number, col: Color)
pattern_out(0, 3). pattern_out(1, 8).
```

The GRID gives visual shape; the derive rule filters (e.g., `C != 0` for non-bg members) and tags with the eid.

## Set-keyed relations via parent/child tables

A relation keyed by a multiset of members declares as two tables glued by an `eid`: parent holds `(eid, out-fields)`, child holds `(eid, member-fields)`. The match uses the count-trick — an entry fires when the count of matched members equals the entry's total member count.

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

## `divide_by_size` (K, G) parameter space

Step size between tile starts is `K + G`. Different (K, G) splits of the same step model the same spatial rhythm with different tile/gap semantics.

For a frame extent H and effective step S = K + G, divisibility requires `(H + G) % S = 0`.

Concrete: period-2 pattern over H=7.

| K | G | Step | Divisibility | Tile semantics |
|---|---|------|-------------|----------------|
| 2 | 0 | 2 | `7 % 2 = 1` — fails | — |
| 1 | 1 | 2 | `8 % 2 = 0` ✓ | bg cell = tile, dot cell = gap |
| 3 | -1 | 2 | `6 % 2 = 0` ✓ | adjacent tiles overlap by 1 row |

K=2 G=0 (the visual period) fails for odd H. K=1 G=1 reframes bg as tile and dot as gap. K=3 G=-1 uses shared-boundary overlap.

Before adding a new primitive for a periodic pattern, check whether an existing divide/divide_by_size encoding covers it via a different (K, G) split.

## 1D `divide` composed to 2D

`divide` along V and H separately, composed via `compose`, gives 2D decomposition.

```
divide(P_grid, VERTICAL,   Nv, Gv, P_outer_v, P_inner_v),
divide(P_grid, HORIZONTAL, Nh, Gh, P_outer_h, P_inner_h),
compose(P_outer_v, P_outer_h, P_tile),
compose(P_inner_v, P_inner_h, P_intile).
```
