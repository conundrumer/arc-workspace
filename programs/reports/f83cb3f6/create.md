# f83cb3f6

## Departures
- The witness file renames the Analyze witness `background=DominantColor` to `dots-outnumber-background`, and keeps it as a further witness of the `background=DominantColor` branch: `derive` recorded its own witness under the branch's name (train0 with 0 and 1 swapped). The `@derive` line records the plausibility and verdict of that witness.
- The witness file adds `dots-in-one-column` (two dots on one column, one on each side of a full wall). The audit reported that no run showed `wall_color=RarestColor` defined and differing from `$WallByLine`. On this input the rarest color is the dot color, whose cells lie on one column, so `wall_color=RarestColor` takes the dots for the wall. `$WallByLine` finds two colors on one line and is undefined. The concept pulls the dots to the 8 wall.
- `$StoredAxis`, `$Stack`, `$HoleKeep`, `$HoleThrough` and `$StoredDotColor` have no constructor: `analyze.md` gives each of them no witness, since each fails Fit.

## Judgments
- Witness `background=DominantColor` (written by `derive`: train0 with 0 and 1 swapped) is `variant`, verdict `derived`, `@relaxed dots`: it is a color permutation of a train pair, so the generator pairs it with an output on background 1, which is the derived branch's output. At the stored background 0 the 1 cells are non-background cells that are no dots of one color.
- Witness `dots-in-one-column` is `ordinary` with verdict `concept`: it breaks no scene claim. It is a further witness of a `@derive` branch, so it has no `@witness` line.
- `color_line` keeps `// @ignore: store`: `store` reports it holds 8 on every input. That color is the wall's, which the concept case already stores as `wall_color`. Storing it in `$WallByLine` gives the concept case's model.
- Keywords `move lines`: the dots translate onto the wall, and each line across the wall acts on its own.
- Hole-drops has no clause of its own. `approach` pairs a dot only with a wall cell on its line across the wall, so a dot whose line meets a hole has no pile.
- The `out` clause requires `wall_axis`, so the model is undefined where the wall cells are fewer than two or lie on no one row or column, as `analyze.md` gives.
- Determination: `background` is the commonest color of every train output (`Mode`), and `wall_color` is the color whose cells lie on one line in every input, through the shared `Parse`. Both give their stored value, and the plan lists no action.
- Deletions that change nothing on the pairs, all kept: `!params.background` in `color_line` and `rival_line` (the pairs have no background on one line and no second color on one line); `wall_axis` and `perp` in `approach`, and `!wall` in `dot` (they matter only for a dot inside a hole cell or for wall cells, which the pairs do not separate); `past` and its negations (train0 col 9 has a pile of one color, so nearest and farthest agree); `wall_axis(W, _)` in `out` (the undefinedness guard); the determination defects (the pairs give one value). The negation `!params.background` in `off_line` was removed, since `color_line` already excludes the background.
- No hint fired, and no performance issue: every run finished in 2 s or less, apart from `deletions` at 11–14 s.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
