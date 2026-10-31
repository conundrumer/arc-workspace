# fcb5c309

## Departures
- The witness file has a witness, `recolored-background`, that `witnesses.json` does not have. It is train0 with colors 0 and 1 swapped. On it, `background=DominantColor` is defined and the stored-background case is undefined: `witness` reported no run that showed `background=DominantColor` defined and differing from another case, and the witness `background=DominantColor` shows it only undefined.
- The witness file's groups are rewritten by `record --all` to name cases. `witnesses.json` names branches. `witness --file programs/reports/fcb5c309/witnesses.json` passes.

## Judgments
- The frames are found by `Outlines` keyed on each ink color. The frame color is the ink color whose every cell lies on an edge of one of its outlines, and the dot color is an ink color with a cell off its outlines. This keeps a 2x2 block of dots from counting as a frame, and keeps a dot that touches a frame from joining it. No pair has a 2x2 block of dots.
- Each score is a `Mode` over a frame's cells. The cases are the frame's dot cells (concept), its cells within the box (`$Area`), its border cells (`$SizeByBorderCells`), its interior cells (`$SizeByInterior`), and its dot clusters by component id (`$CountDotClusters`, with `$Adj4` and `$Adjacency8`). A tie keeps both frames, and the crops then conflict, so the model is undefined at a tie, as `analyze.md` gives.
- `Choice` is the record `[s: Selection, u: CountUnit]`, with `size-measure` nested under `$SelectLargest` and `adjacency` nested under `$CountDotClusters`, as `analyze.md` nests them. `impl_choice` leaves out each `$SelectLargest` & `$CountDotClusters` combination, because `analyze.md` gives its model as `$SelectLargest`'s model alone.
- `recolored-background`: plausibility `variant`, because a color permutation of a train pair is a variant task. The verdict is `background=DominantColor`, because the generator's output on a color-permuted input is the permuted output, and that is the derived branch's output. The solver has no `@witness` line for it, as with any further witness of a `@derive` branch.
- The determination of `background` reads the train outputs alone: it is the color, other than the border color, that stands inside the border of every train output. The plan listed it because `DominantColor` covers the value from a fact the concept does not use.
- `deletions` reported 6 deletions that change nothing. These are `box_edge` in `on_outline`, `!dot_color` in `frame`, both `interior` tests in Determine's `fill`, and `missing` with its negation. The pairs do not instantiate the structure that each one tests: no dot color lies wholly inside frame boxes, no dot-colored outline exists, and every train output gives the same fill color. Each one states part of a claim, so all stay.
- Keywords `crop objects border select rank`: the extremum over dot counts is `rank`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
