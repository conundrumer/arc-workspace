# `LatticeOrbit<Key>` — the cells a translation lattice identifies

The positions a run of period-sized shifts reaches from a seed without
leaving the frame: given the per-axis periods of a pattern, `orbit` pairs
each seed with the cells that hold the same content under the lattice.
`ShiftInvariance.min_period` or a stored period feeds `period` directly.
A caller repairing damage seeds the damaged cells and reads an intact
counterpart; a caller extending a pattern over the whole frame seeds every
cell; a caller stamping a motif seeds the stamp.

```
.comp LatticeOrbit<Key> {
    // The frame the orbit stays inside, per key.
    .decl cell(key: Key, p: Position)           // input
    // The lattice's period along each axis, per key.
    .decl period(key: Key, a: Axis, k: number)  // input
    // The positions the orbit runs from, per key.
    .decl seed(key: Key, p: Position)           // input

    // One lattice shift, either way along its axis, landing in the frame.
    .decl step(key: Key, p: Position, q: Position)

    // q is reached from seed p by a run of steps. Reflexive on the seeds.
    .decl orbit(key: Key, p: Position, q: Position)
}
```

- An axis with no period contributes no shift, so a lattice on one axis
  alone is the caller stating one period row.
- The frame clips every step, so the orbit of a seed is the seed's
  congruence class inside the frame and nothing else.

Not: which shifts a set is invariant under (`ShiftInvariance`); isometries
beyond translation (`Wallpaper`); a single stored jump with no closure
(`jump`); a flood over adjacency (`Reach`); an advance of a stored step
count along a cycle (`CycleWalk`).

Match: a recursive relation over positions whose step composes a
period-sized delta and clips the result to the frame — `compose` against a
`jump_delta` or a stored `Shift` in a rule whose head it also reads. Grep:
`jump_delta`, `period_delta`, `compose(.*Delta`, `stride(`.

Survey: 2026-09-05 13:36

Callers: 017c7c7b `fill`, 13f06aa5 `paint` (served once `cell` is clipped
to the ray), 135a2760 `orbit.equiv`, 16de56c4 `lattice`/`advance`,
1ae2feb7 `claim`, 1d0a4b61 `step` with its recursive `out`, 29ec7d0e
`restored`, 332efdb3 `$Motif`, 484b58aa `orbit`, 50a16a69 `period_step`
with `orbit`, 53b68214 `out`, 834ec97d `$Period` `beam`, 8eb1be9a `out`,
963e52fc `out`, ca8f78db `period_delta` with `peer`, d492a647 `$Period`
`lattice`, 53fb4810 `pattern` (served once `cell` is clipped to the
band's growth side of its anchor), 58490d8a `slot` (served under
`$FromMark` once `cell` is clipped to the ray), 6a980be1 `strip_out` (the
strip's content seeded, its `min_period` along the line axis, the whole
grid as frame).

Near: 0b17323b `$Line`, 05269061 `known`, 3979b1a8 `out`, c1990cce
`emitter` run a lattice whose generator is diagonal, and 5207a7b5
`region` one whose generator is oblique — one cell across an axis and
`rise` cells along it. 045e512c `copy`, 12422b43 `$Stamp` `copy`,
13f06aa5 `paint`, c1990cce `emitter`, 3979b1a8 `out` run their period one
way only; for 045e512c and 12422b43 the backward half lands on the
content the run copies from. 4acc7107 `lane` and `slot` run a clipped
chain of jumps whose step length is the previous element's size, so no
period holds it. 0dfd9992 `Wallpaper.step`, 1b60fb0c `orbit`, 47c1f68c
`unfold` close over isometries, and 30f42897 `$Period`, 195c6913 `walk`,
46c35fc7 `cycle.walk` advance a step count along a cycle.
Phase-into-a-table sites (ba26e723, 221dfab4, 34cfa167, 97999447,
c1990cce `$Stripe`, 516b51b7 `$Cycle` over an erosion depth, and seven
more) read the residue as a number with no seed and no closure, and
lattice-as-division sites (332efdb3 `$Stripes`/`$Inset`, 305b1341,
1c0d0a4b, 695367ec) anchor the lattice on the frame with `divide_by_size`.

