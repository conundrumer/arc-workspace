# fd4b2b02

## Departures
- The concept branch of `bar` is the constructor `$OneBar`. The `background` choice point is the `@derive DominantColor` line on `background`, so its branch is `background=DominantColor` in the witness file, as `analyze.md` names it: the derived branch needs no constructor of its own.
- `record --all` rewrote the groups of `two-bars` to the listed form. It grouped `background=DominantColor` with `concept`, and the case `$PerBar & background=DominantColor` with `$PerBar`. The grids are the same as the ones `witnesses.json` gives, and `witness --file programs/reports/fd4b2b02/witnesses.json` reports no difference.

## Judgments
- The chain is a `Propagation` walk over candidate bars. A candidate bar is the cell at its corner nearest the chain's start, its box in that cell's frame, and its color. One step takes the near corner past the bar by its extent on each axis (`jump`), reflects the box across the chain's diagonal (`apply` with `diag_flip_of`), and takes the `partner` color. The precedent for this is the walk in 136b0064. Recursion is banned, and `Propagation` is a construction, so no claim rests on it. For a solid rectangle, the reflection across the chain's diagonal gives the same bar as the quarter turn that the concept names.
- `clip-at-edge`: no edge leaves a node whose near corner is outside the grid, and the drawing keeps only grid cells. The deletions run showed that an `in(N2, _)` test on the edge target changed nothing, so I removed it.
- The concept case keeps the input's cells and draws only chain bars past the input bar (`!start`). This matches `witnesses.json`, where the bounding box of two bars is not filled. Undefinedness comes from `Unanimous` (two ink colors give no bar), from `bar_defect` (a component with two colors under `$PerBar`, or a bar color with no `partner` row), and from two colors at one cell.
- Deletions findings: the `bar_defect` rules, `!bar_defect` and `!start` stay. The pairs do not exercise them, but the witnesses do. The `shape.d` column and `diag_axis_of(D, Da)` in `shape` stay, because they keep the candidate shapes to the two shapes each direction takes. I removed `in(P, _)` in `out`, because both branches bind `P`. The bound enumerator `diag_dir_elem(D)` stays, as the tool says.
- The hint `single-consumer` on `defined` was correct. I inlined `defined` into `out`.
- `background`: I renamed the stored relation from `bg` to `background`, the concept file's name. `derive` found `DominantColor`, and I gave its line `variant derived` with `@relaxed one-bar`, from the witness that `analyze.md` gives. The plan lists `background (DominantColor exact)`. I wrote no determination relation for it, because the proposer reads the same fact that a reader of the concept reads: the field color around the bar.
- `partner`: the sweep reports that the train pairs do not pin the set, because single-row changes for colors that no bar has still fit. No reader of the concept takes those rows, so `partner` is not an open parameter. `Determine.partner` reads it from the evidence as the bar's color paired with the color that the output adds, and the plan reports it as determined.
- `$Lattice` and `$ColorByAxis` have no constructor. They fail Fit (train0, and train0 with train2), as `analyze.md` gives, and they have no witness.
- `store` printed no line to add: `chain_cell[col]` varies by `p`.
- Keywords: `bbox` (the bar is a bounding box), `objects` (`$PerBar` components), `walk` (the chain), `d4` (each next bar is the last one reflected), `mapping` (`partner`).

## Unsettled
- The case `$PerBar & background=DominantColor` is not witnessed (3 of 4 cases are witnessed). A witness with two bars on a background other than 0 would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
