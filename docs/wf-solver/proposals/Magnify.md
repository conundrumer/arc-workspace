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