Spec: `period`'s axis column would widen from `Axis` to `Axis4`. Four
sites state a diagonal generator, and 0b17323b `$Line` is the operation in
full but for the axis type. `axis4_of`, `diag_axis_of`, and `jump_delta`
over `Dir8` cover both kinds in one step rule, and the widening costs the
16 callers nothing: `ShiftInvariance` yields cardinal rows, and the
stored-period callers set an `Axis` as before. The orbit stays undirected
and `step` stays public: a caller wanting one side clips `cell`
(13f06aa5), and 16de56c4 reads `step` alone for its halting variant. The
period enters as `(a, k)`, the form `ShiftInvariance.min_period` produces
and `jump_delta` consumes; the two sites holding it as a `Shift`
(332efdb3, 16de56c4) convert at the call. An oblique generator fits
neither form: 5207a7b5 is the one site that asks for a `Shift`-typed
generator, and no other caller or near-miss needs one.

Survey: 2026-09-08 12:00, over the 183 solvers postdating the survey above
that it does not already name.

Delta callers: none. `jump` appears at eleven sites in that scope, each a
single application under no head recursion, and `ShiftInvariance` appears
nowhere in it.

Delta near: 351d6448 `wave` closes a stored velocity forward and backward
with `compose`, but each step also advances a panel index, so the run is
over (panel, cell) pairs across a panel sequence and the velocity is the
animation's, not a period of the content. 447fd412 `carry` runs a K-sized
`jump` whose step is driven by one-cell template adjacency, so the closure
is a two-frame scale correspondence that no single-frame period holds.
1c56ad9f `Parse.phase` folds a distance into a stored period with `stride`
and reads the residue into a table. 539a4f51 advances a shell index around
`IndexCycle`, so its period lives in ring index rather than in a
translation. 3bdb4ada `ink_run`, 363442ee `$Tile`, and 456873bc anchor
their period on a box or on the grid with `divide_by_size`. 4852f2fa
`place` builds its repeated copies with `concat_slab` over an `AxisFrame`
rather than reaching them.

Delta spec: the scope adds no support for widening `period`'s axis column
to `Axis4`, and one caution against it. Its diagonal sites run at period 1
— 4aab4007 repairs a wallpaper cell from an intact one and 4c7dc4dd
`spread` chains constancy across both diagonal families, both with
`same_line` — and at period 1 the operation degenerates into `same_line`,
which states the whole line in one atom with no closure. 1e97544e `flow`
is the scope's one diagonal closure, and its content changes per step, so
it is no orbit under any axis type. On the generator's type, 351d6448
`wave` is a second site after 5207a7b5 carrying a free `Shift` through a
closure; it is no caller, so it does not settle the question.

Survey: 2026-09-09 00:25, over the 236 solvers postdating the survey above.

Delta callers: none beyond 58490d8a, the solver that dispatched this survey.
The grep signature matches 76 lines in 33 files of that scope and the shape
signature 39 rules in 28 files, and 19 of those files the entry already names.
`ShiftInvariance` appears at eleven sites in scope, all named but c3f564a4.

Delta near: c3f564a4 `out` under `$Shift` applies one `si.cand` shift to a noise
cell with no head recursion, and its header states that the period varies per
pair, so it carries no `$Period` case; its sibling ca8f78db keeps the closure and
is a caller. 08573cc6 `arm` rotates and lengthens the previous step's delta, and
234bbc79 `trail_dest` takes each piece's displacement from where the piece before
it landed, so both change the generator per step, the 4acc7107 class. 17829a00
`reach` and 56dc2b01 `reach` close in Shift space over one-cell steps that a
stopper ends — the "Slide until halted" pattern, not a period. 2546ccf6 `reflect`
closes over mirrors in the divider cuts. 2601afb7 `Parse.next_bar` steps around
`IndexCycle` over bar ranks, the 539a4f51 class. 13e47133 `out` reads a `stride`
residue of an erosion depth into a palette table, the phase-into-a-table class.
47996f11 `counterpart`, 3345333e, 5751f35e, 4c5c2cf0, and 18419cfa repair through
D4 images. 1b59e163 `paint`, 1caeab9d `moved`, 20981f0e `moved`, 20fb2937 `paint`,
247ef758 `paint`, 264363fd `carried`, and 48634b99 `target` each compose one
computed displacement with no closure.

