# ce8d95cc

## Departures
- I added the branch `bg=DominantColor` (`// @derive DominantColor: variant concept`, `@relaxed full-lines`) on `bg`, which `$GapCollapse` and `$Rebuild` read: `derive` reports that it fits, and Develop step 4 says to keep a fitting derivation as a branch. Its witness `bg=DominantColor` is train0 with colors 0 and 1 swapped. On it, `$GapCollapse` with the stored `bg` 0 sees no background, keeps every row and column, and returns the input unchanged. With the derived `bg` it gives the concept's output. I judged it `variant` because it is a color permutation of a train input, and it breaks `full-lines` at the stored background 0. The verdict is `concept`.
- The analysis says `$GapCollapse` and `$Rebuild` are defined on every input. In the solver they are not. `$GapCollapse` is undefined where the rows (or columns) of one background run differ. `$Rebuild` is undefined where the input's background lines differ, and where it needs a background line but the input has none, for example when no cell has the stored `bg`. The branch `@rule` lines say this. The reason: a run that collapses to one line, or a synthesized background line, has to take its cells from somewhere. Choosing one member of a run, such as the first, would hide an orientation in the program. So each output line takes every input line that falls on it, and several different colors on one output cell make the output undefined. On the task inputs and both Analyze witnesses, every case is defined and gives the output `witnesses.json` lists.

## Judgments
- Parse: the solver works per axis. Each input line, taken as a row or column through `split`, gets its output line from per-direction counts (`Tally`, then `DirPack.axis_pos`). Each output cell then comes from the crossing of its row's and its column's source lines. The precedent, e1baa8a4, does the same counting on cells. I used lines because `$Rebuild` has to create output lines that no input line falls on, which a per-cell placement cannot do. With lines, all three cases share one placement and one `out` clause, and reusing that comes before precedent in the parse priorities.
- `dedupe-columns` reads "in the result of dedupe-rows", but the solver finds column boundaries on the input grid. The two give the same result: a row removed by dedupe-rows is identical to a row that is kept, so two adjacent columns differ in the deduped grid exactly when they differ in the input.
- Not formed in `analyze.md`: I formed no branch from it. Columns-first and keep-another-row-of-a-run both describe the concept's model, so they would fail Equivalence. Keep-distinct-rows and fixed-factor downscaling both fail Fit on the train pairs.
- `store` reported no value to store. Every derived relation varies with a line or a position.
- `$Rebuild & bg=DominantColor` is a case, but `run_dl` does not count it as witnessed. Both its non-concept branches are rejected (every verdict on them is `concept`), and the rules do not let a case that combines two rejected branches be witnessed. I built `edge-line-recolored` (edge-line with its field recolored to 7) to show it. It did separate the case, but the runner still did not count it as witnessed, so I removed that witness.
- `Determine.bg`: for each train input, the commonest color; a color is kept when it is the commonest in every train input (`Mode`, then the defect `clash`). I first used the color of the grid corners, from `lines-apart`. The plan rejected it because at witness `edge-line` the top corners lie on a line.
- `deletions`: 11 deletions changed nothing. I kept all of them.
    - The `a` columns of `source` and `bg_line`, `perp(A1, A2)`, and both `axis_of(D, A)` atoms keep rows and columns apart. A row and a column can be the same axis-only position in a degenerate frame, and without `perp` a row would cross another row.
    - `placed`, `frame.extent` and the `$Rebuild` clause of `source` create background lines that no input line falls on. The task inputs never need one; witness `edge-line` does.
    - In Determine, `ex_out(E, _, _)` restricts the check to train examples, as the test-inputs rule requires. `clash` does nothing here only because every train input has the same commonest color.
- Hints: lint gave one finding, a missing `@claim` on the `bands` Tally instance, which is not a construction. I added `// @claim dedupe-rows dedupe-columns`. No other hint fired. Every run took 2 s or less, so there is no performance issue.
- Keywords: `lines`, because the model works on whole rows and columns.

## Unsettled
- The derived branch `bg=DominantColor` competes with an alternative derivation, the color the scene calls the field (for example, the color of the cells that lie on no line). Settling it would take a witness where the commonest color is not the field, such as a grid packed with lines. On such an input the generator's output is the concept's either way, so only `$GapCollapse` and `$Rebuild` would separate.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
