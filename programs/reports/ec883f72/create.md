# ec883f72

## Departures
- The witness file has one more witness, `thick-wall`, that `witnesses.json` does not have: `witness` reported that no run showed `$SolidCore` defined and different from `$WallByShape` among the `$CoreCornerRays` cases. On `thick-wall`, the other object is a 2×2 block with one more cell. The solid-core cases read it as the wall and are defined. The `$WallByShape` cases find no 1-wide bent object and are undefined. So `$CoreCornerRays` meets Subsumption and stays.
- The Params relation is named `background`, as the concept's Parameters section names it. The `derive` run first recorded a witness `bg=DominantColor` while the relation was still named `bg`. That witness duplicated `background=DominantColor` from `witnesses.json`, so I removed it.
- Each `ray-blocking` branch and `$CoreCornerRays` applied together (analyze.md says only "the two branches' changes applied together"): the core-corner ray's start is the cell after its first wall cell, and the blocking branch then acts on the cells from that start to the grid edge.

## Judgments
- The single-consumer hint on `obj_color`: I inlined it into `core_color`.
- `background=DominantColor` is a `@derive DominantColor: variant derived` line with `@relaxed background`. It has no constructor. The witness for it is `background=DominantColor` from `witnesses.json`.
- `$CoreByRarity`, `ray_color=stored` and `background=SharedColor` fail Fit, as analyze.md gives. They have no witness and get no constructor.
- Not formed items of analyze.md:
    - Painting the bend cell itself fails Fit at train0 (3,3).
    - Core-corner rays that paint the pocket cells fail Fit at train0 (2,2).
    - Rays from the free ends of the arms give no model, because no diagonal points away from two neighbors.
    - So no branch was added for any of these.
- `thick-wall` is `foreign any` with `@relaxed wall`. The generator only draws a 1-wide wall that encloses the core, never a thick blob apart from the core. On such an input, no output is more correct than another.
- Determination: `determination-plan` asked for a relation for `background` from a fact other than DominantColor's. `Determine.background` keeps the one color that every train input holds. The core and wall colors change from pair to pair, so 0 is the only such color.
- `store` reported `corner_cast.dir` (every corner on every input) with no witness and no line to add. That clause has a `@workaround` mark and was not redesigned.
- The `deletions` items I kept:
    - `beam.blocked`, `params.background`/`in` in `$RayKeepsInk`, and the `pocket` clauses. The pairs never meet ink or an inward bend, and `stepped-wall` separates these branches.
    - `core(C, _)`, `wall(C, _)` in `out`. These make a case undefined where the scene cannot be read. `bent-core`, `background=DominantColor` and `thick-wall` show this.
- I removed `corner_cast.cell`. `stop` does not read the domain, and `corner_cast` uses only `stop`. This removal was the last solver edit, and it came after the one `deletions` run. The final pairs run passes.
- 36 cases are written and 10 are witnessed. The pairs run, `witness`, `witness --file witnesses.json` and `audit` all pass.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