Delta spec: the scope adds no support for widening `period`'s axis column to
`Axis4`, and one further caution. c3f564a4 `$Diag` is a diagonal-stripe wallpaper
stated as `params.diag(DA), same_line(DA, P, Q)` — period 1 along the diagonal,
where the operation degenerates into `same_line`, as the delta above records for
4aab4007 and 4c7dc4dd. The scope's other diagonal sites (1f876c06, 55059096,
55783887 `span`, 54dc2872, 1d61978c) cast or count along diagonal lines under no
period. On the generator's type, 08573cc6 `arm` and 234bbc79 `slide` carry a free
`Shift` through a closure, after 5207a7b5 and 351d6448, but both change that
`Shift` each step, so neither settles the question; 5207a7b5 stays the one site
asking for a `Shift`-typed generator.

Survey: 2026-09-09 00:36, over the 2 solvers postdating the survey above.

Delta callers: none, including 58e15b12, the solver that dispatched this
survey. The grep signature matches three lines in the scope and the shape
signature one rule; `jump_delta`, `period_delta`, `ShiftInvariance`, and
`min_period` appear nowhere in it.

Delta near: 58e15b12 `trace` carries a bar cell one bar length along the bar
axis and one cell across it, clipped to the frame. Two exclusions each rule it
out on their own. Its generator is oblique, which `period`'s `(a, k)` form
cannot state — the 5207a7b5 class. And it runs that generator one way only,
which clipping `cell` does not recover: the across direction is fixed at the
seed while the along direction ranges over both, so the reached set is the
forward halves of two distinct generators, and each backward half runs across
the bar pair onto the other bar's side rather than overshooting one end. That
is stricter than the 045e512c / 13f06aa5 one-way class, whose unwanted half a
clip removes. 58c02a16 `phase` folds a cell's two distances from a stored
corner into the block extent twice with `stride` and reads the residues back
through `diag_dist`: the lattice-as-division class, anchored on the pattern box
rather than on the frame, with no seed and no closure. Its coarse level is no
orbit at any period either — the cells sharing a coarse residue span `N`
consecutive residues — and the program consumes the quotient, which no orbit
yields.

Delta spec: the scope adds no support for widening `period`'s axis column to
`Axis4`; both of its lattices are cardinal. On the generator's type, 58e15b12
`trace` is the second site after 5207a7b5 carrying a constant oblique generator
through a closure, and unlike 351d6448, 08573cc6, and 234bbc79 it holds that
generator fixed across steps. It still does not settle the question. A
`Shift`-typed generator alone would not serve it, because it also needs a
directed run and the clip the spec relies on is unavailable. And its generator
is per-key derived data — the length off the color's bbox, the direction pair
off direction enumeration — so it asks for a keyed `generator(key, delta)`
input, where 5207a7b5's `params.slant` is a stored `Shift`. 5207a7b5 stays the
one site asking for the `Shift`-typed generator the operation as specified
would serve.

Survey: 2026-09-09 00:47, over the 3 solvers postdating the survey above,
58c02a16 among them for its edit after that survey.

Delta callers: none. The scope holds one head-recursive rule and one lattice,
each excluded below. `jump_delta`, `period_delta`, `compose`, `ShiftInvariance`,
and `min_period` appear nowhere in it.

Delta near: 5961cc34 `live` closes a current forward along `feeds`, the edge
relation pairing an object with the object its port's beam lands on. That
closure runs over object ids rather than positions, and each edge's length is
whatever the field leaves between two objects, so no fixed delta generates a
step — the graph-reachability class. 58c02a16 `phase` stands as the delta above
records it, and its current form sharpens that exclusion twice: its lattice is
anchored on the frame corner `params.corner` stores rather than on a seed set,
and its coarse level takes the fine level's quotient as its own input, so the
program consumes a quotient, which no orbit yields. 58f5dbd5 runs no lattice and
no closure; its one delta site lets a bounding box out by the border width with
`uniform_delta`, a single placement.

