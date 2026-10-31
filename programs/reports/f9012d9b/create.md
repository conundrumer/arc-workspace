# f9012d9b

## Departures
- `$CopyNeighborTile` stays a case of the solver. `analyze.md` says it fails Subsumption: it rests on the concept being defined wherever that branch is. The witness check reported that no run showed the case defined and differing. Two built witnesses show it defined where the concept is undefined, so it meets Subsumption: `rows-no-period` (the rows have no period shorter than the grid, and the column period alone fills the hole with 3) and `split-residue` (one column residue shows 3 left of the hole and 5 right of it, and only the cells one period away are read).
- The witness file adds `second-solid-color`. The witness check reported that no run showed `$ColorHole & hole_color=RarestColor` defined and differing from `$HoleByShape`. On this input a 4x4 tile holds a 2x2 block of 5 that shows once. Two colors then form one solid rectangle, so `$HoleByShape` is undefined, and the rarest-color hole (4) fills to `2`.
- `$PeriodAndSymmetry` gives `Wallpaper` every D4 element as a transform, which is the precedent of 0dfd9992. `analyze.md` names reflections only. The analyze witness `hidden-residue` gives the same output under both readings, and `witness --file programs/reports/f9012d9b/witnesses.json` passes.
- The concept branches take the constructor names `ColorHole` (hole point) and `Lattice` (orbit-reach point). The `orbit-basis` and `period-source` points have no constructor: their non-concept branches (`$FillBySymmetry`, `$StoredPeriod`, `period=Period`) fail Fit and have no witness. `record --all` rewrote the witness groups to the solver's names.

## Judgments
- `@derive RarestColor: variant derived`, `@relaxed one-rectangular-hole`: this is the plausibility and verdict that `analyze.md` gives the `hole_color=RarestColor` witness.
- `second-solid-color` is variant with verdict `hole_color=RarestColor`. It breaks `one-rectangular-hole` because its hole is 4 and not 0. Its periods (4, 4) are shorter than the 5x5 grid, and the hole's residue shows at (4,1), so the generator's answer is `2`. Per the `@derive` rule it has no `@witness` line.
- `rows-no-period: borderline $CopyNeighborTile`, `@relaxed periodic-pattern`: a pattern whose row period equals the grid height is unusual. The column period still gives 3 to the hole, and that is the answer a person reads.
- `split-residue: foreign $CopyNeighborTile`, `@relaxed periodic-pattern`: one residue class holds two colors, so the input is not periodic, and the generator never makes it. The only defined output is the neighbor copy.
- `least-period` uses `OffsetInvariance.min_period` per axis. `analyze.md` (Not formed) treats the per-axis test as the same claim. On `split-residue` the per-axis test accepts column period 2, which the 2D claim rejects. Under both, the concept case is undefined there, so the output is the same.
- Determine: the first draft kept the color that every train input has and that no train output shows. That drew the hint `determine prediction` (the test reads inputs and outputs together), and the hint was right. `hole_color` is now the color that forms one solid rectangle in every train input, which is an input-only fact. That test is shared with `$HoleByShape` through `Parse<Key>`.
- `deletions`: I removed the redundant `hole_choice(H)` from `residue.edge`, because `si.min_period(H, ...)` grounds `H`. I kept the other entries:
    - `hole(H, P)` in the `$Lattice` and `$PeriodAndSymmetry` fills limits the fill to hole cells.
    - `wp.transform` and `wp.cell` are needed by `hidden-residue`.
    - The axis atoms and both disjuncts of the `$CopyNeighborTile` fill pick the period of the jump's own axis. The pairs have equal periods on both axes, so the pairs do not show it.
    - `ex_out` in `ex.cell` limits the determination to train examples.
- Lib name clash: the first run failed because `Reach` is a lib comp. The point's type is now `Source`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
