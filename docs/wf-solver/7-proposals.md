# Proposals

For proposing and staging changes to `.dl` style and primitives. Not a changelog or general notes.
If a proposal is implemented, it is removed from this doc.

## `ConcatPipeline` — unequal-sized rectilinear tiles

`divide` / `divide_2d` / `divide_by_size_2d` (forward) and `concat` /
`concat_slab` / `concat_2d` (inverse) cover uniform tiles: every tile shares a
size, so the per-tile step is constant. Unequal-sized rectilinear tiles need
cumulative offsets — each row/column carries its own extent. `ConcatPipeline`
derives per-tile dims and per-edge cumulative offsets, then recomposes via
`compose`.

Solver populates `tile_in` (dim info; values aren't read by the pipeline) and
`axis_gap`. The component derives per-row / per-col tile dims, cumulative
per-edge offsets, assembles `tile_offset(p_outer, p_off)`, and exposes a
one-liner `concat` (lookup + `compose`).

```
.comp ConcatPipeline {
    .decl tile_in(p_outer: Position, p_inner: Position)
    .decl axis_gap(a: Axis, g: number)

    // Tile dim along axis(D), indexed by tile's distance from edge D.
    // Every cell in a rectilinear tile produces the same K — set semantics dedupes.
    .decl axis_dim(d: Dir, i: number, k: number)
    axis_dim(D, I, K) :-
        tile_in(P_outer, P_inner),
        dist(P_outer, D, I),
        opposite(D, D2),
        dist(P_inner, D, Near), dist(P_inner, D2, Far),
        K = Near + Far + 1.

    // Cumulative offset from edge D for the tile at distance I from D.
    .decl edge_off(d: Dir, i: number, off: number)
    edge_off(D, I, OFF) :-
        axis_dim(D, _, _),
        axis_of(D, A), axis_gap(A, G),
        OFF = (sum K : { axis_dim(D, J, K), J < I }) + I*G.

    // Tile bbox offset in grid units, assembled from the four edges.
    .decl tile_offset(p_outer: Position, p_off: Position)
    tile_offset([OT, BO, OL, RO], [T_off, B_off, L_off, R_off]) :-
        edge_off(TOP,    OT, T_off),
        edge_off(BOTTOM, BO, B_off),
        edge_off(LEFT,   OL, L_off),
        edge_off(RIGHT,  RO, R_off).

    // Lookup + compose.
    .decl concat(p_outer: Position, p_inner: Position, p_grid: Position) inline
    concat(P_outer, P_inner, P_grid) :-
        tile_offset(P_outer, P_off),
        compose(P_off, P_inner, P_grid).
}
```

Internals collapse via `Dir`: `axis_dim`, `edge_off`, and `tile_offset` each
generalize across edges/axes in a single rule. Like the uniform `concat` family,
it's shape-agnostic — `P_outer` full-2D or axis-only both flow through `compose`,
so 2D and slab arrangements use the same rules.

Solver usage:

```
.init concat = ConcatPipeline
concat.tile_in(P_outer, P_inner) :- tile_data(P_outer, P_inner, _).
concat.axis_gap(VERTICAL, 0). concat.axis_gap(HORIZONTAL, 0).

out(P_grid, V) :-
    tile_data(P_outer, P_inner, V),
    concat.concat(P_outer, P_inner, P_grid).
```

## `KeyedSetCompare` extensions — set-relationship lattice

`KeyedSetCompare<Key, Member>` (in `lib.dl`) exposes `covers` / `equals` / `pattern_size`.
These extensions derive from the same three counts it already computes (`|pattern|`,
`|observed|`, `overlap`); add one when a real task needs it, not preemptively
(lib-addition protocol):

- `within(observed, pattern)` — observed ⊆ pattern (`overlap == observed_size`)
- `disjoint(observed, pattern)` — `overlap == 0`
- `intersects(observed, pattern)` — `overlap > 0`
- `observed_size(observed, n)`, `overlap_size(observed, pattern, n)` — projections that
  unlock nearest / best-overlap selection

**Scope.** The component owns set-relationship derivation. Ranking policy (`best_covered`,
`nearest`) and approximate / multiset / payload matching sit at or past the edge —
solver-local or a separate component. Current hints: 3618c87e → an `unmatched` negative,
44f52bb0 → `best_covered`.

**Global observed set.** When the observed set is global — one set, no
meaningful key (44f52bb0's invariance set, 27a28665's silhouette) — the call passes a
constant `0: number` key, which is what lib landed on. A `.type Unit = U {}` singleton
keyed on `$U()` remains a possible tightening — it would state "exactly one observed
set" in the type instead of a dummy int.

## `Ordinal` — sparse → dense rank

Pattern: turn a sparse numeric set into a dense ordinal-position mapping. `rank(K, R)` where R is the count of elements strictly less than K. For input `{2, 5, 7}` → `{2→0, 5→1, 7→2}`.

```
.comp Ordinal {
    .decl idx_set(k: number)

    .decl rank(k: number, r: number)
    rank(K, R) :-
        idx_set(K),
        R = count : { idx_set(K2), K2 < K }.
}
```

**Task-local home (protocol step 1).** f8ff0b80 ranks non-bg colors by cell
count and lays them out along an axis. Its `color_rank` is exactly this
operation; it carries a solver-local `Ordinal` comp fed by the distinct color
counts (`o.idx_set(N) :- color_count(_, N)`), with `color_rank` joining color →
count → rank. Ranking the *distinct counts* (rather than competition-ranking the
colors, which skips ranks on ties and drives DirFrame's opposite-edge distance
negative) keeps `dist_set` dense.

Composes with `DirFrame`: Ordinal does sparse → dense; DirFrame keeps its dense-input contract and places indices in axis-only Positions.

```
.init o = Ordinal
.init col = DirFrame

o.idx_set(K) :- some_sparse_indices(K).
col.dir(TOP).
col.dist_set(R) :- o.rank(_, R).

out(P, ...) :- some_sparse_indices(K), o.rank(K, R), col.pos(R, P).
```

**Direction.** Default is ascending (`K2 < K`). When the rank is purely
positional — it only feeds a frame placement — a descending layout falls out by
placing from the opposite edge (flip `DirFrame.dir` to `opposite(anchor)`), no
negation needed; f8ff0b80 does this to seat the largest count at its anchor
edge while ranking ascending. Upstream negation is only needed when the rank
*value* itself flows downstream (a color lookup, an arithmetic step), where the
magnitude must invert.

**Ties.** `idx_set` is a set — duplicate K values dedupe. Distinct items mapping to the same K share that K's rank. Useful for grouping; if unique placement is needed, break ties upstream. The dedupe keeps the output rank set dense even under ties, so a `DirFrame` fed from it stays valid; the collision is two items at one Position, not a sparse frame.

**Naming.** "Rank" in pure math means matrix rank / set rank — different concepts. "Ordinal" sidesteps that misappropriation while naming the output (an ordinal position). The operation itself (count of strictly-less-than over a set) matches CS / stats / SQL "dense rank."

## `Cycle` — directed cycle with basepoint-free rotation

The Z/n cycle species made first-class. `succ` declares a directed cycle by its
edges; `walk(p0, n, p)` advances a start cell n successor steps. The edge set
carries no basepoint, so the cycle is recoverable content but any single
position is an arbitrary reference — `walk` (a step count, the torsor
difference) is basepoint-free; the absolute position is not.

```
.comp Cycle<T> {
    .decl succ(p: T, p_next: T)
    .decl step(n: number)               // advance counts in use (bounds the walk)

    .decl walk(p0: T, n: number, p: T)  // p = p0 advanced n steps along succ
    walk(P0, 0, P0) :- succ(P0, _).
    walk(P0, N1, P2) :-
        walk(P0, N, P1), succ(P1, P2),
        step(N1), N1 = N + 1.
}
```

**Bound.** `walk` over a finite cycle never terminates unbounded — n grows past
the cycle length. `step` enumerates the advance counts the solver needs and caps
the recursion. Alternative: have the component count cycle length L and expose
the full Z/L (`walk` for n in 0..L-1) — more machinery, unneeded when a solver
applies only a few shifts. `DirCycle` (below) takes that alternative for a dense
axis — it counts L from its nodes, so its caller hands it no step set.

**Task-local home (protocol step 1).** ca8de6ea collapses a 5×5 X onto a dense
3×3. The output's 8-cell ring is a CW `Cycle`; each X-arm cell maps to the ring
cell at its own diagonal, advanced by a per-ring shift — corner ring 0, inner
ring +1.

```
.init ring = Cycle<Position>
ring.succ(P, P_next) :- c.ring_succ(P, P_next).   // the ring cycle
ring.step(N)         :- c.ring_shift(_, N).        // shifts in use

out(P_out, ...) :- ..., ring.walk(P_corner, Shift, P_out).
```

**Second home (protocol step 1).** 6d1d5c90's rows are a `Cycle` built by
`DirCycle` (below). Where ca8de6ea enumerates an irregular ring as `succ` data,
6d1d5c90 *derives* `succ` from axis adjacency — the abstraction's two ends.

## `step_delta` — direction → unit displacement

`step_delta(d: Dir, delta: Position)` is the unit step toward `d`: −1 at edge `d`,
+1 at its opposite. It is the direction-keyed form of the four step deltas
`Reach`/`Components` hardcode — `step([-1,1,0,0]). step([1,-1,0,0]). ...` collapse
to `step(S) :- dir_elem(D), step_delta(D, S)` — connectivity rebuilds on it
instead of recopying the deltas.

```
.decl step_delta(d: Dir, delta: Position) inline
step_delta(D, Step) :-
    opposite(D, O), edge_delta(D, -1, Sd), edge_delta(O, 1, So), compose(Sd, So, Step).
```

**Home.** In lib it is a free inline beside `edge_delta` — its ±1 are lib-internal
literals. Task-local it can't sit in a solver body (the linter bars the unit
literals), so 6d1d5c90 shelters it in a one-relation `UnitStep` comp (`.comp`
blocks are skipped), used as `u.delta(D, S)`.