Delta spec: the scope adds no support for widening `period`'s axis column to
`Axis4`. Its one lattice is cardinal on both levels — `diag_dist` splits the
corner distance into two cardinal-axis components, and each is folded on its own
axis. That site is mild support for the `(a, k)` period against a `Shift`,
because it reads its period straight out of `block.extents($U(), A, N1, N2)`,
the form `ShiftInvariance.min_period` produces; it is a near-miss, so it does not
settle the question. The scope holds no site carrying a free `Shift` through a
closure, so 5207a7b5 stays the one site asking for that generator.

Survey: 2026-09-09 03:07, over the 26 solvers postdating the survey above.

Delta callers: none, including 5e6bbc0b, the solver that dispatched this
survey. The grep signature matches six lines in three files of that scope and
the shape signature no rule; `period_delta`, `ShiftInvariance`, and
`min_period` appear nowhere in it.

Delta near: 5e6bbc0b `block_cell` under `$Parity` takes the frame cells whose
corner distance shares the mark's residue, which pairs a seed with that seed's
class as a cell set — the operation but for `period`'s axis type, and the delta
spec below reads it. 5c2c9af4 `outline` closes one constant delta, but that
delta is an `Inset` dilating a box rather than a translation, the ground
`Concentric` names this entry on and the class it claims 5c2c9af4 for.
4ff4c9da `reached` closes over blob ids along the relation pairing blobs that
share their rows or their columns, the graph-reachability class of 5961cc34
`live`, which the 00:47 delta records and whose edit put it back in scope.
56dc2b01 `shift` closes in Shift space over one-cell steps an anchor line ends,
now through lib's `Slide` — the slide-until-halted class the 00:25 delta
records for it. 5adee1b2 `outside` floods over adjacency and 1190bc91 `arm`
casts a blocked ray. 5d588b4d `place` folds a sequence rank into the output
width and consumes the quotient as a line index, the lattice-as-division class,
which 5ad4f10b and 5a5a2103 also run, anchored on a box or on the grid with
`divide_by_size`, `divide_2d`, and `Tile2D`. 5af49b42 `stamp`, 5dbc8537
`covers`, 5b526a93 `covered`, 5b692c0f `mirrored`, 409aa875 `shot`, and
58f5dbd5 `view` under `$Arrange` each apply one displacement with no closure.

Delta spec: the scope holds the first support for widening `period`'s axis
column to `Axis4`, and it rests on 5e6bbc0b alone. That solver's `$Parity` runs
period 1 along both diagonal families at once, where every diagonal site the
deltas above cite — 4aab4007, 4c7dc4dd, and c3f564a4 `$Diag` — runs one family:
on its `train0 input` the two `same_line` atoms through the mark give five
cells against the class's fifteen, so no `same_line` form replaces the closure
and the degeneration ground does not reach it. Two qualifications sit beside
it. The widened operation would not serve that case as parameterized: `$Parity`
stores a period over corner distance, and a diagonal lattice reaches only
displacements whose two coordinate changes differ by an even number, so the
residue class is an orbit for an even period alone, at `(DAXIS_AD, 1)` and
`(DAXIS_DG, N/2)`; at this task's period 2 both are 1, which spends the case's
one parameter on unit literals and narrows its family to the checkerboard, a
different model under the same-model test rather than another encoding of that
one. And the support is the surfacing solver's own, so it stands as a
caller-only reading rather than as a change. On the generator's type, 5c2c9af4
`outline` is the scope's one further closure over a constant free delta, and
`Concentric` claims it, so 5207a7b5 stays the one site asking for the
`Shift`-typed generator.

Survey: 2026-09-10 00:39, over the 317 solvers postdating the survey above.

