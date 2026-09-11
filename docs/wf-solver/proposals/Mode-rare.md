# `Mode.rare` — the least common member

A readout beside `Mode.mode`: the members of a key whose token count is the
lowest, ties kept. `mode` states the same reading at the other end, so one
instance gives both ends of the tally, and a solver that picks the group with
the fewest cells names it the way it names the group with the most.

```
.decl rare(key: Key, m: Member)
rare(Ky, M) :- tally(Ky, M, N), N = min N2 : { tally(Ky, _, N2) }.
```

Not: `ArgExtremes.low` over a score the caller computes (any score, not a
count); `Extremes.low` (the score alone); `Tally` (the counts, over one member
set per key); `Unanimous` (the one value, absent on disagreement).

Match: a `Tally` instance whose `tally` feeds an `ArgExtremes.cand`, with that
`ArgExtremes` instance's `low` read. `grep -l ArgExtremes programs/solvers/*.dl`
narrows it; the `cand` rule body carries the `tally` atom. A second form scores
`Extremes` by a tally and recovers the member by re-joining that tally.

Survey: 2026-09-09 06:03

Survey: 2026-09-09 07:56 — the solvers edited at or after the survey above.
No new caller, and nothing further on the spec question.

## Spec question

Whether a member with no token competes. As written above it does not: it has no
`tally` row. Three sites need the opposite, and `Tally` carries a `domain` input
for exactly that, which `Mode` does not expose:

- `54db823b` feeds `marks.domain(O)` over every object, so the object holding no
  mark cells wins; its Determine comp feeds `tint.domain([E, O, C])` for the same
  reason.
- `2ccd9fef` feeds `miss.domain([A, N])`, so a split whose template explains
  every cell competes at zero.

Serving them needs a member-enumeration input beside `item`, with
`tally(Ky, M, 0)` for an enumerated member that holds no token. On the high end a
zero-count member never wins, so that input is inert for `mode` and changes only
`rare`.

Settled by the sites:

- Ties keep every member, as `ArgExtremes` does. `150deff5` depends on it: every
  tied minimum region enters a `Canon` equivalence.
- No caller needs the count beside the member. Every `ArgExtremes.low` reader in
  the corpus writes `_` for the score column, and `tally` stays available.

`Mode`'s single `Token` type parameter limits which callers reach it at all:
`1f85a75f` shares one `ArgExtremes` instance across two cases whose tokens are
`Position` and `Ident`, so it needs two instances and a per-case read rule, and
`f8b3ba0a` receives precomputed counts from three `Tally` instances of mixed
token type.

## Near-misses

Grouped by what excludes them:

- The count is taken under a different key than the selection, so `rare` would
  re-count per selection key: `20818e16`, `337b420f`, `5545f144`.
- The score is a distance or an edge minimum: `13713586`, `16b78196`,
  `1b8318e3`, `234bbc79`, `332202d5`, `3490cc26`, `4c3d4a41`, `25d487eb`,
  `1ae2feb7`, `20a9e565`, `34cfa167`, `1478ab18`, `045e512c`.
- The score is a box extent: `48634b99`, `4c7dc4dd`.
- The score is a stored rank from Params: `3d31c5b3`, `ea9794b1`, `a68b268e`,
  `6a11f6da`, `cf98881b`, `281123b4`, `1e5d6875`.
- `Extremes` over counts with no argmax — the extreme count itself flows on as
  an extent or a step count: `3ee1011a`, `271d71e2`, `2ba387bc`, `41ace6b5`,
  `4290ef0e`, `89565ca0`.
- A full `Order` over counts, read by rank against a threshold: `9caf5b84`,
  `89565ca0`, `4df5b0ae`, `31f7f899`, `3d6c6e23`.
- `31adaf00` — maximality by defect negation, local to overlapping squares and
  over a side length.
- The score is a `KeyedSetCompare.pattern_size` or an `Excess.excess`, neither a
  member count of the scored key: `44f52bb0`, `8597cfd7`.