**Task-local home (protocol step 1).** 6d1d5c90, as `DirCycle`'s linear successor
(below).

## `DirCycle` — a dense line closed into a cycle

The 1D-cycle peer of `DirFrame`, same `dir(d: Dir)` parameter: where `DirFrame`
seats an index in a line measured from an edge, `DirCycle` walks a line closed into
a loop advancing toward an edge. Given a node set on an axis it builds the cyclic
`succ` — linear step toward `dir`, plus a wrap from the `dir`-extreme back to the
far extreme — counts its own length, and exposes `walk`.

```
.comp DirCycle {
    .decl node(p: Position)
    .decl dir(d: Dir)                    // advance direction

    .init u = UnitStep
    .decl succ(p: Position, q: Position)
    succ(P, Q) :- node(P), dir(D), u.delta(D, S), compose(P, S, Q), node(Q).       // step toward dir
    succ(P, Q) :- node(P), dir(D), dist(P, D, 0),                                  // wrap:
                  node(Q), opposite(D, O), dist(Q, O, 0).                          //  dir extreme -> far extreme

    .init cyc = Cycle<Position>
    cyc.succ(P, Q) :- succ(P, Q).
    cyc.step(N)    :- L = count : { node(_) }, N = range(0, L).   // every advance the cycle allows

    .decl walk(p0: Position, n: number, p: Position)
    walk(P0, N, P) :- cyc.walk(P0, N, P).
}
```

