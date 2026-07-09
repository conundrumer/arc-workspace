# Patterns

Patterns observed across `.dl` solvers. Distinct from `style.md` (rules every solver follows).

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

## Position remapping via `GRID` id join

A stored position correspondence spells as two GRIDs joined on an opaque id: `src` labels the domain cells, `dst` gives each target cell the id of its source. The correspondence is visible in layout; ids carry identity only. Raw Position-pair facts state the same data illegibly.

```
.decl src(p: Position, id: number)
GRID_3x3(src,
    0, 1, 2,
    3, 4, 5,
    6, 7, 8)

.decl dst(p: Position, id: number)
GRID_5x5(dst,
    0, 0, 1, 2, 2,
    0, 0, 1, 2, 2,
    3, 3, 4, 5, 5,
    6, 6, 7, 8, 8,
    6, 6, 7, 8, 8)

.decl map(p_in: Position, p_out: Position)
map(P_in, P_out) :- src(P_in, Id), dst(P_out, Id).
```

(e633a9e5 $Map — a nonuniform scale-up as pure data.)

## Stored total orders as dense ranks

A total order in Consts spells as dense 0-based rank data, consumed by comparison only. Ranks state each element's place in the sequence; successor edges imply it through closure. Comparison-only consumption keeps the borrowed number structure inert; dense 0-based fills keep the encoding canonical — a gapped fill spells one order many ways.

```
.decl ink_rank(c: Color, r: number)
ink_rank(7, 0). ink_rank(4, 1). ink_rank(8, 2). ink_rank(6, 3).

beaten(P, Col) :-
    ink_at(P, Col), ink_at(P, C2),
    c.ink_rank(C2, R2), c.ink_rank(Col, R), R2 < R.
```

Over a spatial domain the ranks lay out as a GRID — a68b268e's `c.prio`, the precedence visible in the tile arrangement.

## Stored symmetry sets as full subgroups

A stored symmetry set is a stabilizer — the transforms that fix a grid — and a stabilizer is a subgroup. It spells as the subgroup's complete element list, identity included. Generating sets spell one subgroup many ways (`{LR, TB}`, `{LR, HT}`, `{TB, HT}` close to the same Klein group); the full list is one spelling per subgroup, and a fill is valid iff it is one of D4's ten subgroups.

```
.decl sym(d: D4)
sym(D4_ID). sym(D4_CW). sym(D4_HT). sym(D4_CC).
sym(D4_LR). sym(D4_TB). sym(D4_DG). sym(D4_AD).
```

ID is inert at consumption: an application site skips it through its clean-source guard (b8825c91); an invariance test finds it vacuously unbroken (44f52bb0's `mapping_sym`).

## Set-keyed relations via parent/child tables

A relation keyed by a multiset of members declares as two tables glued by an `eid`: parent holds `(eid, out-fields)`, child holds `(eid, member-fields)`. The match runs through `KeyedSetCompare` (`lib.dl`) — the child table feeds `pattern_member`, the observed cells feed `observed_member`, and `covers` / `equals` test containment / equality. The parent table maps the matched `eid` to its output.

```
.decl combine_member(eid: number, p_outer: Position, c: Color)
.decl combine_out(eid: number, c_out: Color)

combine_member(0, [0,1,0,0], 0). combine_member(0, [1,0,0,0], 0). combine_out(0, 2).
combine_member(1, [0,1,0,0], 9). combine_member(1, [1,0,0,0], 0). combine_out(1, 0).

.type CombineMember = [p: Position, col: Color]
.init combine_match = KeyedSetCompare<Position, CombineMember>
combine_match.pattern_member(Eid, [P_outer, C]) :- c.combine_member(Eid, P_outer, C).
combine_match.observed_member(P_grid_out, [P_tile, C]) :-
    decompose(P_grid_in, P_tile, P_grid_out, _), in(P_grid_in, C).

out(P_grid_out, Col_out) :-
    c.combine_out(Eid, Col_out),
    combine_match.equals(P_grid_out, Eid).
```

`equals` here because the observed tiles at a cell *are* exactly the entry's members; use `covers` where the observed set is a true superset of the pattern.

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
divide(P_grid, AXIS_V, Nv, Gv, P_outer_v, P_inner_v),
divide(P_grid, AXIS_H, Nh, Gh, P_outer_h, P_inner_h),
compose(P_outer_v, P_outer_h, P_tile),
compose(P_inner_v, P_inner_h, P_intile).
```

## Wide and long layouts

A relation lays co-occurring values out wide — columns of one atom — or long — one row per member. Multiplicity the concept fixes goes wide: the two axes, a corner's two dirs, the four edge distances (Position is the wide form of per-Dir distance data). Multiplicity the task varies stays long: markers, tiles, ink cells.

Wide reads by unification; long reads by joins. A long spelling of a fixed co-occurrence makes every consumer reassemble it — a self-join with a distinctness guard, deriving each symmetric result twice:

```
edge(D1), edge(D2), D1 != D2, marked(P, D1), marked(P, D2).
```

The reassembly belongs in one place: the domain's pairing relation (`opposite` is the Dir form; each closed domain earns its own), or the defining rule of a wide relation. On a domain with identity only (colors), the distinctness join is the concept itself, not a shadow of one.

Order inside a wide atom is a tag column or a repeated value, never slot position. A pairing relation carries all orders as rows (`opposite`, `turn`), so which member fills which slot is data. A record ordering members by positional convention is a wide form without that license — the convention crosses as data.

A repeated variable in a wide atom states the diagonal case directly — equal extents (a square), equal distances (centered; on a corner's diagonal) — where the long spelling needs an agreement join.

Derivation is long by nature: a rule quantifying over an index emits one row per index value, and aggregation computes per index (`Bbox` aggregates `edge_min` per Dir, then packs the four into `margin`'s Position). Widening derived data costs one pairing join at its defining rule; a readout of a value that already carries the co-occurrence widens for free.

## `cell_split` — input cell with its axis decomposition

Pairs an input cell with its along/across split on the task's axis.

```
.decl cell_split(p: Position, col: Color, p_inner: Position, p_across: Position)
cell_split(P, Col, P_inner, P_across) :- in(P, Col), c.axis(A), split(P, A, P_inner, P_across).
```
