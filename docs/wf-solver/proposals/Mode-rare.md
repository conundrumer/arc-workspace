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