**Composed, not new machinery.** `step_delta` (via `UnitStep`) supplies adjacency;
`Cycle` supplies `walk`; `DirCycle` adds only the wrap edge and the length count.

**Dense line.** Like `DirFrame`'s dense `dist_set`, `DirCycle` assumes the nodes
form a contiguous line — the unit-step `succ` needs each interior node's neighbor
present. A sparse set dead-ends mid-line (a covering-relation `succ` would be the
sparse variant); a cyclic shift is dense, so this contract fits.

**Task-local home (protocol step 1).** 6d1d5c90: `node` is each row (an `in` cell
split onto the shift axis), `dir` the shift direction, `walk(row, M)` the rotation.

## Region & shape toolkit

Five comps carried by 3b4c2228 compose into a shape-detection stack — `Reframe`
(position algebra, the inverse of `compose`), `Components` and `Bbox` (find and
frame regions), `Occurrences` (`Reframe` + `KeyedSetCompare`, "find this shape"),
and `Diagonal` (a corner diagonal). They're grouped below with their siblings
`Reach` (seeded connectivity) and `DiagPlacement` (quadrant geometry). The two
3b4c2228 detectors show the wiring:

- `$Object` = `Components` → `Bbox.margin` → `Reframe` → `KeyedSetCompare.equals`
  (each connected component, reframed into its box, set-equal to the shape).
- `$Placement` = `Occurrences` (every footprint placement covering the shape).