Delta callers: none beyond 6a980be1 `strip_out`, the solver that dispatched
this survey, which stands caller-only: it seeds `strip_in` (the strip's
content inside the frame), takes `strip_shift.min_period($U(), A, K)` on the
line axis, steps with `axis_of(D, A), jump(P, D, K, P2)` either way, and
clips with `in(P2, _)` — the whole grid as frame — in a rule whose head it
reads. The grep signature matches 71 lines in 34 files of that scope, 29 of
them files the entry already names, and the shape signature 16
head-recursive rules in 13 files plus 9 delta-built rules on an indirect
positive cycle in 8 files; each unnamed hit is excluded below.
`period_delta` and `LatticeOrbit` appear nowhere in the scope;
`ShiftInvariance` and `min_period` appear only in named files.

Delta near: 28e73c20 `walk` closes a spiral one `neighbor` step at a time,
turning on a box's margins and letting that box out by `params.inset` with
`compose` at each closed cycle, so its constant delta is an `Inset` dilating
a box and its translation is unit and turning — the `Concentric` class of
5c2c9af4 `outline` joined to the walk class. 4e34c42c `place` closes over
fragment ids along `join`, each edge carrying that pair's fitted `Shift`, so
the generator varies per edge — the graph-reachability class of 5961cc34
`live`. 60d73be6 `image` closes over the two flips of a cross, seated by
`displacement`/`apply`/`compose` around each line, and 6165ea8f `slot`
transposes through `diag_flip_of` — isometries, the 2546ccf6 `reflect`
class. 142ca369 `enter` heads a ray walk that reflects off walls one
`neighbor` step at a time; its `compose` sites place a glyph and its launch
cell once. 5ffb2104 `Settle.room` composes each body's `rest` into the room
the body behind it has, with `jump_delta` to the frame edge as one
placement — the slide-until-halted class of 17829a00 and 56dc2b01, closed
over bodies rather than positions. 05f2a901 and 11dc524f `shift`, and
17829a00 `shift` and 47996f11 `cand` as recorded, enumerate every axis-aligned
`jump_delta` of the frame with `sub_extent` as move candidates, with no seed
and no closure. 6350f1f4 `template` overlays blocks on their intile position
under a `DividerFrame` and a `BoxFrame`, the lattice-as-division class
anchored on the separator lines rather than on a seed, with no closure; its
`repair` sibling 4290ef0e `mirror` repairs through a center reflection.
22233c11 `echo_cell`, 22208ba4 `moved_cell`, 3631a71a `mirror`, 4364c1c4
`moved`, 5168d44c `target`, 11dc524f `mirror`, 18447a8d `landed`, 320afe60
`paint`, 62593bfd `paint`, 5623160b `ink`, 5521c0d9 `moved`, 64a7c07e
`landed`, 337b420f `covered`, 39e1d7f9 `footprint`, and 414297c0 `glyph`
each apply one displacement with no closure.

Delta spec: the scope adds no support for widening `period`'s axis column
to `Axis4`. Its unnamed diagonal sites carry no period: 22233c11 `echo_cell`
jumps a quadrant one quadrant-length along its corner diagonal once, 142ca369
walks diagonal rays cell by cell, and 22425bda `collinear` tests
`same_line` over `axis4_elem` with no step. The one new site whose seed,
period, and frame all match the operation is the surfacing solver, whose
period is cardinal and comes as `(a, k)` straight from
`ShiftInvariance.min_period`, the form the spec fixes; that supports the
`(a, k)` period against a `Shift`, and as the surfacing solver's own reading
it stands as caller-only. On the generator's type, the scope's closures over
a free delta all change it per step (4e34c42c `place`) or dilate rather than
translate (28e73c20 `walk`), so 5207a7b5 stays the one site asking for the
`Shift`-typed generator.

Survey: 2026-09-10 03:04, over the 329 solvers postdating the survey above.

Delta callers: 7447852a `$Stamp` `mark_cell`, the solver that dispatched
this survey, which stands caller-only. The grep signature matches 87 lines
in 42 files of that scope, 37 of them files the entry already names, and
the shape signature 41 rules in 32 files, 21 of them named; each unnamed
hit is excluded below. `period_delta` and `LatticeOrbit` appear nowhere in
the scope; `ShiftInvariance` and `min_period` appear only in 6a980be1 and
in the caller's Determine comp.