- The read is the complement of the mode. "Not the commonest" names every
  non-mode member, where `rare` names the minimum alone; the two coincide only
  at two members: `6350f1f4`, `20818e16`.

## Callers

Each entry names the relation the `low` read derives.

- `1818057f` (family: `7e02026e`) — `frame.cell`, in Determine: the smallest
  component of a train grid, which fixes the stamp's footprint.
- `1b59e163` — `anchor(P, $Odd())`: within each shape, the color covering the
  fewest cells.
- `1b60fb0c` — the shift whose symmetry orbit covers the fewest cells.
- `1f85a75f` — `shape(P, L)`: the ink color with the fewest cells, or with the
  fewest pieces.
- `23b5c85d` — per size class, the color whose object holds the fewest cells.
- `269e22fb` — `chart_ink`, in Determine: the color covering the fewest witness
  cells.
- `2bcee788` — `marker_cell(P, $Minority())`: the ink color with the fewest
  cells.
- `2ccd9fef` — the panel holding the fewest distinct colors, and the split whose
  template leaves the fewest unexplained cells.
- `31aa019c` — `mark(P, Col, $Minority())`: the non-bg color with the fewest
  cells.
- `337b420f` — `mover(M, $Yield())`: among the movers with a clearing slide, the
  one with the fewest cells.
- `3bd292e8` — the region with the fewest cells.
- `446ef5d2` — `mark(Col)`: the ink color with the fewest cells; the same
  instance's `high` names the drawn color.
- `48f8583b` — `active(P)`: the color with the fewest cells.
- `4e7e0eb9` — per section, the color filling the fewest tiles.
- `54db823b` — the object holding the fewest mark cells, and in Determine, per
  example and color, the object holding the least of that color.
- `62ab2642` — `Parse.smallest`: the region with the fewest cells. It reads
  `high` and `low` off one instance, so `mode` and `rare` replace its `Tally`
  and `ArgExtremes` pair exactly.
- `aabf363d` — `marker(P, Col, $Minority())`: the color with the fewest cells.
- `150deff5` — `pick.equiv`, in Determine: per color, the smallest changed
  regions. Reached through the second code form.
- `88e364bc` — `head_of(C, Col, $Minority())`: per wall color, the legend
  color with the fewest cells.

Survey: 2026-09-10 20:33 — the solvers since 2026-09-09 07:56.

**Operation:** `Mode.rare` — the members of a key whose token count is the lowest, ties kept, as a readout beside `Mode.mode`. **Scope:** the 69 solvers named in the brief (045e512c through fafffa47), matched by the entry's signature (a `Tally.tally` in the body of an `ArgExtremes`/`Extremes` `cand` rule, with `low` read) via a parser script over `idx.refs`, plus a grep read of every `Tally`, `Mode`, `Extremes`, `ArgExtremes`, and `Order` instance in the scope. The signature matched five sites: 84ba50d3, 878187ab, 88a62173, 88e364bc, 89565ca0.

**1. Callers**

Callers:
- `88a62173` — `rarest.low(Ch, T, _)` feeding `out`: per case, the tile whose pattern the fewest tiles share (`alike` tallies the tiles `KeyedSetCompare.equals` matches to each tile). A `Mode<Choice, Position, Position>` with `item(Ch, T, T2)` gives it in one instance, where it now keys the `Tally` by `[T, Ch]` and the `ArgExtremes` by `Ch`.
- `88e364bc` — `head_of(C, Col, $Minority())`: per wall color, the legend color with the fewest cells. Already on the entry's list; it still writes the operation.

**2. Near-misses**

