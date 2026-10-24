# d94c3b52

## Departures
- Witness `gap=SepThickness`: in `witnesses.json` the concept case gives the input unchanged. The solver's concept case is undefined there. This rests on analyze.md's own statement, "the concept is undefined on an input where no tile, or more than one tile, holds `key_color`". With the stored gap 1, the 22×22 grid admits no tiling: the inset frame is 20 cells and 21 is not a multiple of 4. So no tile holds 8, and `out` is empty because its keep-clause needs `key.value`. `record --all` rewrote the groups to match.
- A `@derive TileDim` branch on `gap` was found and then dropped. `derive` reported that it fits, which analyze.md does not give, and it was held under Develop step 4. It is now `@ignore: derive TileDim` because it fails Subsumption (see Judgments). Its witness `gap=TileDim`, which `derive` wrote, had the same input as `gap=SepThickness`, so I removed it from the witness file.
- Added the witness `gap-three-wide`: the left 4×4 tiles of train0 with lines 3 wide. It separates `gap=SepThickness` (defined: the copies at (1,3) and (2,1) turn 8) from `gap=TileDim` (undefined) and from the stored gap (undefined). I built it to resolve the witness report "no witness separates `gap=SepThickness` from `gap=TileDim`". It stays as a second witness of `gap=SepThickness`.
- Added `@store cell: variant concept` (`@relaxed tiling`) on `link.cell`, the tiling's tile set, which `store` printed. Its witness `link.cell=stored` is train0 turned a quarter turn. The stored 4×6 tile set drops the links that the rotated 6×4 tiling needs.

## Judgments
- Choice = `[i: Identity, p: Precedence]`. The concept branches are `Exact` (my name) and `KeepKey` (my name). The other branches are `$TranslateMatch` and `$LinkOverMatch`. All four combinations fit every pair. `$TranslateMatch & $LinkOverMatch` takes two rejected branches, so it is not a witnessed case. The run reports 7 witnessed cases of 96.
- The analyze.md branches that fail Fit (`$CongruentMatch`, `$DiagonalSpans`, `$KeyEndpointSpan`, `$KeyNotEndpoint`, `$FillLinkTile`, `$StampKeyShape`, `tile_size=SepTileDim`, `tile_size=TileDim`, `link_color=OutNewColor`) have no constructor and no case.
- Under Not formed in analyze.md, "links only between consecutive key-shape tiles" states one model, but that model is equivalent to the concept. Combined with `$LinkOverMatch` it also gives the concept's output, because the middle copy ends both of its consecutive spans. So it fails Equivalence and is not formed. The other items there state no model of their own: "rows alone or columns alone" is an orientation that every value covers, the component parse gives no tiling rows, and the rest are scene parameters.
- `gap=TileDim` fails Subsumption. On every input I tried, including the analyze witnesses and five built grids, it was either undefined or equal to `gap=SepThickness`.
- `@derive` verdicts: `DominantColor`, `SepThickness` and `RarestColor` are `variant derived`, as analyze.md gives them. Each line carries the `@relaxed` lines that analyze.md gives.
- `@store cell` is `variant concept`. Train0 turned a quarter turn is a D4 variant task. It breaks `tiling`, which says 4 tiles down and 6 across, and the generator would pair it with the derived tiling's output.
- The header leaves out `@scene key-shape-repeats`. Style admits a `@scene` line only where a `@claim` or `@relaxed` denotes it, a rule's text depends on it, or a branch replaces it, and none of these holds for this claim.
- Parse: the tiling (`uniform_inset`, `crop`, `divide_by_size_2d`) is a `Parse<Key>` comp, because both the program and Determine read it. This follows the edge-inset-then-divide precedent of 33067df9.
- Program components: `Unanimous` serves `one-key-tile`. It also makes the concept undefined where no tile, or more than one tile, holds `key_color`, as analyze.md states. `KeyedSetCompare` serves `match-takes-key-color`, `Ray` serves `between-takes-link-color`, and `Bbox` serves `$TranslateMatch`'s match-takes-key-color.
- `linked` reads `Ray.ray` with `Q != P_tile` rather than `Between.between`. `Between` counts a mark as being on its own ray, so every key-shape tile would come out as between, and `$LinkOverMatch` needs strictly-between.
- Determine: `background` is the commonest input color (`Mode`). `gap` is the least margin between the frame edge and a non-background cell (`Extremes`). `tile_size` is the least size whose tiling leaves no train shape cell on a line (`Extremes` over the sizes with no `stray`). `key_color` is a recolor that the input already holds, and `link_color` is a recolor that the input lacks. The plan reports no actions, and the determination check passes for all five parameters.
- Hint `head-repeat` on `tiling.tile_size`: kept, with `@ignore`. Each candidate size keys its own Parse instance, and Parse reads the size from that input.
- Deletions: the negations `!linked` and `!copy` in the shared `paint` clauses, the `$KeepKey` and `$LinkOverMatch` paint rules, and `key.value` in the keep-clause cover structure the pairs never show: no three collinear copies, and a key tile always present. The witnesses exercise them, and they stay. The `ex_out(E, _, _)` atom in `tiling.grid` is the handbook's rule that contradiction clauses range over train examples.
- Performance: the solver runs in about 2 s. The Determine tiling search raised one run to about 19 s, which is acceptable.
- Process slip: I piped one `run_dl.py` run to `grep`, against the instruction to read run output whole. A later unpiped run showed the full output.

## Unsettled
- `gap=TileDim` was dropped under Subsumption on a search that found no separating input. It is not a proof. A layout on which TileDim gives a gap that SepThickness does not, with the model defined there, would bring it back as a case. Knowing the conditions under which TileDim is defined would settle it.
- `$TranslateMatch & $LinkOverMatch` is a case of the solver but not a witnessed case, because both of its branches are rejected.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/d94c3b52/witnesses.json`, witness `gap=SepThickness`, group `concept`: the grid should be `null` (undefined), by analyze.md's statement that the concept is undefined where no tile holds `key_color`.

## Tickets filed
- none
