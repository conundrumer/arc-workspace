# c8cbb738

## Departures
- `$CornerBackground` reads the background from the corner cell that the `@open` parameter `bg_corner` gives, and all four corners are stored. The Analyze report gives that branch the top-left cell and no parameters. That reading fixes an orientation in the program, and an orientation is task data. Every corner fits every train pair, and the pairs do not separate the corners, so each one is an open value. So on `mark-on-corner` the case gives two grids: the input back (at `DIAG_TL`) and the concept's 3x3 overlay (at the other corners). The Analyze file gives the input back alone. `witness --file work/task/c8cbb738/witnesses.json` reports this difference, and only this one.
- I added a choice point `Figures` with the branch `$CountedClasses` and the parameter `marks_per_figure(4)`, with witness `stray-dot`. It comes from the Not formed item "a filter that keeps only color classes of `marks-per-figure` cells", which states one model that meets Fit and Relational form (Develop step 3).
- I added `@derive TileCount` and `@derive TileDim` on `marks_per_figure`, with witnesses `marks_per_figure=TileCount`, `marks_per_figure=TileDim` and `diagonal-pair`. `derive` lists both as derivations that fit, and Develop step 4 has me keep each one as a branch.

## Judgments
- Concept constructor names: `LargestSquare` (output-frame), `CommonestBackground` (background), `EveryColorClass` (figures).
- The other Not formed items are not formed:
    - Two figures of one color: the split into four-mark figures is not unique, so the item states no one model.
    - Layer order and rounding: the pairs give no order and no direction, so these items state no one model.
    - Centroid alignment: a mean has no relational form.
- `stray-dot` is `borderline concept`, `@relaxed one-figure-per-color`. A one-cell color class breaks the four-mark scene. Where the generator drew such a class, I judge that it stacks it like the other figures, onto the output's empty center.
- The witnesses of the derived branches are `borderline concept`, `@relaxed one-figure-per-color`. These derivations read a count from the grid's tiling, which the task does not have. They fail no case condition: Fit holds, and `diagonal-pair` and the derive witnesses show the cases defined and different. So the branches stay, and no `@ignore: derive` line applies.
- `store`: neither `frame.extent[a]` nor `class_size.tally[n]` printed a line to add (no image changes the axis column, and no case that takes the tally fits). So the solver has no `@store` branch.
- The lint hint "case section" on the `parse.cell` clauses was correct. Each clause now stands under its background marker.
- Determination: `marks_per_figure` is the commonest class size of each input, where every input agrees on it. The first version kept a size only where every class had that size. `determination-plan` showed that this version gave nothing with `stray-dot` added. `bg_corner` is determined by the values at which the model fits every train pair, as the plan gives it.
- Parse: the commonest-color `Mode` and the class `Tally` are in `Parse<Key>`, which the program (keyed by background reading) and `Determine` (keyed by example) share.
- Deletions:
    - I removed three items: `bg(Ky, _)` in `class_cell`, because a background always exists at each key; `class_size.domain`, because `Tally` counts the item keys without it; and `frame.cell` on the landing cell, because `out` already ranges over frame cells.
    - These items stay because the pairs never exercise them: `uncentered`, the square test in `square_side`, the size test of `$CountedClasses`, `params.bg_corner` in the corner background, `ex_out` and `unshared` in `Determine`.
- Keywords: `overlay color-class bbox rank count`. `count` is for `$CountedClasses`.
- 11 of the 24 combinations are witnessed cases. In each of the others, the non-concept branches only add their changes to one another on every input the pass ran.
- Once I piped the output of `run_dl.py record` to `tail`, which my documents do not permit. The record calls that followed I ran whole.

## Open
- Whether a reviewer wants `@ignore: derive TileCount` and `@ignore: derive TileDim` on `marks_per_figure`. Those derivations fail no case condition, so this pass kept them. A rule that rejects a derivation from a structure the task does not have would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-834_task_c8cbb738_create.md
