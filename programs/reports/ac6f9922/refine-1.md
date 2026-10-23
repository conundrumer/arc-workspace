# ac6f9922

## Departures
- The witness file has a witness that the Analyze file lacks, `uneven-bars` (borderline, verdict `$WindowBands`, relaxed `window-grid`), and the solver has a `@witness` line for it under `WindowBands` (create). In the left column, the bar between the two rows of windows is one row higher than in the right column, so no bar row runs the full width. `$WindowBands` gives `2 3 / 4 4`, `$DividerTiles & $BackgroundEmpty` gives `2 3`, and the exact-row cases are undefined. Without this witness, no run shows `$WindowBands` defined and differing from `$DividerTiles`. It holds: `witness` and the audit report no unseparated pair and no case without a defined, differing run, so `$WindowBands` meets Subsumption.
- In the witness file, `record --all` wrote the groups with the combined cases, for example `$DividerTiles & $WindowFill` gives `2 4 / 4 1` on `missing-window` (create). It holds: `witness --file work/task/ac6f9922/witnesses.json` reports no difference.

## Judgments
- Reconcile: the solver passes every pair, lint, the audit, `witness`, and `witness --file work/task/ac6f9922/witnesses.json`. The two departures of create.md hold. No `## Fixes elsewhere` item in another task's report names this task.
- Cases: all 20 combinations of `Background` (2), `CellUnit` (`Window{region, grouping}`, 2×2, or `DividerTiles`) and `EmptyColor` (2) fit every pair (create). This pass checked it again from the rows of `out` on each pair input: each of the 20 cases gives the expected grid on train0–2 and test0. Because every combination is a case, the solver has no `impl_choice`. It keeps only the `window_grouping_choice` enumerator, which `unit_cell` reads. The runner witnesses 7 of the 20 cases.
- The constructors of the concept branches are `EdgeColor`, `Window`, `ClosedRegion`, `SameExtent`, and `BackgroundEmpty` (create). The branches that fail Fit in the Analyze report (`$MarkBands`, `$StoredEmpty`, `$BarEmpty`, `$StoredExtent`) have no witness and no constructor.
- Not formed, a D4 transform of the output picture: it fails Equivalence (create). A D4 transform of the whole task moves the input and the output picture together. So across the generator's tasks the stored transform takes only the identity, and the model is the concept's.
- Not formed, a window with two mark colors or a bar-colored mark: the item gives no reading, so no claim forms (create). Every case is undefined there, through the `mark` Unanimous clash.
- Each unit (window or tile) is named by its bounding box, so windows and tiles share one path for color, banding and placement (create). Rows and columns are classes of one `Canon<UnitAxis>`. Exact grouping (`$SameExtent`, and also `$DividerTiles`, whose tiles share their extents exactly) uses `equiv` on equal extents. `$WindowBands` uses `edge` on a shared line, as the 0a1d4ef5 precedent for overlap bands does. `mixed` makes the exact-row reading undefined where two rows share a line, because `OrderFrame` requires bands that do not interleave.
- `$WindowFill` reads a unit's fill as the one color of its cells that have a 4-neighbor of the bar color (create). For a tile, this counts the tile's own bar-colored cells. So `$DividerTiles & $WindowFill` gives the bar color for a tile that is all bar color (`missing-window`).
- Bar-color and commonest-background ties are undefined: the `Mode` result goes through a `Unanimous` (`bar_color`, `sole_commonest`) (create).
- `uneven-bars` plausibility `borderline` and verdict `$WindowBands`: it breaks `window-grid`, and a reader would still see a 2×2 grid of windows (create).
- Hint `single-consumer` on `unit_color`: inlined into `out` (create).
- Simplify: `unit_band` only unpacked the record of `same_band.id`, so its readers in `mixed`, `layout` and `out` now read `same_band.id` directly. The comments in `out` now say "its band on one axis" and "and on the other", because the clause enumerates both axes. The pairs, the witnesses and the audit give the same results after the change.
- The two `same_band.equiv` clauses (`$SameExtent` and `$DividerTiles`) differ only in the key's pattern. They stay separate, because a clause does not range over choice tags through a disjunction, and `Canon` requires that the `$WindowBands` keys stay out of `equiv`.
- Deletions that change nothing on the pairs (create; `deletions` lists the same ones this pass, less the `impl_choice` atoms that create removed):
    - `mixed` and `!mixed`: kept, because `staggered-window` and `uneven-bars` need them.
    - `fill.b`: kept, because `$WindowFill` fills each unit on its own.
    - `broken_line.a`: kept, because the axis types the line.
    - `dir_elem(D)` in `rim`: kept, because it limits touch to the four cardinals.
- Keywords `decompose enclose rank` (create).

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- none
