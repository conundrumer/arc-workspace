# `Magnify<Key>` — the picture cell whose scaled block covers a drawn cell

The map from a cell of a picture drawn at a scale factor back to the picture cell it enlarges, per key, with the drawing placed by one cell: the picture's origin cell enlarges onto the block that starts at a seat cell, and blocks extend from their start toward a corner. It is the anchored, per-cell peer of the `divide` family, which reads block index and within-block position off a whole frame and asserts that the frame's extent divides: here the drawing sits anywhere, the frame need not divide, and a cell behind the seat on either axis is in no block. A solver that walks a chain of ever-larger copies, or seats a scaled-up copy of an object at a marked cell, reads the source of each output cell through it.

Code form (plain relation, as the solver writes it):

```
.decl block(key: Key, q: Position, p: Position)
block(Ky, Q, P) :-
    cell(Ky, Q), seat(Ky, S), displacement(S, Q, V), factor(Ky, F),
    corner(Ky, Dg), diag_dirs(Dg, _, D1, D2),
    opposite(D1, O1), dist(V, O1, K1), stride(K1, F, 0, N1, _),   // steps toward D1, scaled down
    opposite(D2, O2), dist(V, O2, K2), stride(K2, F, 0, N2, _),   // steps toward D2, scaled down
    origin(Ky, P0), jump(P0, D1, N1, P1), jump(P1, D2, N2, P).
```

Not: `divide_by_size_2d` and the `Tile2D` family, which decompose a whole frame and need its extent to divide; `PixelScale`, which finds the factor; `Occurrences`, which places an unscaled shape; a `concat` that assembles tiles into a frame; a stamp of a stored picture at a marker (`GRID_STAMP`), which scales nothing.

Match: a rule that takes a cell's displacement from an anchor cell (`displacement`, or a `Reframe` inner position), divides each of its two components by one factor (`stride` with the remainder dropped, or `divide_by_size` on a frame that starts at the anchor), and rebuilds a position from the two quotients (`jump`, `compose`, or `DirPack`) from a second anchor. Also the forward form: a picture cell whose displacement from an anchor is multiplied by a factor, with a block of that factor's side enumerated at the product.

Survey: 2026-09-10 03:45

Scope: all 658 solvers. The three-leg parser match (an anchor displacement
or `Reframe` inner; a `stride` quotient or divide-family call; a `jump`,
`compose`, or `DirPack` rebuild) hits one rule corpus-wide, `762cd429`
`source`. Of the 23 solvers that call `stride`, 20 read only the remainder;
the two that read the quotient are `58c02a16` (below) and `5d588b4d`
`place`, which wraps a rank into reading order and scales nothing. The
forward form turned up at two sites, found by `jump` with a count bound from
an extent readout and by `concat` output fed to `compose`. Scan scripts:
`.scratch/762cd429/scan_magnify.py`, `scan_forward.py`.

Near-misses:

- `58c02a16` `phase` — a corner-anchored per-cell decomposition: `stride`
  reads block index and within-block position from the grid corner, then
  folds the index by the pattern period. A whole-frame decomposition whose
  index names a wallpaper phase, not a seated picture cell.
- Scaled drawings placed by a bounding box whose extent divides, read with
  the divide family: `103eff5b`, `6b9890af`, `6ecd11f4`, `58743b76`,
  `33b52de3`, `6aa20dc0`, `5833af48`, `15113be4`, `5ad4f10b`.
- Whole-frame scale-ups assembled with `concat_2d`/`concat_slab`:
  `60c09cac` and its family, `007bbfb7`, `0692e18c`, `2072aba6`, `310f3251`,
  `ac0a08a4`, `d4b1c2b1`, `469497ad`, `46f33fce`, `65b59efc`, `42f83767`,
  `1be83260`, and the `$Scale` cases of `3979b1a8`, `539a4f51`, `963e52fc`.
- `e633a9e5` — a nonuniform scale-up: tile extents vary per line, so there
  is no factor.
- `18286ef8` `$Map` — a 1:1 tile-to-cell map through `BoxFrame.inner`, no
  factor.

Spec questions:

- **Sidedness.** Both forward callers put the origin inside the picture, so
  blocks lie on every side of the seat; the entry's one-sided form
  (`stride`'s `T >= 0`) serves only `762cd429`. Under a two-sided
  definition, where a block starts at the seat plus the scaled signed
  displacement and extends toward the corner, `762cd429`'s two per-side
  anchors state one affine map, and one anchor would serve. Two callers
  beyond the surfacing solver argue for the two-sided form.
- **Direction.** Two callers read forward (picture cell to its block's
  cells), `762cd429` backward; its recursion reads the relation either way.
  A forward derivation takes the picture domain as `cell` and enumerates
  the F×F intile positions; a two-sided backward derivation needs floor
  division, which `stride` does not offer. Which domain the comp takes as
  input is open.
- **Factor.** One scalar serves all three callers: `447fd412` asserts square
  blocks, and `57aa92db`'s mark blocks are square on every pair, though it
  feeds `Tile2D` per axis.
- **Corner.** `447fd412` seats by the block's margin box (toward BR from
  the box's TL cell); `57aa92db` seats by the mark block's cells, indifferent
  to convention; `762cd429` uses a per-side corner. A fixed convention would
  serve the two forward callers and move `762cd429`'s seat to the diagonal
  cell past the front corner.

Placement validation (`447fd412` checks that every template mark's box is
a block) and clipping to the grid stay with the callers.

## Callers

- 762cd429 — `source` (`:64-69`): backward form, one anchor per side, keyed
  by `Choice`; `copy` reads it recursively, so the chain of doublings falls
  out of one map.
- 447fd412 — `carry` (`:60-66`), read by `covers` and `stamped`: forward
  form written as a walk, one template cell and one box jump of `K` cells
  per step; origin = a template mark, seat = the block's box, factor = the
  block's side.
- 57aa92db — `seat` and `stamp`: forward form; `concat_2d` scales the shape
  in the template's tile frame, `displacement` reads the seat off the mark
  tile, `compose` places every scaled cell; factor = the mark block's extent.

Survey: 2026-09-10 21:11 — the solvers since 2026-09-10 03:45.

Callers:
8a004b2b `drawing` and `painted` — the forward form of the magnify operation: `drawing` spreads each blueprint cell over a `Frame2D` tile with `concat_2d`, giving the blueprint scaled by the block side in its own frame; `seat` (`Occurrences`) places that drawing where every block cell lands on a drawing cell of its color; `painted` reads each frame cell's drawing cell through that placement with `compose`. Factor = a block's side, one scalar, read off `block_box.extents(_, A, K, K)`.

No second caller in the scope. The three-leg parser match (an anchor displacement or Reframe-family inner position; a `stride` quotient, divide-family call, or `Tile2D`/`Divide2D` tile; a `jump`, `compose`, or `DirPack` rebuild) hits no rule across the 58 solvers. Every `stride` site in scope (13e47133 `out`, 212895b5 `phase_turn.item`, 759f3fd3 `filled`, 97999447 `slot_color.item` and `mask`) leaves the quotient wild and reads the remainder alone: a period phase, not a scale. The divide-family sites (85b81ff1 `decompose`, 88a62173 `tile_val`) decompose a whole frame into equal panels with no factor. Of the `concat` sites, only 8a004b2b `drawing` scales a picture by a factor; the rest assemble unscaled content. The forward-form probes (a `jump` count bound by an extent readout; `concat` output fed to `compose`; `displacement` beside a `concat`) hit 11dc524f `mirror` only, a translation by a box length.

Near-misses:
- 8719f442 `cell` — a whole-frame scale-up: the input grown by one ring is the tile frame, every tile is input-sized, and `concat_2d` assembles the output over that whole frame. The `seat_delta` shifts the block's tile index inside the tile frame, not a cell seat, and the frame's extent divides. The `concat`-assembles-a-frame exclusion rules it out.
- 412b6263 `placed` — a tiling of unscaled copies of the input, assembled with `concat_2d` (`$Layout`) and `concat_slab` (`$Count`) across line-width gaps. No factor: each tile is the input under a D4 element.
- 291dc1e1 `out` — a stack of unscaled blocks assembled with `concat_slab` along the stack axis. No factor.
- 85b81ff1 `decompose` and 88a62173 `tile_val` — whole-frame equal-panel decompositions by the divide family (`divide_slab`, `divide_by_size_slab`, `divide_2d`, `divide_by_size_2d`), reordered or selected. The divide-family exclusion rules them out, and nothing is scaled.
- 11dc524f `mirror` — a box placed one shape-length past its home with `jump` by a `Bbox` extent. A translation of a reflected shape, no factor.
- 7f4411dc `square_kept`, 890034e9 `twin`, 264363fd `stamped`, 88a10436 `stamp` — `Occurrences` or a `compose` from a marker places an unscaled shape. The unscaled-`Occurrences`/stamp exclusion rules them out.

Spec:
- Direction. 8a004b2b reads forward, as the two forward callers in the 03:45 result do: the picture domain in, the scaled cells out. That adds a third forward site against the one backward site (762cd429).
- Factor. 8a004b2b reads one scalar and asserts square blocks (`extents(_, A, K, K)`), as 447fd412 does. Nothing in scope reads a per-axis factor.
- Seat as a separate step. In 8a004b2b, as in 57aa92db (03:45), the scaling happens in the picture's own frame (`concat_2d` over a `Frame2D` tile) and the seat enters afterwards through `compose`. 8a004b2b needs the unseated scaled picture: `Occurrences` finds the seat by matching that picture's cells against the blocks, so a comp that fuses seat and scale cannot feed it. Two callers argue that the forward form should expose the scaled picture in its own frame, with the seat a caller-side `compose`; under that reading the seat and corner inputs of the entry's code form serve the backward caller only. With the forward form stated as `Frame2D` tile × `concat_2d`, the spec question is whether the operation beyond what lib holds is only the backward map (per-cell, anchored, non-dividing), which 762cd429 alone writes.
- Corner. 8a004b2b is indifferent to the corner convention: `concat_2d` fixes the block layout inside the drawing frame, and `Occurrences` places the whole frame by its margin. This matches 57aa92db, and leaves 447fd412 and 762cd429 as the only sites where a corner input is read.

Reimplementations: none.
Matcher hit counts over the 58 solvers: three-leg backward match 0; `stride` sites 5 in 4 solvers, all remainder-only; divide-family sites 4 in 2 solvers; `concat` sites 6 in 5 solvers; extent-bound `jump` 1; `concat`-to-`compose` and `displacement`-with-`concat` 0. Method: the parser scan at the scratch path, over `dl.corpus.each_solver` filtered to the scope, plus a grep of the `// concept:` lines for scale, stamp, grow, and tile-arrangement, with each hit read in its rule.
