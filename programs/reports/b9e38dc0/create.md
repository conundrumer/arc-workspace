# b9e38dc0

## Departures
- `cup` scene claim: the solver derives what `probe.py` takes as given for each grid. The wall ends are the cup cells that touch exactly one other cup cell. The flow is the cardinal direction along which the last step into each end advances. Each wall is named by its side across the flow. The concept's "walls end on one line" does not hold in train1, where the ends are (2,7) and (7,8), so the mouth is the line of the end that lies further back along the flow. In train1 this puts the mouth at col 8, where the probe uses col 9. The outputs are the same on every pair and on both witness inputs.
- `walls-repeat` and `widen`: the probe uses a hand-picked chain for each wall, and when the chain has fewer than two steps, it falls back to the last step alone. The solver walks each wall back from its end. The walk continues while the line behind holds exactly one cup cell that touches the current cell and lies no further out. The pattern is the shortest run of last steps whose repeats agree with the steps before it, within that walk. Train1's lower wall, (6,9) to (7,8), needs this reading: if the walk went further back to (7,10), no pattern would repeat. The continuation cells are the same as the probe's on every pair.
- `liquid` scene claim adds "no cell of that color lies outside it". In train2, both 3 and 6 have cells inside the cup, and the concept's text does not separate them. The probe separates them by whether a flood from the color's cells leaks.
- `pour` rule adds "or lies beyond one". The probe feeds from the nearest cell between the walls whenever the cell behind is not between them.

## Judgments
- Case set: the four combinations of `Feed` {`FedStream`, `$GeometricStream`} and `Shadow` {`CupFill`, `$CupShadow`} all fit. Both witnesses have verdict `concept`, so `$GeometricStream & $CupShadow` is a case but not a witnessed case.
- Branches with no witness are not constructors, because each fails Fit as `analyze.md` gives: `$DiagonalCone`, `$StraightStream`, `$LastStepOnly`, `$NoBlock`, `$RefillBehind`, `$Flood8` and `$StoredColors`.
- Not formed, the downward stream: this reading fails Fit at train1 and train2, so it is not a case.
- Not formed, the fitted straight wall: this reading has no relational form, because a fitted slope counts nothing the task has.
- Params is empty. `derive` and `store` find nothing, the sweep finds nothing, and the determination plan lists no actions, so the solver has no Determine comp.
- Hint `head-repeat` on `advances(D, D)`: I removed `advances`. The flow and the walk back now test "advances along d" with `nearer`.
- Hints `case section` on `wet_cup`, `liquid` and `pour`: I moved the shared cup fill above the markers, and `pour` now stands under `// --- $FedStream ---`.
- Hint `single-consumer` on `run_start`: I removed `run_start`. `pattern_break` now asks whether some run cell lies at or behind the line of Q2.
- Deletions: I removed three atoms that other atoms already imply: `held(P)` in `liquid_color`, `between(F)` in `feed`, and `stream(X)` in the `$FedStream` liquid clause. The atoms that remain and that the pairs never exercise each state part of a claim (for example `back_fork`, the run-line bound in `pattern_break`, the `!dry` tests, and the `liquid_color(_)` gate that makes the output undefined where no liquid is found). I kept them.
- Check on an input outside the task: train1 with five more background rows. The lower wall continues diagonally from (7,8) to the grid edge, and the stream fills inside it.
- Keywords: `chain` for the walk along each wall, `wallpaper` for the wall continued by its repeating step pattern, `rank` for the largest object, `enclose` for the cup's closed region, `flood` for the cup fill, `cast` and `walk` for the line-by-line stream, and `objects`.
- Performance: each run takes about 1 s.

## Open
- The probe puts train1's mouth at the narrowest line (col 9). The solver puts it at the end that lies further back (col 8). An input with an obstacle between those two lines, on a wider flare, could separate the two readings. The Analyze report does not list this as a choice point, and no witness tests it. A witness built on a widened train1 flare would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