Callers: 7447852a `$Stamp` `mark_cell` — seeds the stored `params.stamp`
mask seated on the anchor edge (`params.anchor(D), slab_anchor(D, Pm, Q)`
over `in(Q, _)`), takes its period as the stored scalar `params.period(K)`
on the anchor's axis (`axis_of(D, A)`, so the row is `(A, K)`), steps
either way along that axis with `axis_of(O, A), jump(Q, O, K, Q2)`, and
clips with `in(Q2, _)` — the whole grid as frame — in a rule whose head it
reads. Its Determine comp reads the period back as
`si.min_period(_, A, K)` from `ShiftInvariance` over `ex_out`.

Delta near: 6ad5bdfd `Settle.room` is the 5ffb2104 `Settle.room` site
under a second solver: each body's `rest` composes into the room the body
ahead leaves, with `jump_delta` to the frame edge as one placement — the
slide-until-halted class closed over bodies. 6cbe9eb8 `obox`/`anchor` chain
nested boxes along `nest.next`, each step's `displacement` read off the
previous box's corner cell, so the generator changes per step — the
4acc7107 class. 5587a8d0 `covers`/`inside` grow each ring from the one
inside it by one `dir8_elem` `neighbor` step in Shift space, a dilation —
the `Concentric` class of 5c2c9af4. 212895b5 `turtle` steps one `neighbor`
along a heading and turns it by the gait's phase each step, around
`IndexCycle`; 69889d6e `walk` alternates unit steps along a corner's two
directions and turns in place when blocked; 508bd3b6 `beam` runs a diagonal
unit-step beam that walls bounce; 36a08778 `wet` runs a unit-step pour that
blocks halt and re-seeds beside them; 89565ca0 `line` carries a frame line
one `neighbor` under a hiding cell when the two cells behind it carry it;
3d6c6e23 `cone` spreads one `neighbor` toward the floor and its two diagonal
corners per step, inside the grid; 6df30ad6 `Dilate.depth` grows outward
from seeds one step per ring — all unit-step walks or floods under no
period, the 28e73c20 / 142ca369 / `Reach` classes. 6d0160f0 `tile` anchors
its 3×3 lattice on the grid with `divide_by_size_2d`, the
lattice-as-division class, with no closure. 6ffbe589 `rot` advances a
turn count around a rotation cycle with `CycleWalk`, the 30f42897 class.
6ca952ad `flush` and 6e453dd6 `slid` each compose one displacement with no
closure.

Reimplementations: 36a08778 `wet`, `programs/solvers/36a08778.dl` lines
66 and 70, hand-write `Ray.clear` and `Ray.stop` — a cardinal cast from
the pour cells, clipped to `in` and halted by `block` — while the same
file instantiates `Ray<Axis>` for its `$Shell` runs; its marks would come
from the closure itself, since each `barred` cell seeds the next pour one
step aside.

Delta spec: the scope adds no support for widening `period`'s axis column
to `Axis4`. Its diagonal sites carry no period: 508bd3b6 `beam` walks a
diagonal cell by cell and bounces, 3d6c6e23 `cone` spreads by unit diagonal
steps, and 69889d6e `walk` reaches its corner by alternating unit cardinal
steps that obstacles turn. The one new site whose seed, period, and frame
all match the operation is the surfacing solver: its period is cardinal
and stored as a scalar with the axis taken from the anchor direction, so
it feeds the `(a, k)` row with one `axis_of` atom, and its Determine comp
reads that row straight from `ShiftInvariance.min_period` — support for
the `(a, k)` period against a `Shift`, standing as caller-only. On the
generator's type, the scope's closures over a free delta all change it per
step (6cbe9eb8 `obox`, 212895b5 `turtle`) or dilate rather than translate
(5587a8d0 `covers`), so 5207a7b5 stays the one site asking for the
`Shift`-typed generator.
