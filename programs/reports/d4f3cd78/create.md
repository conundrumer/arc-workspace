# d4f3cd78

## Departures
- `$PaintBackgroundOnly` leaves a gap that is not `background` unpainted, and the branch has a `@rule fill-gap` line that says so. The analyze.md text says the branch replaces only `fill-interior` and `stream-out`. But in witnesses.json, `$PaintBackgroundOnly` paints nothing on `background=DominantColor`, where the gap (7,5) is 1 at stored `background` 0. That grid is only right if the gap is painted only where it is background, so the solver follows witnesses.json.
- In `$EachObject`, a component's gaps are the non-corner border cells of its own box that are not cells of that component. They are not "every cell that is not `wall_color`". In the `two-gaps` grid from witnesses.json, the first component streams out through (5,7), (6,7), (7,5) and (7,6), which are cells of the other component. That happens only when each component is taken alone.
- `background=SharedColor` fits in this solver, although analyze.md says it fails Fit at train0. `background=VanishedColor`, which analyze.md does not list, also fits. Here `background` is read as a set, so the extra value 5 adds only wall cells, and no pair's interior or stream holds a wall cell. On one input, each of these derivations gives every color of that input. Every cell then counts as background, and the case gives `$Overwrite`'s output on every input. So both are recorded as `@ignore: derive` under Equivalence.
- I removed two witnesses from the witness file, `background=SharedColor` and `background=VanishedColor`, which `derive` had written. Their branches have no cases, and their input is the same grid as the `background=DominantColor` witness. `record --all` then rewrote the groups of every witness into case names.

## Judgments
- The concept constructors are named `ColorHull` (interior), `Overwrite` (obstacle) and `ToEdge` (stream-stop). analyze.md names them only as `concept`.
- `$SealedRegion` encoding: a sealed cell G is a gap when sealing G closes off cells that were not already closed off, and exactly one of G's neighbours is among those cells. The stream leaves G away from that neighbour. The interior is the cells G closes off. Cells closed off with nothing sealed are left out, so an already closed box gives nothing. In train1, both (5,5) and (4,5) count as gaps. Both give the concept's paint, so Fit holds.
- The "case section" hint (5 times): judged a false positive and kept with `@ignore: case section` on `basin_wall`, `hull`, `walls` and `object_box`. Each case reads `basin_wall` only at its own Interior value. The hint loses that key through the shared `water`/`gap` clauses. Precedent: c0f76784.
- One shared `Ray<Interior>` casts all four directions from every gap, and each paint clause keeps the ray whose direction is the gap's. The instance is shared because the per-case versions would differ only in the case name.
- Deletions: 16 deletions change no pair output. I kept them all. Corner exclusion, `closed`, the `background` tests, `stream.blocked`, the gap/direction join and the single-inlet gate are each part of a branch's model, and the pairs never exercise them. The `not_*` defect relations state "in every input".
- Determine: `background` is the commonest color of every input (Mode), `wall_color` the rarest color of every input (ArgExtremes.low), and `fill_color` a color some train output has that its input lacks. These are the facts the determination plan named, and after them the plan reports "No actions".
- `store` printed no `@store` line to add. Its `stream.cell` entry built no witness, so I held no `@store` branch.
- Keywords: `color-class` (the concept boxes every wall cell as one unit), `objects` (`$EachObject`), `bbox`, `border`, `enclose`, `cast`.
- 9 cases are witnessed. The audit is clean: witness, dropped cases, derive, store, open values and relabelings are all ok. `witness`, run both on the witness file and against witnesses.json, reports no differences.

## Unsettled
- In `$EachObject`, a basin is identified by its box. Two different components with the same bounding box would share one wall set, so cells of one would not be gaps of the other. This needs a witness with two such components, or a basin keyed by component id.
- `$SealedRegion` runs `Closed<Position>` once for each non-wall cell, which grows with the square of the grid area. On 10×10 grids a run takes about 3 s. A 30×30 grid has not been timed, and running one would settle it.
- A gap at a box corner: no model was formed, as analyze.md says. A variant task with a corner opening would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
