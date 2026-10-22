# ac6f9922

## Departures
- The witness file has a witness that the Analyze file lacks, `uneven-bars` (borderline, verdict `$WindowBands`, relaxed `window-grid`). It also has a `@witness` line under `WindowBands`. In the left column, the bar between the two rows of windows is one row higher than in the right column, so no lattice row runs the full width. `$WindowBands` gives `2 3 / 4 4`, `$DividerTiles` gives `2 3`, and the exact-row cases are undefined: `witness` without `--file` reported that no run showed `$WindowBands` defined and differing from `$DividerTiles`, and this witness shows it, so `$WindowBands` meets Subsumption.
- In the witness file, `record --all` rewrote the groups with the combined cases, for example `$DividerTiles & $WindowFill` gives `2 4 / 4 1` on `missing-window`. `witness --file work/task/ac6f9922/witnesses.json` reports no difference.

## Judgments
- Cases: all 20 combinations of `Background` (2), `CellUnit` (`Window{region, grouping}`, 2×2, or `DividerTiles`) and `EmptyColor` (2) fit every pair. This was checked from the rows of `out` on each pair input, one grid per input across all cases. Because every combination is a case, the solver has no `impl_choice` and keeps only the `window_grouping_choice` enumerator, which `unit_cell` reads. The runner witnesses 7 of the 20 cases.
- Concept branch constructors are named `EdgeColor`, `Window`, `ClosedRegion`, `SameExtent`, and `BackgroundEmpty`. Branches that fail Fit in the report (`$MarkBands`, `$StoredEmpty`, `$LatticeEmpty`, `$StoredExtent`) have no witness and get no constructor.
- Not formed, D4 transform of the output picture: this fails Equivalence. A D4 transform of the whole task moves the input and the output picture together, so the stored transform takes only the identity across the generator's tasks. The model is then the concept. (a251c730's create pass reasons the same way.)
- Not formed, a window with two mark colors or a lattice-colored mark: the item gives no reading, so no claim forms. Every case is undefined there, through the `mark` Unanimous clash.
- Each unit (window or tile) is named by its bounding box. This lets windows and tiles share one path for color, banding, and placement. Rows and columns are classes of one `Canon<UnitAxis>`. Exact grouping (`$SameExtent`, and also `$DividerTiles`, whose tiles share their extents exactly) uses `equiv` on equal extents. `$WindowBands` uses `edge` on a shared line, which follows the precedent 0a1d4ef5 sets for overlap bands. `mixed` makes the exact-row reading undefined where two rows share a line, because `OrderFrame` requires bands that do not interleave.
- `$WindowFill` reads a unit's fill as the one color of its cells that have a 4-neighbor of the lattice color. For a tile, this counts the tile's own lattice-colored cells, as the probe does. So `$DividerTiles & $WindowFill` gives the lattice color for a tile that is all lattice (`missing-window`).
- Lattice and commonest-background ties are undefined: the `Mode` result goes through a `Unanimous` (`lattice`, `sole_commonest`).
- `uneven-bars` plausibility `borderline` and verdict `$WindowBands`: it breaks `window-grid`, and a reader would still see a 2×2 grid of windows.
- Hint `single-consumer` on `unit_color`: inlined into `out`.
- Deletions that change nothing on the pairs:
    - `mixed` and `!mixed`: kept, because `staggered-window` and `uneven-bars` need them.
    - `fill.b`: kept, because `$WindowFill` fills each unit on its own.
    - `broken_line.a`: kept, because the axis types the line.
    - `dir_elem(D)` in `rim`: kept, because it limits touch to the four cardinals.
    - `impl_choice` atoms: removed together with `impl_choice`.
- Keywords `decompose enclose rank`.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-69_task_ac6f9922_create.md
