# df978a02

## Departures
- The witness file's group names are the ones `record --all` writes (`$MostCells`, `$BiteTip`, `$GrowPastBack`, `background=stored`, `grow_width=derived`), not the long name lists of `witnesses.json`: the [Witness file](docs/handbook/solver-file.md#witness-file) form asks for the fewest names whose cases give each output. Every grid is unchanged, and `witness --file programs/reports/df978a02/witnesses.json` reports no difference.

## Judgments
- A shape is a color class, not a connected component: in train0 the right `9` shape touches only at corners, and every input gives each shape its own color.
- The parse finds no center cell. A tip is a front cell, the shape's extreme cell toward a direction, from which a ray across the background first stops on the opposite-facing front cell of another shape. This gives the concept's output on `flat-front`, where the front line of the left shape holds two cells, and on `grow_width=stored`, where only two shapes stand.
- The grown line is relational. A `Ray` from the anchor across the winner's axis gives each half-width k that reaches k cells on both sides. A `Tally` of each such run is compared with the count of tips taken. Where no run matches, because the count is even or the line leaves the grid, no line exists and the out guard leaves the case undefined, as `analyze.md` states.
- The concept fixes the winner's uniqueness through `Unanimous` over `ArgExtremes.high`, so a tie leaves the case undefined.
- `grow_width=stored` is a `@store` branch on `grow_width`, the relation that `store` reports. `background=DominantColor` is the `@derive` branch that `derive` reports. Neither has a constructor.
- `store` printed no line to add for `reach`, `spread.cell` or `taken.tally`, and the other values it lists vary by key. No other store branch is held.
- Determination: `sweep` gives `background` the unique value 8. The plan lists `background (DominantColor exact)` for a determination relation only where the proposer reads a fact other than the concept's. The concept's field is the commonest color, which is the same fact, so no `Determine` comp is written. The fit-every-train-pair determination gives 8.
- `deletions`: the `domain` rules of `taken`, `run`, `size` and `back`, `facing.cell`, and the `s` column of `behind` were removed, because a cell has one color, `stop` ignores the domain, and no tally reads a zero count. The `reach` atoms and the `!line` test in `out` stay, because they state that the line must be symmetric and inside the grid, and that line cells take the winner's color. The enumerator guards on the branch clauses stay, because they bind each clause to its case.
- Keyword hint: the first run's `@keywords` line used commas. With spaces, every keyword is in keywords.md.
- The other combinations of branches all fit; `witness` reports no unseparated pair and no unshown case among the 6 witnessed cases.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
