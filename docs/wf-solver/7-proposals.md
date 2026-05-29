# Proposals

Forward-looking changes to `.dl` style and primitives — a working draft.

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

## `Cycle` — directed cycle with gauge-free rotation

The Z/n cycle species made first-class. `succ` declares a directed cycle by its
edges; `walk(p0, n, p)` advances a start cell n successor steps. The edge set
carries no basepoint, so the cycle is recoverable content and any single
position is gauge — `walk` (a step count, the torsor difference) is gauge-free;
the absolute position is not.

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
applies only a few shifts.

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

**Why a cycle, not `apply(D4)`.** D4 rotations move in 90° steps. A diagonal →
adjacent-cardinal twist is 45°, outside D4, so it can't be an `apply`. Modeling
the destinations as one 8-cycle makes that twist an ordinary single `succ` edge
and keeps the rotation a step count rather than a chosen representative pairing.

**Generalization.** The shift lives in Consts as a Z/n value, so spiral-collapse
siblings (more rings, larger per-ring twist) are a Consts edit. And the cycle is
combinatorial — `succ` follows cell order, not geometry — so an irregular loop (a
closed circuit of arbitrary shape, length not a multiple of 8) flows through
unchanged. A bigger or irregular loop is the honest test that the abstraction
isn't pinned to Chebyshev radius. Dihedral (undirected loop — adjacency without
direction) would be a sibling component if a task needs it.

**Naming.** "Cycle" matches the Z/n cycle species; the sibling project's
color-symmetry analysis uses the same name for the color analog. `walk` names the
advance, `succ` the generating edge.

## Diagonal placement — `nearer` / `quadrant` / `diag_cell`

A dependency chain of position predicates for diagonal/quadrant geometry,
realized as a component so it can name axes directly.

```
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

**Why a component, not loose body relations.** Two body constraints push it into
a `.comp`. A solver body can't name `VERTICAL`/`HORIZONTAL`, so reading a corner's
two perpendicular components there needs two `dir_of` rows plus an `A1 != A2`
disequality; inside a component (as `corner_anchor` does in lib) the axes are
named directly and the disequality is gone. And `nearer` is used under negation
(`in_center :- ..., !nearer(...)`), which Souffle can't do to an `inline`
relation — but a component's non-inline relations negate fine. The component
settles both at once.

**Task-local home (protocol step 1).** ca8de6ea carries a solver-local
`DiagPlacement`, fed `dp.cell(P) :- cell(P)` over input ∪ output-ring cells:
`quadrant` keys each X-arm cell and each ring corner to its diagonal, `diag_cell`
adds the ring that feeds the per-ring `Cycle` shift, and `in_center` negates
`dp.nearer`. The clean axis-named form already runs there.

**`nearer`** is the base — which side of the axis midline a cell sits on — and
reusable past diagonals (half-plane tests, center detection).

**Open.** `nearer` and `quadrant` are unambiguously general. `diag_cell` is
`quadrant` plus a ring readout — general-looking for diagonal/X-structured tasks,
but with one home; worth a second before it earns a lib slot.

## `Reach` / `Bbox` — connected component and bounding box

Two of the most basic ARC operations, and they compose: isolate a blob, take its
extent. Task-local home: 1e81d6f9's `$Bbox` model (keep the corner region's
bounding box, erase the keyed color outside it).

```
// Connected component: closure of 4-adjacency over a node set, from seeds.
.comp Reach {
    .decl node(p: Position)
    .decl seed(p: Position)

    .decl step(delta: Position)
    step([-1, 1, 0, 0]). step([1, -1, 0, 0]). step([0, 0, -1, 1]). step([0, 0, 1, -1]).

    .decl reach(p: Position)
    reach(P)  :- seed(P).
    reach(P2) :- reach(P1), step(D), compose(P1, D, P2), node(P2).
}

// Bounding box of a cell set, classified against a grid of positions.
.comp Bbox {
    .decl cell(p: Position)
    .decl grid(p: Position)

    .decl cell_dist(p: Position, d: Dir, k: number)
    cell_dist(P, D, K) :- cell(P), dir_elem(D), dist(P, D, K).

    .decl extent(d: Dir, lo: number, hi: number)
    extent(D, LO, HI) :- dir_elem(D),
        LO = min K : { cell_dist(_, D, K) }, HI = max K : { cell_dist(_, D, K) }.

    .decl inside(p: Position)
    inside(P) :- grid(P),
        dist(P, TOP,  T), extent(TOP,  Tlo, Thi), Tlo <= T, T <= Thi,
        dist(P, LEFT, L), extent(LEFT, Llo, Lhi), Llo <= L, L <= Lhi.
}
```

**Why `Reach` is seeded.** It returns the component *anchored at the seed*, not
the whole node set. When the nodes form several components (1e81d6f9: the L frame
plus a stray mask cell), the seed selects which one — the stray is unreachable
from a corner-edge seed, so it never enters `reach`, and the bbox stays tight
instead of inflating to span the stray. A task wanting *all* components would use
component-labeling instead; seeded reach fits when there's a natural anchor. (The
seed is also the closure's base case — without it `reach` is empty.)

**Why `Bbox` names `TOP`/`LEFT`.** One reference edge per axis pins a cell's 2D
position; the box is the rectangle spanning the cell set on both. The choice of
edge per axis washes out — `dist`-to-top and `dist`-to-bottom are complementary,
so `BOTTOM`/`RIGHT` define the identical rectangle. It's a gauge pick (some edge
is needed to measure against), not a privileged origin: under D4 the extents
recompute and the box transforms with it. `step`'s unit deltas are the same kind
of internal literal.

**Composition.** `Bbox` over `Reach`'s output is the recurring "isolate a blob,
take its extent" move; 1e81d6f9 wires `box.cell(P) :- region.reach(P)`.

**The bar.** Unlike `diag_cell` (one home), connectivity and bounding box recur
across a large fraction of ARC — these clear the lib bar on sight. `step` (unit
4-adjacency) is the shared sub-primitive; an 8-adjacency variant, or a
parameterized adjacency input to `Reach`, is the obvious extension when a task
needs diagonal connectivity.

**Linter note.** A generic component carries lib-shaped literals (`step` deltas,
`Bbox`'s `TOP`/`LEFT`). A `// lint-ok` marker on the `.comp` header silences them
— the comment-driven analog of how `.comp Consts` is skipped — and they're moot
on promotion to `lib.dl` (which the linter doesn't scan). The flags mark generic
code living in the solver, not a defect.
