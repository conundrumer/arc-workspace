# `Occurrences.carry` — the cells a figure lands on, seated at an occurrence of its matched part

A per-cell readout on `Occurrences` for a figure larger than the shape it was sought by: the search matches a part of the figure — its marks, its anchor cells, its outline — and the whole figure is composed at each occurrence, so a caller reads where every figure cell lands, matched part and carried part alike. `covers` is this with the figure landing no cell outside the shape; a figure that reaches past the shape lands cells the search never tested, on the grid or off it, and the caller decides what an off-grid landing means.

```
    // The figure the shape is part of, per key, in the shape's frame.
    .decl figure(key: Key, p: Position)  // input

    // The grid cells the figure lands on at an occurrence, cell by cell.
    .decl carry(key: Key, p: Position, p_fig: Position, p_cell: Position)
    carry(Ky, M, F, P) :- occurrence(Ky, M), figure(Ky, F), compose(M, F, P).
```

Not: `covers` (the figure lands no cell outside the shape); `placement` composed before the mismatch test; a stored footprint or satellite composed at a mark or a seat that no occurrence test found; a figure composed at a searched Offset that `Occurrences` did not produce; `apply_about` and `apply_between`, whose landing is a frame Position and not a searched placement.

Match: a rule that composes, with `compose`, a relation that together with the instance's `shape` feed is the figure — the shape's unfiltered source, the whole object whose subset the shape is, the source's complementary part alone, or a satellite cell alone — at a placement an `Occurrences` instance's `occurrence` produced. The placement reaches that rule directly, or through derived relations, any number of them, and through a lib comp that selects among candidate placements, as `PlacementPruning.alive` does; a placement some other rule computes is the `Not:` line's unsearched seat. Take the forward closure of the instance's `occurrence` over the solver's rules, counting a lib instance's relations as joined to one another, then read each rule in that closure that holds `compose` and check that the composed relation lands cells the shape does not. A relation over the shape's cells with substituted values, as 6c434453's `params.dst` is, and a subset of the shape's feed, as 825aa9e9's `mover_cell` is, land no such cell: both are `covers`. Grep `occurrence(` for the instances; run the closure and the check with the parser.

Survey: 2026-09-10 06:15

Scope: every solver in `programs/solvers/`. Every `Occurrences` instance's
`occurrence` was traced to the rules that compose a Position at it, directly
and through one derived relation (`.scratch/7df24a62/carry_sites.py`,
`hops.py`), and each composed relation was compared with the instance's
`shape` feed.

Near-misses:

- 142ca369 `enter`, 409aa875 `placed`: the composed cell (`marker_launch`,
  `glyph_apex`) is a member of the glyph the shape holds, so the figure is
  the shape — `covers` restricted to one member.
- 6c434453 `stamped`: `dst` is a `GRID_3x3` over the same nine cells as
  `src`, so the figure is the shape with other values — `covers` with a value
  substitution.
- 652646ff `drawn`, 3ed85e70 `stamp`, 045e512c `copy`: the search is
  inverted — the whole figure is the cell domain and what shows of it is the
  shape — and the figure is composed at the inverse of the occurrence, a
  Shift `Occurrences` did not produce.

Spec question: the interface stands as proposed. Two things the sites show
bear on the entry's text, not on `carry`:

- The Match line's "strict superset" misses two of the callers, whose
  composed relation is disjoint from the shape feed: a satellite alone
  (3aa6fb7a `piece_gap`) and the source's complementary part alone (79369cc6
  `image` at the fill color). The signature should read: a relation that,
  together with the shape feed, is the figure.
- Three callers derive an occurrence-level predicate back from a carried
  cell's grid content (79369cc6 `blocked`, 6e4f6532 `partial`, 21897d95's
  hole-center payload). That is a caller rule over `carry`, and `carry`
  exposing `p_cell` serves it.

Callers:

- 7df24a62 `filled` — the posed box (`pose`, the shape's unfiltered source)
  composed at each seating of its marks.
- 0e206a2e `placed` — the whole posed object composed where its anchor cells
  seat on the markers.
- 6e4f6532 `seated` — the whole posed object composed where its core seats on
  a target.
- 79369cc6 `fill_at` — the posed template's fill cells composed where its mark
  cells seat.
- 3aa6fb7a `mark` ($Glyph) — the L's gap cell composed at each placed L.
- 21897d95 `placed_arrow`, `arrow_host.item` — the chart's center and its
  frame's free cells composed at each placed arrow chart.
- 4e34c42c `seam_cell.item`, `disagree` — the whole fragment (`content`,
  `motif` in every color) composed at the fit of one color's motif.
- d9fac9be `out` ($Box) — the box frame's center composed where its ring
  seats on an ink.