- `878187ab`, `counts` — `Extremes` over `marks.tally`, both `high` and `low` read, and the extreme count itself flows on as a `Frame2D` extent; no member is recovered. Excluded as `Extremes` (the score alone).
- `89565ca0`, `widest` — `Extremes.high` over `size.tally`, the count flowing on as the chart's extent; and `fewer`, a full `Order` over the same counts read by rank against a row index. Both already on the entry's near-miss list.
- `84ba50d3`, `widest` — `Tally` into `ArgExtremes` with only `high` read: the widest row of a shape. The high end is `Mode.mode`, not `rare` (see part 4).
- `264363fd`, `marker` — `!hue.mode(Id, Col)`: the cells of a rectangle not in its commonest color. The complement of the mode names every non-mode member, not the minimum.
- `8698868d`, `fewer` / `block_rank` / `piece_rank` — a count comparison feeding a full `Order` over `region_count.tally`, read by rank from both ends. A full order over counts, not the minimum.
- `85b81ff1`, `tile_rank` / `line_rank` / `obj_rank` — `Tally` counts fed to `Ordinal`, read by rank. A full order over counts.
- `88bcf3b4`, `size` — `size.tally(W, N)` compared against a walk rank (`R < N`); its `ArgExtremes` instances (`reach`, `silhouette`, `entry`, `nearest`) score edge distances.
- `412b6263`, `block_n` / `tile_n`; `84f2aca1`, `region_size` / `hole_size`; `b1fc8b8e`, `ink_tally`; `13e47133`, `pal_len`; `31d5ba1a`, `3428a4f5`, `34b99a2b`, `filled` — a `Tally` count flowing on as an extent, a table key, a stride period, or a threshold test; no extremum over the members.
- `1190bc91`, `13e47133` (`sight`), `3490cc26`, `1478ab18`, `045e512c` (`reach`), `cf98881b` (`nearest_pane`) — `ArgExtremes`/`Extremes` over a distance; `cf98881b` (`front_ink`, `front_pane`) — over a stored rank; `291dc1e1` (`widest`) — over a box extent; `44f52bb0` (`best_id`) — over `pattern_size`. All excluded by the `Not:` line, and the entry already lists them.
- `212895b5`, `cycle`; `97999447`, `unbroken` — `Extremes.low` over candidate period lengths, not counts.

**3. Spec**