They diverge on touching copies — `$Object` merges them into one component,
`$Placement` counts placements separately — which is why both earn a model.

### `Reframe<Key>` — keyed inverse of compose

`compose(outer, inner, grid)` builds a grid position from an outer origin and an
inner offset. `Reframe` runs it backward: per key, an `outer` origin and the
`cell`s to view from it give `inner = cell − outer`. Outer extent + inner extent =
cell extent, so the one subtraction both resizes and repositions — it moves a cell
between frames of different size, not just within one.

```
.comp Reframe<Key> {
    .decl outer(key: Key, p: Position)
    .decl cell(key: Key, p: Position)

    .decl sub(p: Position, q: Position, d: Position) inline
    sub([T1, B1, L1, R1], [T2, B2, L2, R2], [T1-T2, B1-B2, L1-L2, R1-R2]) :- true.

    .decl inner(key: Key, p: Position)
    inner(K, I) :- cell(K, P), outer(K, O), sub(P, O, I).
}
```

**One origin per key.** `outer` is one position per key — the frame each key's
cells are viewed from. Feeding several `outer`s under one key cross-products
(every cell against every outer); the honest way to use that is to key by the
thing varied so each key keeps one origin (see `Occurrences`' candidate-gen).

**Encapsulates `sub`.** Position subtraction (compose's inverse) has no standalone
meaning worth a solver-scope relation; `Reframe` is its home. Candidate-placement
generation collapses to it too — keyed by shape cell, "align each shape cell to
each cell" *is* a reframe, needing no comp of its own.

**Composes with `Bbox`.** `Bbox.margin` is exactly an `outer` — feed it to express
a cell set in its own bounding frame (3b4c2228 `$Object`).

**Task-local home (protocol step 1).** 3b4c2228 — both detectors reframe:
`$Object` views each component from its box margin; `$Placement` (via
`Occurrences`) views cells from each candidate placement.

### Connectivity — `Reach` / `Components`

Two readouts of 4-adjacency closure over a node set. `Reach` returns one component
from a seed; `Components` labels every component. Both share `step` (unit
4-adjacency); an 8-adjacency variant or a parameterized adjacency input is the
obvious extension when a task needs diagonal connectivity.

```
// One component: closure of 4-adjacency from seeds.
.comp Reach {
    .decl node(p: Position)
    .decl seed(p: Position)

    .decl step(delta: Position)
    step([-1, 1, 0, 0]). step([1, -1, 0, 0]). step([0, 0, -1, 1]). step([0, 0, 1, -1]).

    .decl reach(p: Position)
    reach(P)  :- seed(P).
    reach(P2) :- reach(P1), step(D), compose(P1, D, P2), node(P2).
}

// Every component, each labeled by an opaque id.
.comp Components {
    .decl node(p: Position)

    .decl step(delta: Position)
    step([-1, 1, 0, 0]). step([1, -1, 0, 0]). step([0, 0, -1, 1]). step([0, 0, 1, -1]).

    .decl conn(p: Position, q: Position)
    conn(P, P)  :- node(P).
    conn(P, Q2) :- conn(P, Q1), step(D), compose(Q1, D, Q2), node(Q2).

    .decl label(p: Position, id: CompId)
    label(P, $Comp(Min)) :- node(P), Min = min ord(Q) : { conn(P, Q) }.
}
```

**Seeded vs labeled.** `Reach` fits when there's a natural anchor and one
component matters — the seed selects it and is the closure's base case (1e81d6f9:
a corner-edge seed picks the L frame, the stray mask cell stays unreachable, so a
following `Bbox` doesn't inflate to span it). `Components` fits when every
component counts (3b4c2228 `$Object`: each 2×2 is its own component); it is the
"task wanting all components" the seeded form can't serve.

**Opaque label.** A component's id is a sealed token, `.type CompId = Comp { tag:
number }`, off the lowest-`ord` member cell. The type stops it being read as a
`Position`, which would leak the (arbitrary) representative's coordinates in as
orientation. `ord` gives an arbitrary but within-run-stable order, so the pick
carries no geometry. Identity needs a *member cell* — distinct components have
disjoint cells, so it's injective; the bounding box would alias two components
sharing a box (interleaved diagonals under 8-adjacency), which is why
`Bbox.margin` is placement, not identity.

**The bar.** Connectivity recurs across a large fraction of ARC — clears the lib
bar on sight.

### `Bbox<Key>` — keyed bounding box

Bounding box of a keyed cell set, with two readouts: `margin` (the box as a
Position — min distance from each edge to the box) and `inside` (grid cells within
the box). `margin` feeds `Reframe` as the outer origin; `inside` is the membership
test. Keying lets one instance box many sets at once (per-component, per-placement);
single-set sites pass a constant key.

```
.comp Bbox<Key> {
    .decl cell(key: Key, p: Position)
    .decl grid(key: Key, p: Position)

    .decl cell_dist(key: Key, d: Dir, k: number)
    cell_dist(K, D, Kd) :- cell(K, P), dir_elem(D), dist(P, D, Kd).

    .decl edge_min(key: Key, d: Dir, m: number)
    edge_min(K, D, M) :- cell_dist(K, D, _), M = min Kd : { cell_dist(K, D, Kd) }.

    // The box as a Position — margin from each edge. Feed to Reframe as outer.
    .decl margin(key: Key, p: Position)
    margin(K, [Mt, Mb, Ml, Mr]) :-
        edge_min(K, TOP, Mt), edge_min(K, BOTTOM, Mb),
        edge_min(K, LEFT, Ml), edge_min(K, RIGHT, Mr).

    // Grid cells inside the box — at least the margin from every edge.
    .decl inside(key: Key, p: Position)
    inside(K, P) :-
        grid(K, P),
        dist(P, TOP, T),    edge_min(K, TOP, Mt),    T >= Mt,
        dist(P, BOTTOM, B), edge_min(K, BOTTOM, Mb), B >= Mb,
        dist(P, LEFT, L),   edge_min(K, LEFT, Ml),   L >= Ml,
        dist(P, RIGHT, R),  edge_min(K, RIGHT, Mr),  R >= Mr.
}
```

**margin vs inside.** Both read the same four edge-mins. `margin` packs them into
a Position — the box's placement, the `Reframe` origin (3b4c2228 `$Object`).
`inside` tests grid cells against them — the erase-outside-box move (1e81d6f9).

**Why min-per-edge, not min/max-per-axis.** min-dist-to-TOP and min-dist-to-BOTTOM
pin the vertical band as tightly as min/max-dist-to-TOP would, and the four mins
are already a Position — so `margin` falls out without a separate assembly, and
`inside` is symmetric across the four edges. The edge choice washes out under D4
(the box transforms with the grid); `step`'s unit deltas in Reach/Components are
the same kind of internal literal.

**Composition.** `inside` over `Reach`/`Components` isolates a blob and takes its
extent; `margin` → `Reframe` expresses it in its own frame. Both are everyday ARC
operations — lib-worthy alongside connectivity.

### `Occurrences` — find a shape among cells

Placements where a shape's footprint lands fully on a cell set — the ARC "find
this shape" move, as a composition of `Reframe` and `KeyedSetCompare`. Candidate
placements come from aligning each shape cell to each cell (a `Reframe`); each is
verified by viewing the cells from it (another `Reframe`) and testing the shape
against that view (`KeyedSetCompare.covers`).

```
.comp Occurrences {
    .decl cell(p: Position)
    .decl shape(p: Position)

    // Candidate placements — align each shape cell (one origin per key) to every
    // cell, union over the shape cells.
    .init align = Reframe<Position>
    align.cell(S, P)  :- shape(S), cell(P).
    align.outer(S, S) :- shape(S).
    .decl placement(p: Position)
    placement(M) :- align.inner(_, M).

    // View the cells from each placement and test the shape's footprint.
    .init view = Reframe<Position>
    view.outer(M, M) :- placement(M).
    view.cell(M, P)  :- placement(M), cell(P).

    .init matcher = KeyedSetCompare<Position, Position>
    matcher.pattern_member(0, S)  :- shape(S).
    matcher.observed_member(M, I) :- view.inner(M, I).

    .decl occurrence(p: Position)
    occurrence(M) :- matcher.covers(M, 0).
}
```

**Backward, not forward.** Placements come from the data (`cell ⊖ shape-cell`),
not from enumerating a placement frame. So `Occurrences` needs only `cell` +
`shape`, never the grid bounds, and its work scales with the cells present, not
the grid area. Off-grid candidates self-filter — their footprint cells aren't in
`cell`, so `covers` fails. (Forward — slide a placement frame — is the same model,
read with the bound supplied; the binding pattern is the only difference.)

**Policy is `covers`, here.** The observed set per placement is *all* cells viewed
from M, for which only `covers` (shape ⊆ footprint cells) is meaningful — extra
viewed cells outside the footprint don't affect it. `within` / `equals` / overlap
would need the observed set restricted to the footprint region; that's a
window-local variant, not this one, and `matcher` is the seam where it'd plug in.

**Task-local home (protocol step 1).** 3b4c2228 `$Placement`: occurrences of the
2×2 block shape among the color's cells — a distinct model from a `Components`
detector (they diverge on touching copies), not an alt impl.

### Diagonal geometry — `Diagonal` / `DiagPlacement`

Position predicates for diagonal/quadrant geometry, in components so they can name
axes directly. `Diagonal` is the base — cells equidistant from a corner's two
edges; `DiagPlacement` gates and extends it.

```
// Cells on the diagonal through a corner — equal distance to the corner's two
// edges; ring is that shared distance. The ungated diagonal (center included).
.comp Diagonal {
    .decl cell(p: Position)
    .decl corner(d: DiagDir)

    .decl diagonal(p: Position, ring: number)
    diagonal(P, K) :-
        cell(P), corner(Diag),
        dir_of(Diag, VERTICAL,   Dv), dist(P, Dv, K),
        dir_of(Diag, HORIZONTAL, Dh), dist(P, Dh, K).
}

.comp DiagPlacement {
    .decl cell(p: Position)

    // Strictly nearer edge d than its opposite — which side of the axis midline.
    .decl nearer(p: Position, d: Dir)
    nearer(P, D) :-
        cell(P), dir_elem(D),
        dist(P, D, K), opposite(D, Opp), dist(P, Opp, K2), K < K2.

    // The diagonal quadrant a cell sits in: nearer on both of that corner's edges.
    .decl quadrant(p: Position, diag: DiagDir)
    quadrant(P, Diag) :-
        dir_of(Diag, VERTICAL,   Dv), nearer(P, Dv),
        dir_of(Diag, HORIZONTAL, Dh), nearer(P, Dh).

    // On the diagonal of its quadrant, at ring K — the shared distance to both
    // edges of that corner.
    .decl diag_cell(p: Position, diag: DiagDir, ring: number)
    diag_cell(P, Diag, K) :-
        quadrant(P, Diag),
        dir_of(Diag, VERTICAL,   Dv), dist(P, Dv, K),
        dir_of(Diag, HORIZONTAL, Dh), dist(P, Dh, K).
}
```

**`Diagonal` is the base; `diag_cell` gates it.** `DiagPlacement.diag_cell` is
`Diagonal.diagonal` ∩ `quadrant` — the corner→center *ray* (it drops equidistant
cells, which sit in no quadrant). `Diagonal` alone is the full corner-to-corner
diagonal. So the two diagonal uses across solvers are the gated ray (ca8de6ea's
X-arms) and the ungated diagonal (3b4c2228's tally) — distinct relations, not one
repeated.

**Why a component, not loose body relations.** Two body constraints push it into a
`.comp`. A solver body can't name `VERTICAL`/`HORIZONTAL`, so reading a corner's
two perpendicular components there needs two `dir_of` rows plus an `A1 != A2`
disequality; inside a component (as `corner_anchor` does in lib) the axes are
named directly and the disequality is gone. And `nearer` is used under negation
(`in_center :- ..., !nearer(...)`), which Souffle can't do to an `inline`
relation — but a component's non-inline relations negate fine. The component
settles both at once.

**Task-local homes (protocol step 1).** 3b4c2228 carries `Diagonal`, fed the 3×3
output frame and the tally corner; `$Tally` reads `diagonal(P, ring)` and marks
rings below the count. ca8de6ea carries `DiagPlacement`, fed input ∪ output-ring
cells: `quadrant` keys each X-arm cell and ring corner to its diagonal, `diag_cell`
adds the ring feeding the per-ring `Cycle` shift, and `in_center` negates `nearer`.

**`nearer`** is the base of `DiagPlacement` — which side of the axis midline a cell
sits on — and reusable past diagonals (half-plane tests, center detection).

**Open.** `nearer`, `quadrant`, and `Diagonal` are unambiguously general (the
equidistance test is also the fixed set of the corner's diagonal flip). `diag_cell`
(the gated ray) still has one home — worth a second before a lib slot.

