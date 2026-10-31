# e619ca6e

## Departures
- The solver has no case that takes `$Adj8` together with the concept branch `$Rect`. The `$Adj8` group in `witnesses.json` has no case to compare against, so the run against that file reports that `$Adj8` "denotes a model that is no case of the solver": that model fails Subsumption. Two 4-components that 8-adjacency joins never form a solid rectangle, so under `$Rect` the `$Adj8` model is undefined on every input where it differs from the concept. `analyze.md` says the same. The `$Adj8` constructor stays because the cases `$OwnCells & $Adj8` and `$BboxFill & $Adj8` take it.
- The witness file's groups are the ones `record --all` wrote, which name the solver's cases. Each grid is the same as in `witnesses.json`.

## Judgments
- How copies are found: the program does not step k times, which would need arithmetic or recursion. It measures a cell's distance from the two back edges of the block's box with `relative` and `diag_dist`. It then cuts each distance into periods of the block's height and width with `stride`, and keeps the cells whose period index is the same on both axes and above 0. The `own_copy` relation takes the block cell at the same in-period place, so `$AnyShape` copies the object's own cells.
- Components are keyed by `Part = [oc, col]`. Under `$AnyInk` the key is the background color, so every non-background cell can join one component. Under `$PerColor` the key is the cell's own color. With this key, one `Components` and one `Components8` instance serve both object-color branches.
- `$Rect` is undefined through `live`: on an input where some object's box holds a cell outside that object (`hollow`), the case gives no `out` facts.
- `@ignore: store` on `member`, `own_copy` and `paint`: `store` reported one color, 3, on every input. The concept's `copy-keeps-block` takes the copy color from the block, and 3 is the scene parameter `block_color`. So no stored-color branch was held (see the progress note).
- `background=DominantColor` is a `@derive` branch with no constructor, at `variant derived`, `@relaxed solid-blocks`, as `analyze.md` gives it.
- Determination: `background` reads from the evidence the input color of the cells the output changes. `cast_dir` has no determination relation. I tried one clause that read the corners whose diagonal neighbor turns into the block color. It gave rows beyond {BL, BR}, because in train 0 other staircases pass the corners of blocks. A version built on `corner_miss` tested inputs and outputs together, and the lint flagged it. `cast_dir` therefore rests on fit, and the sweep finds it unique as a set.
- Deletions: these eight changed no pair's output: the `reach` columns `d_back`, `a`, `i` and `j`; the `diag_dist` atom in `own_copy`; `hollow` and `!hollow`; and `live` in the `$Rect` paint clause. Every block in the pairs is solid, so the pairs never instantiate those structures. The witnesses `l-shape` and `background=DominantColor` do instantiate them, so they stay. The `live` atoms in the `$AnyShape` paint clauses were redundant, and I removed them.
- Not formed items in `analyze.md`: each one fails Fit, is equivalent to the stored set, or states no model. So Develop step 3 added no branch.
- The witness check without `--file` reported no unseparated pair of cases and no case that no run shows defined and differing. The audit found no stored fact whose removal changes nothing.

## Unsettled
- A determination relation for `cast_dir` that reads the directions from the evidence: it needs the blocks parsed in `Determine`, or moved into `Parse`, so that each block's first copy can be read at its touching corner.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