No change from these sites. Both callers feed no `domain`, and neither can have a zero-count member (`88a62173`'s alike set always holds the tile itself; `88e364bc` tallies only colors that occur), so they add nothing to the zero-count spec question. Both write `_` for the score column and read ties as `ArgExtremes` keeps them, which matches the settled points. `88a62173` shows the record-key fold the entry's `62ab2642` remark describes: the `Tally` key `[T, Ch]` and the `ArgExtremes` key `Ch` collapse into one `Mode` key with `T` as the member, so the instance count drops from two to one; this is caller-side evidence, not an interface change.

**4. Reimplementations**

Reimplementations:
- `programs/solvers/84ba50d3.dl` lines 74–82 — `width = Tally<ShapeRow, Position>` feeding `widest = ArgExtremes<Ident, Position>` with only `high` read is `Mode<Ident, Position, Position>` with `item(Id, R, P) :- shape_row_cell(Id, R, P)` and `mode(Id, R)`; ties are kept by both.

Survey: 2026-09-11 04:31 — the solvers since 2026-09-10 20:33.

Callers:
7b0280bc fewest — `fewest.low($U(), Col, _)` feeding `end_color`: among the square colors, the color with the fewest pieces (`squares = Tally<Color, Ident>` counts each square color's pieces). A `Mode<Unit, Color, Ident>` with `item($U(), Col, Id) :- square_color(Col), piece_color(Id, Col)` and `rare($U(), Col)` gives it in one instance.
88a62173 rarest — `rarest.low(Ch, T, _)` feeding `out`: per case, the tile whose pattern the fewest tiles share. Already on the entry's list; it still writes the operation, with the `Tally` keyed by `[T, Ch]` and the `ArgExtremes` by `Ch`.
88e364bc rarest — `head_of(C, Col, $Minority())`: per wall color, the legend color with the fewest cells. Already on the entry's list; it still writes the operation.

Near-misses:
- 878187ab `counts` — `Extremes` over `marks.tally`, both `high` and `low` read, and the extreme count itself flows on as a `Frame2D` extent; no member is recovered. Excluded as `Extremes` (the score alone).
- 84ba50d3 `widest` — `Tally` into `ArgExtremes` with only `high` read: the widest row of a shape. The high end is `Mode.mode`, not `rare` (see Reimplementations).
- 8731374e `biggest`, 8efcae92 `winner`, 8e5c0c38 `ground` / `fit`, and the `bg_mode` / `field` / `ground` instances of 538b439f, 5dbc8537, 7b0280bc, 7c66cb00, 8698868d, 88bcf3b4, 8b7bacbf, 8b9c3697, 8f215267 — `Mode.mode` reads, the high end; 538b439f, 7b0280bc, and 8f215267 also read `!x.mode`, the complement of the mode, which names every non-mode member and not the minimum.
- 8698868d `size` — `Extremes.high` over `box.extent`, a box extent; `fewer` / `block_rank` / `piece_rank` — a count comparison over `region_count.tally` feeding a full `Order`, read by rank from both ends. A full order over counts, not the minimum.
- 85b81ff1 `tile_rank` / `line_rank` / `obj_rank` — `Tally` counts fed to `Ordinal`, read by rank. A full order over counts.
- 8abad3cf `debut` — `Extremes.low` over a `LexOrder` rank, not a count; `ink` / `area` — two `Tally` counts joined by equality, with no extremum over the members.
- 53fb4810 `shortest` — `Extremes.low` over `ShiftInvariance.period` lengths, not counts.
- 8dae5dfc `layer_depth` — `Extremes.low` over `Rim.depth`, a distance, feeding an `Order`.
- 8cb8642d `nearest` — `ArgExtremes.low` over an edge distance.
- 88bcf3b4 `reach` / `nearest` / `silhouette` — `ArgExtremes` over edge distances; `size` — `size.tally(W, N)` flows on as a cell count for the walk, with no extremum.
- 8e301a54 `hue_size` / `object_size`; 84f2aca1 `region_size` / `hole_size`; 8ba14f53 `holes` / `offset`; 8f215267 `blobs` — a `Tally` count flowing on as a jump distance, a table key, a block extent or stacking offset, or a slot bound; no extremum over the members.

Spec:
No change from these sites. The new caller 7b0280bc feeds no `domain` and can have no zero-count member (`square_color` holds only colors that have a piece), so it adds nothing to the zero-count spec question. It writes `_` for the score column and reads ties as `ArgExtremes` keeps them, matching the settled points. Its member type is `Color` and its token type `Ident`, which the single `Token` type parameter serves. The `Tally.domain` reads in the scope (8698868d `region_count`, 85b81ff1 `tile_ink`, 8ba14f53 `offset`) all feed an order or an offset, not a minimum, so they bear on `Tally` and not on `rare`.

Reimplementations:
- `programs/solvers/84ba50d3.dl` lines 74–82 — `width = Tally<ShapeRow, Position>` feeding `widest = ArgExtremes<Ident, Position>` with only `high` read (through `unique_widest.item`) is `Mode<Ident, Position, Position>` with `item(Id, R, P) :- shape_row_cell(Id, R, P)` and `mode(Id, R)`; ties are kept by both, and `Unanimous` then drops them as it does now.
The signature (a `Tally.tally` in the body of an `ArgExtremes`/`Extremes` `cand` rule, with the instance's `low` or `high` read) was matched by a parser script over `idx.refs` across the 49 solvers of the scope, and hit five sites: 7b0280bc, 84ba50d3, 878187ab, 88a62173, 88e364bc. Every `Tally`, `Mode`, `Extremes`, `ArgExtremes`, `Order`, `Ordinal`, and `LexOrder` instance in the scope was then read at its rule; a grep for raw `min`, `max`, `count`, and `sum` aggregators in the scope found none.
