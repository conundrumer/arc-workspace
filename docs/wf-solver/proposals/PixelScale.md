# `PixelScale<Key, Val>` — the scale a picture is drawn at

The block size at which a keyed valued cell set is a scale-up of a smaller
picture, per axis, together with that picture's cells: the size is the
largest one whose every block holds a single value, so a solver reading a
grid whose content is drawn with fat pixels recovers the picture without
being told the factor. The known sites sweep the block sizes the extent
admits, test each with a `Unanimous` over the blocks, and take the largest
that no block breaks.

```
.comp PixelScale<Key, Val> {
    .decl cell(key: Key, p: Position, v: Val)  // input

    // A block size the frame's extent admits, per axis.
    .decl cand(key: Key, a: Axis, s: number)

    // A candidate one of whose blocks holds two values.
    .decl broken(key: Key, a: Axis, s: number)

    // The largest size no block breaks.
    .decl scale(key: Key, a: Axis, s: number)

    // A cell's pixel, and its place inside that pixel.
    .decl pixel(key: Key, p: Position, p_outer: Position, p_inner: Position)
}
```

Not: a scale factor read off two extents, or stored as a parameter; a
period (`ShiftInvariance`), which repeats a pattern rather than stretching
one cell; a run collapse, which admits pixels of unequal length; a tile
size chosen by a criterion other than block uniformity.

Match: a sweep of block sizes over one frame — `sub_extent` or `axis_dim`
feeding `divide_by_size` or `divide` — whose survivors are filtered by
whether the resulting blocks hold one value, and one of which is then
selected. Also any solver that divides a grid by a size it derived from
that grid's own repeated content.

Survey: 2026-09-08 23:54

Scope: all 566 solvers. The parser scan for the core shape — a cell grouped
by the block position a swept divide gives it — matched one rule corpus-wide.
Of the 122 divide-family calls that take a size, 13 take a size that is not a
parameter, and 6 derive it by a sweep. No reimplementation of a lib comp
turned up at any of the sites read.

Near-misses, each a sweep with another criterion:

- `7b7f7511` `$Tile` keys the `Unanimous` by the within-slab position, so its
  test is that the slabs agree cell by cell — the period.
- `e9afcf9a` `$Divide` keeps the size at which the intile position fixes a D4
  transform.
- `0934a4d8` `Determine` keys a symmetry subgroup per block and takes the
  coarsest size whose blocks *differ*.
- `456873bc` keeps the size whose tile arrangement is square, reading no
  block content.
- `2ccd9fef` sweeps panel counts and scores each split by unexplained cells.
- `5614dbcf` `$Solid` tests that a block holds one value, at a stored size.
- `1990f7a8` and `447fd412` recover a drawing scale by measuring one
  component's square bounding box.

The four sweeping sites share their first half exactly: `sub_extent` or
`axis_dim` producing candidates, a divide-family call per candidate, then a
keyed `Unanimous` over the decomposition. They part on what the `Unanimous`
is keyed by and how one survivor is picked. A smaller operation cut at that
seam would have four sites; block uniformity alone has one.

Survey: 2026-09-09 01:42

Scope: the solvers whose file time is at or after 2026-09-08 23:54. It added
no caller: of the fourteen solvers in scope, none sweeps a size, and every
divide-family call in scope takes its size from a parameter or from a measured
bounding box. Its near-misses are `58743b76` `part`, which sizes its parts by
the ratio of two boxes with no block test; `58c02a16` `phase`, whose block
size is the layout's period, measured off a separator-delimited box; and
`465b7d93` `edge_hole`, which maps side to side and computes no size. No
reimplementations.

Spec questions, on which the callers so far agree:

- Whether `cand` holds the whole extent. Both callers write
  `( sub_extent(P, A, S) ; axis_dim(P, A, S) )`, because the picture may be
  one pixel across on an axis; every sweeping near-miss uses `sub_extent`
  alone.
- Whether `pixel` carries `p_inner`. Both callers read the block index only.
- How per-axis `scale` reaches the 2D `pixel`. Both callers bridge the two by
  feeding each axis's size into a `Tile2D` `dim`. `58743b76` performs the same
  bridge into a `Divide2D` `dim`, so the bridge is the corpus's ordinary way
  of turning per-axis sizes into a 2D decomposition rather than a feature of
  this operation.

Callers:
- 5833af48 ($Blocks case)
- 5ad4f10b ($Pixels case) — the figure's own pixel size, against the stored
  picture extent of its $Extent case.
