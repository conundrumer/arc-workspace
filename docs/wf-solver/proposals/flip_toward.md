# `flip_toward` — the D4 element a crossing toward a Dir8 induces

The D4 element that inverts each axis d has a component on: the flip of d's axis for a cardinal, and the half turn for a diagonal. Content that crosses a boundary toward d — a cut, a shared edge, a corner between two cuts — reflects by this element, so a solver that mirrors content across what it crosses reads the element from the direction in one atom. A program cannot state the diagonal row itself: the element is a composition of two flips, lib holds no D4 multiplication, and D4 literals are banned, so solvers restate it as two `apply` steps over a grounded position domain.

```
// The D4 element that inverts each axis d has a component on: the flip of
// d's axis for a cardinal, the half turn for a diagonal.
.decl flip_toward(d: Dir8, t: D4)
flip_toward(D, F) :- axis_of(D, A), flip_of(A, F).
flip_toward(D, D4_HT) :- diag_dir_elem(D).
```

Not: `flip_of` (keyed by the axis that inverts, cardinal only); `diag_flip_of` (the reflection across a diagonal axis line); `apply_dir8` (the action of a given D4 element on directions).

Match: grep `axis_of\(.*flip_of|flip_of\(.*apply\(` for the cardinal form, and prose for the diagonal form: a rule that applies two axis flips in sequence, or branches a mirror on cardinal against diagonal direction.

Survey: 2026-09-08 01:40

Near-misses: `2c181942` `notch` takes `axis_of(D, A), perp(A, A2), flip_of(A2, F)` — the
mirror along side d, which fixes d's axis, the operation's perpendicular; `bd4472b8` reads
`diag_flip_of` from a stored DiagAxis; `be03b35f` stores a DiagDir→D4 table whose entries
are per-quadrant quarter turns, not the both-axes inversion; `4938f0c2` and `4c416de3` use
`apply_dir8`'s diagonal peer on a D4 already in hand; `46c35fc7` reads a D4 off a Dir8
through `rotation`, a turn; `18419cfa` `$Doorway` is axis-driven with no direction.

Spec: no interface change. An `Axis4` key is ruled out: `flip_toward(d)` equals
`flip_toward(opposite(d))`, but every caller holds a direction and no axis — the `axis_of`
atom is exactly the dead weight — and the DiagAxis half would collide with `diag_flip_of`
(same key, a different element). The index sentence's definitional half (invert each axis d
has a component on) carries all callers; two of them (`18419cfa` `$OneSided`, `496994bd`
`$Seat`) read the element off a direction with no crossing, so the crossing sentence is
interpretation, not definition. The diagonal row is exercised only by the surfacing solver.

Callers:

- `67e8384a` `unfold_val` (family: `0c786b71`, `3af2c5a8`, `62c24649`, `833dafe3`) — 2x2
  unfold, each neighbor tile the reflection across the shared edge
- `4c4377d9` `unfold_val` (family: `59341089`, `6d0aefbc`, `6fa7a44f`, `8be77c9e`,
  `bc4146bd`, `c9e6f938`) — the same unfold over a 1D strip
- `8d5021e8` `unfold_val` — 3x2 unfold from a centered anchor tile
- `c48954c1` `unfold_val` — 3x3 unfold from the center tile
- `eb281b96` `unfold_val` — 1D unfold with tiles overlapping by one line
- `47c1f68c` `unfold` — unfold over the quadrants a row and column cut
- `e3497940` `fold_ink` — fold of the far subgrid across the separator
- `11dc524f` `paint` mirror branch — docked shape reflected across the block edge in the
  slide direction
- `2bcee788` `mirror` — shape offset flipped across the wall toward the marker
- `496994bd` `img` `$Seat` — ink block reflected by the flip of its flush edge's axis
- `18419cfa` `flip` `$OneSided` — reflection across the interior midline for the side the
  pattern lies toward
- `2546ccf6` `reflect` — reflection across the cut crossed toward d, the diagonal as two
  chained reflections
- `760b3cac` `mirror` — pattern tile reflected across the shared edge into the neighbor
  tile on the side the marker points to

Survey: 2026-09-10 03:33

Scope: the solvers that postdate the previous survey (`since 2026-09-08 01:40`).

Near-misses: axis-driven mirrors with no direction in hand, as `18419cfa` `$Doorway`:
`2b01abd0` `mirror` (line axis derived from two line cells), `3345333e` `mirror` (stored
mirror axis), `47996f11` `Determine.mirrored`, `538b439f` `image` (divider line),
`5a719d11` `out` (stored pair axis), `5b692c0f` `mirror` (axis bundled with the fold line;
the side joins downstream), `60d73be6` `image`, `66ac4c3b` `painted` (unordered marker
pair), `6f473927` `Parse.place`. `5545f144` `sym_cell` takes the operation's perpendicular,
as `2c181942` `notch`. `6165ea8f` `slot` holds a DiagDir but wants `diag_flip_of`'s
transpose, the DiagAxis collision made concrete. `3a25b0d8` reads `flip_of` inversely off
a D4Map symmetry. `4e7e0eb9` `side_img` composes up to two axis flips on Dirs through
`opposite`, keyed by the divider-axis set, with no D4 element. `4290ef0e` `mirror` is a
point reflection through a center with no direction.

Spec: no change. The two new callers sit one on each half of the index sentence:
`6855a6e4` crosses toward a cast direction; `af22c60d` reads the element off a flush edge
with no crossing, as `496994bd` `$Seat`. In `af22c60d` the Dir8 key would also make the
Axis column of `mirror_band` derivable. The diagonal row is still exercised in program
form only by `2546ccf6` and `47c1f68c` `$Mirror`, which chain two cardinal flips.

Callers:

- `af22c60d` `mirror` (family: `3631a71a`) — masked cell restored by the axis mirror band
  flush with edge d: the flip of d's axis, then a jump onto the band; also
  `Determine.band_map`
- `6855a6e4` `image` — mover cell reflected across the first mirror cell its cast toward
  d meets, by the flip of d's axis
- `47c1f68c` `$Mirror` — a second site of the recorded caller: the flip read off the
  anchor's dir per axis, the two axis flips chained in `paint`
