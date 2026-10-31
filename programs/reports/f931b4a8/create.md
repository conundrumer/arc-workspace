# f931b4a8

## Departures
- Params has a parameter `quads(2)`, the tile count of the quadrant split on each axis, which the concept file's Parameters section does not list: the Literals ban makes the program read the non-zero count that `divide_2d` takes from Params. The sweep finds it unique, and the plan reports the `TileCount` proposer covers it.
- In the witness file, `record --all` rewrote the group names to the listed form (`$Quadrant`, `$SharedAnchor`, `$Direct` in place of `concept` where one branch point separates the groups). The outputs are unchanged.

## Judgments
- Quadrant split: `divide_2d` with `params.quads`, and the quadrant named by `box_corner(P_tile, ZERO, Q)`. This follows the precedent of 75b8110e, which reads its tile count from Params. The split and the per-quadrant non-bg tally are in `Parse`, because `Determine` uses them as well.
- Tiling and fill reads use `stride` on each axis's distance from the `anchor` corner's edge, and `diag_dist` from that corner. Because the corner is a parameter, the modulo map has no hidden orientation.
- The concept is undefined where a tile index passes the fill grid. The solver gives this by having no `fill_cell` fact there, so the output is partial. `$FillIndexWrap` wraps the index with `stride` over the fill quadrant's extent on that axis.
- Hint `single-consumer` on `tile_extent` and `fill_extent`: I inlined both into their one consumer. This also fixed an ungrounded axis variable.
- Hint `head-repeat` on `fill_index`: I kept it with `@ignore`. Under `$Direct` the line is the tile index itself, and `$FillIndexWrap` changes that column.
- Hint `determine prediction` on a `count_quad` determination: that relation tested the inputs against the outputs, which is a fit test. I removed it, and the runner determines `count_quad` from the train pairs.
- `fill_anchor`: the sweep finds that the train pairs also admit `DIAG_TR`, and test refutes it. The pairs separate it, so it is not an open parameter, and the solver stores `DIAG_TL` alone.
- `bg`: the plan lists it as covered by `SharedColor`. That is the fact `analyze.md` gives for its value (the only color every input has), so it needs no determination relation.
- `derive` reports that no built-in derivation fits. `store` reports no line to add (`tile_place[a]` varies per cell). So Develop step 4 adds no branch.
- The Not formed items add no branch. The stretched fill grid has no relational form. The other corners and swapped count axes are parameter values that the pairs fix. A split by content has no marker in any input.
- Deletions that change nothing on the pairs, all kept:
  - `fill_index.a` stays because quadrants that are not square need a per-axis wrap (witness `fill-index-past-fill-grid`).
  - In `ink_box.cell`, `!params.bg(Col)` and `params.pattern_quad(Q)` state the `$TileByBbox` claim.
  - In the wrap clause, `params.fill_quad(Q)` names the grid being wrapped.
  - In `Determine`, `!params.bg(Col)` and `!ink_at(E, Q)` state the `pattern-quadrant` claim (both bg and non-bg cells).
  - I removed `ink_count.domain`: the count quadrants always hold ink, and the tally needs no domain.
- The run witnesses 4 cases: the concept case and one case for each single branch. No combination of two non-concept branches gives an output that a case with fewer of them does not give on any input of the task or of the witness file. `witness` and `audit` report no unseparated or unshown case.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
