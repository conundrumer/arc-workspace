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

Survey: 2026-09-11 05:33 — the solvers since 2026-09-09 01:42.

Callers:
5833af48 pixel_cand, band_color, pixel_broken, pixel_size — the $Blocks case sweeps every block size the plan's extent admits per axis (`sub_extent` or `axis_dim`, then `divide_by_size`), keys a `Unanimous` by axis, size, block index, and across component so a band holding two colors breaks the size, and takes the largest unbroken size per axis with `Extremes`, then feeds it into a `Tile2D` `dim` to read each plan cell's pixel. That is the operation the entry specifies, still written as plain relations.
No second caller. Across the scope, 39 divide-family calls take a size; 37 take it from a parameter, and the 2 that do not are both in 5833af48. The parser scan for a rule that binds a divide-family size from `sub_extent` or `axis_dim` in the same rule matched that one rule in scope. Every `Tile2D` and `Divide2D` `dim` in scope other than 5833af48's `pixels` takes its size from a parameter, a stamp's box extent, or a pattern's box extent.

Near-misses:
898e7135 scale_cand — sweeps `axis_dim ; sub_extent` over a piece's box, scales each hole by the candidate with `Frame2D` and `concat_2d`, and picks the size at which the scaled hole is congruent to the piece (`KeyedSetCompare`). The size is chosen by congruence with another shape, a criterion other than block uniformity, and the picture is scaled up, not recovered.
8abad3cf cand_side — sweeps `sub_extent ; axis_dim` over the input and picks the side whose square area equals a color's cell count. No division of the grid and no block test: a size chosen by a count.
8a6d367c blocks — `Divide2D` `dim` is the shape pattern's box extent, so the block size is a scale factor read off two extents (the hole's and the pattern's); `contradicted` tests fill cells against the pattern, not block uniformity.
0dfd9992 axis_rep — `sub_extent` bounded by `period`, an input: a period (`ShiftInvariance`), which repeats a pattern rather than stretching one cell.
045e512c span — `sub_extent` yields step lengths for translations of an object; nothing divides.
88a62173 line_color, lattice — one-colored lines are found by a `Unanimous` and fed as dividers to a `DividerFrame`; the tile size comes from the dividers, not from a sweep tested for uniform blocks.
8f2ea7aa cell ($Divide), 88a62173 tile_val ($Size), 85b81ff1 decompose ($Size), and the divide_slab family in scope (0520fde7, 0c9aba6e, 195ba7dc, 1b2d62fb, 31d5ba1a, 3428a4f5, 34b99a2b, ce4f8723, cf98881b, d19f7514, dae9d2b5, e133d23d, e345f17b, f2829549, fafffa47) — the tile size or count is stored as a parameter.
412b6263 tile_dim — a `Unanimous` over axes in `Determine` agrees a tile count across examples, counted from seat offsets, not a block test.

Spec:
The scope holds one site, the surfacing solver, so every signal is caller-only. Its call site agrees with the entry's recorded questions: `cand` includes the whole extent (`axis_dim` beside `sub_extent`); the block index is the only part of `pixel` read; and per-axis sizes reach the 2D `pixel` through a `Tile2D` `dim`. One detail the entry's prose does not state: 5833af48 tests uniformity per band, a 1D run along the swept axis keyed by its across component, not per 2D block, so the per-axis `broken(key, a, s)` in the code form is the reading the caller takes. Caller-only; no change proposed.

Reimplementations:
8b7bacbf multi_cell, line 51 — `ink(P, Col), ink(Q, Col), P != Q` is `Unanimous<Color, Position>` `clash`; `marker` at line 54 is its `value`.
84ba50d3 wide, line 65 — `shape_row_cell(Id, R, P), shape_row_cell(Id, R, Q), P != Q` is `Unanimous<ShapeRow, Position>` `clash`.
71e489b6 continued, line 31 — `figure_nbr(P, D1), figure_nbr(P, D2), D1 != D2` is `Unanimous<Position, Dir>` `clash`.
7f4411dc support_kept, line 46 — `support(P, D1), support(P, D2), D1 != D2` is `Unanimous<Position, Dir>` `clash`.
Method: a grep for `divide`, `sub_extent`, `axis_dim`, `Unanimous`, `Tile2D`, `Divide2D`, and `stride` over the 103 scope files, each hit read in its rule; a parser scan over the scope for divide-family atoms whose size argument is not bound by a `params` atom (39 calls, 2 hits, 1 bound by `sub_extent`/`axis_dim` in the same rule); and a Unanimous-shape parser match over the scope (25 candidate rules, of which the four above are clash tests and the rest are pair or order rules).
