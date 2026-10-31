# fea12743

## Departures
- The witness ids `$ProperUnion` and `$GutterLayout` are now `frame-inside-copy` and `small-tiles` in the witness file: lint takes a witness id only in slug form.
- New witness `blank-inner-column` (ordinary, concept) under `$GutterLayout`: in this input the left tiles leave their first column blank. `$GutterLayout` then finds blocks of two widths and is undefined, and the stored layout paints the union. The `witness` run reported that no run showed `$StoredLayout & gutter=SepThickness` defined and differing from `$GutterLayout`, and this witness resolves that. The input breaks no scene claim, and a 4x4 drawing with a blank first column is a normal output of the generator.
- `$XorCombine`, `$IntersectCombine`, `$SubsetParts` and `$AllCopies` have no constructor. Each one fails Fit at train0, as `analyze.md` gives, and has no witness.
- Under `$FartherCopy`, a step of the taxicab distance goes to the next tile in the same row or column of tiles (`ahead`, `between_tile`), and not to the neighboring tile position. With `$GutterLayout` and a two-wide gutter, the tile positions from `DividerTiles` skip indices. Before this fix, the `gutter=SepThickness` witness showed `$FartherCopy & $GutterLayout` painting the union and no parts. In the same fix, a case is now undefined where a part shape has no painted copy (`unpainted`).

## Judgments
- `analyze.md` describes the rule "as the generator applies it" (the tiles the generator built as the overlay and its pieces). I did not take this as a restated rule. It refers to the generator's history and not to the input, so it is not a claim about the task. The concept file's rules stand, with no `@approximated:` line.
- `@derive DominantColor: variant derived`, `@relaxed one-ink`: the witness is train0 with colors 0 and 1 swapped. A color-permuted variant task routinely has that background. The concept, with background 0, sees every tile as fully inked and is undefined.
- `@derive TileCount: variant derived` and `@derive SepThickness: variant derived`, both `@relaxed tile-layout`: their witnesses are other layouts (3x3 tiles, and a two-wide gutter). A variant task gives these layouts, and the derived layout paints the union there.
- `tile_size=TileDim` left under Subsumption (`@ignore: derive TileDim`). I built the witness `tile_size=TileDim` (6x6 tiles in a 22x15 frame), and there it gave the same output as `tile_size=TileCount`. I found no input where it is defined and differs from TileCount, so I removed that witness. TileDim always derives size 1 (n = extent, gap 0). That size makes a second decomposition on every frame whose two sides are odd, so TileDim is undefined on those frames.
- Determination of `part_color` and `union_color`: these are the two colors that the output has and its input lacks. The part color is the one that is never outnumbered, because two parts together hold at least as many cells as their union. The union color is the one that never outnumbers the other. This is a fact of the outputs alone, so it takes no tile parse.
- Determination of `gutter`: the least distance from ink to each edge, which must be the same for every edge of every train input. Determination of `tile_size`: the sizes at which the stored-gutter tiles cover every ink cell of every train input.
- Hint `single-consumer` on `next_tile`: I put the relation inline in the `tile_dist.edge` clause.
- Hint `common-subexpr` on `fewer`/`more`: I joined them into one relation, `outnumbers`.
- Deletions: 32 deletions change nothing. These are the undefinedness guards (`union_clash`, `fullest_tie`, `paint_tie`, `unpainted`, `block_size`), the `same_dist` row/column test in `ahead`, unused key columns, and the train-only `train(E)` atoms of `Determine`. The pairs do not instantiate them, and each one states a claim or an undefinedness of a branch, so all of them stay. One column, `union.s_b`, was unused, and I removed it.
- Performance: `store` took 57 s, and `audit` took 29 s.

## Unsettled
- `gutter=TileDim` fits and has no `@derive` or `@ignore: derive` line. It needs a witness on which it is defined and differs from the other cases, or evidence that it fails a case condition.
- `copy_order.before` and `copy_order.cell` `@store` branches (witness: train0 turned a quarter turn clockwise) were not added, because Develop reached its budget. To settle them, add the `@store` lines with a judged verdict and record their witnesses.
- `copy_order`: the sweep and the plan say that (DIAG_TR, AXIS_V), (DIAG_TR, AXIS_H) and (DIAG_BR, AXIS_H) also fit every pair. The audit's relabelings check says that a turn or a mirror of `copy_order` changes no output. `analyze.md` judges that no reader takes these orders as open values, so the value stays stored, and the plan entry stands after three runs. To settle it, judge whether reading order is an open parameter or a value that the concept fixes.
- The audit `store` findings on the copy-order instance are open for the same reason. The other `store` findings are dismissed with `@ignore: store`.
- `deletions` ran before the last solver edit, the removal of the `union.s_b` column. A run after that edit would settle it.
- `record --all` was run a second time with its output discarded, after the TileDim witness was removed. To settle it, run `record --all` again and read its output.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
