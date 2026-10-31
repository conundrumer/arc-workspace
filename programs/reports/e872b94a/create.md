# e872b94a

## Departures
- `$CountTable` under `$BackgroundRegions` reads its own table, `region_count_table`, with keys 2 to 5. Under `$Snakes`, it reads `count_table`, with keys 1 to 4. `analyze.md` names one `count_table`. This split rests on [Parameters across cases](docs/handbook/principles.md#parameters-across-cases): a task that both counted-parts branches fit gives the same output length to a snake count and to a region count that is one higher, so no single table is common to both, and the two tables are distinct parameters.
- `$AxisFromSnakes` is undefined on an input where snakes span both axes. `analyze.md` gives "each axis that some snake spans", which would give two grids there. The solver has no `out` column in which one case can give a grid per axis: [Types](docs/handbook/solver-file.md#types) allows none for this. On every pair and witness, at most one axis is spanned.
- In the witness file, the `count_table` assign of `table-entry-off-form` gives each cell as a Box `[t, b, l, r]` in the entry's own frame. `witnesses.json` gives it as `[row, col]`, which `witness` rejects for the `Position` column.
- `witness --file witnesses.json` reports that `background=DominantColor` denotes no case of the solver. `background` is read only under `$NonBackground`, as `analyze.md` nests it, so that branch's cases are `$NonBackground & background=DominantColor`. Their outputs agree with the grids `witnesses.json` gives that name.
- Two witnesses are added, and they are not in `witnesses.json`:
    - `region-table-entry-off-form` reassigns `region_count_table`. It shows `$BackgroundRegions & $CountTable` defined and different from `$BackgroundRegions & $Strip`. Without it, that case fails Subsumption.
    - `corner-region` shows `$BackgroundRegions & $Adjacency8 & $CountTable` defined and different from its `$Adjacency4` counterpart. The background cell that the corner-touching snake cells close off makes three regions under 4-adjacency and two under 8-adjacency.

## Judgments
- The strip length is the `extra_cells` frame (an `AxisFrame`) extended past one end by one cell per snake: `edge_outset` with the count, read through `box_extent`. This gives count plus `extra_cells` with no arithmetic, and it is defined when the count is 0. Both ends of both axes give the same length, so no orientation is chosen.
- `@derive` lines: `shape_color=RarestColor`, `background=DominantColor` and `fill_color=DominantColor` are each `ordinary concept`, as `analyze.md` gives them.
- `region-table-entry-off-form`: `ordinary`, verdict `$CountTable`. It is train1's input at a reassigned table, as `table-entry-off-form` is.
- `corner-region`: `borderline`, verdict `$Adjacency8`. Snake cells meet at a corner, which breaks `snakes-apart`. A snake that meets another at a corner is one snake, as `corner-contact` judges.
- `@ignore: case section` on `strip_axis`: `$AxisFromSnakes` reads the snake components at the `$Snakes` key under every counted-parts branch. That `$Snakes` is a component key, and it is not the case's branch.
- Deletions that change nothing:
    - `parts_key` and `tally.domain`, and `snake_count.domain` and `region_count.domain` in Determine: these give a count of 0 on an input with no snakes. No pair has such an input. They stay.
    - `ex_out(_, _, _)` in Determine's `axis`: this guard keeps `axis` empty where no example has an output. It stays.
    - `impl_choice(Ch)` in the first `strip.extent` clause: the other atoms ground the record. It was removed.
- No item under Not formed states a model that fits. No branch was added from that section.

## Unsettled
- The `sweep` command stopped at its 120 s timeout with no output, so no stored value was checked against the sweep: run `sweep` with a longer bound.
- The `extra_cells` determination is left to the fit set. A relation that keeps the tail lengths that no output contradicts reads inputs and outputs together, and the `determine prediction` hint flags it. A relation that reads the count of output cells past the snake count, from one end, would settle it.
- `determination-plan` lists `shape_color` (RarestColor) and `background` (DominantColor) as covered and asks for a determination relation for each. Neither has one. The concept stores both, and no fact of the inputs alone or of the outputs alone gives them apart from cell counts. A determination that reads which color forms the paths would settle it.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/e872b94a/witnesses.json`, the `count_table` assign of `table-entry-off-form`: it should give each position as a Box `[t, b, l, r]` and not as `[row, col]`.

## Tickets filed
- none
