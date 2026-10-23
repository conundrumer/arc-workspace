# c97c0139

## Departures
- Witness `background=DominantColor`, group `$FillByLineColor`: `witnesses.json` gives it as undefined, and the solver gives the input unchanged. The rule `analyze.md` gives `$FillByLineColor` is undefined only on an input with a segment whose color isn't a key. At the stored background 0, every cell of that witness is a line cell, and the grid is one bent component. So the input has no segment, nothing fills, and the output is defined. `witnesses.json` erred here, and the witness file keeps the solver's output.

## Judgments
- The model that is undefined when a diamond reaches past the grid edge (Not formed in `analyze.md`) is not formed as a branch. Wherever that model is defined, its output is the concept's output. So it is subsumed by the concept case and fails Subsumption.
- The other Not formed items get no branch. The stored axis, the one-sided fill and the other fill shapes each fail Fit at a train pair. The taxicab ball around the midpoint has no relational form. A derivation of `line_color` under `Ink` has nothing to read, because that branch reads no `line_color`.
- `$CellPairs` gets no constructor: it fails Fit at test0, and `analyze.md` gives it no witness.
- Constructor names of my own: `Ink`, `OneFill`, `StraightComponents` and `KeepLines` for the concept branches. `record --all` rewrote the witness file's names to the forms the solver gives (`$OneFill`, `$LineColorCells & line_color=stored`, `$KeepLines & background=stored`, and so on).
- `$PaintOverLines` changes `diamond-fill` (any diamond cell takes the fill), and `@claim diamond-fill` stands under `KeepLines`. `analyze.md` words this branch as a change to `keep`. If only `keep` changed, the header's `diamond-fill` would still limit the fill to `background` cells, so the change is written on `diamond-fill`.
- The `@witness` lines follow `analyze.md`'s placement: `two-colors` under `$LineColorCells`, and `mapped-second-color` (with `@reassigned fill_by_line`) under `$FillByLineColor`. Under `$LineColorCells`, `mapped-second-color` would stand at the stored assignment while its `assign` changes `fill_by_line`, which the audit rejects.
- `background` stands under the marker `$Ink, $KeepLines`. Under `$LineColorCells & $PaintOverLines`, no clause reads it, as `analyze.md` states.
- `$FillByLineColor` is undefined on an input with an unkeyed segment color because that segment's diamond cells get no `out` fact. No separate guard relation is needed.
- `K > 0` in `diamond` is a comparison of a distance against a bound. It excludes the foot itself, which `$PaintOverLines` would otherwise paint.
- The diamond keeps the concept's wording: `Ray` gives the distance K across the line from the foot, and `jump` by K both ways along the line gives the two cells that must be in the foot's segment. Straightness of a component is a defect test: two of its cells are at different distances across the axis (`same_dist` under negation). `same_line` can't stand under negation because it introduces variables.
- `$StraightRuns` uses `Slide.run` for "in F's run along the line". That needs no run ids.
- Determination: `background` is the commonest input color of every train input (`Mode`, defect negation over train examples). `fill_color`, `fill_by_line` and `line_color` all read `beside`, which pairs the color of a line cell with the output color of a field cell beside it that the output paints. The sweep gave a unique value for each parameter, and the plan's actions are done.
- Deletion report: each deletion that changes nothing removes structure that the pairs never test. That structure is the line color under one line color, the axis and foot columns, `bent` for straight inputs, the `background` test of the target, and the determination's neighbor test. All of it stays. `axis_of(D, A)` in `diamond` is implied by `seg_line`. It stays because it states "along the line" and keeps `jump` off the other directions.
- `derive` gives `DominantColor` for `background` and `RarestColor` for `line_color`, and both stand as `@derive` lines with `analyze.md`'s plausibility and verdict. `store` gives no new line: `line[col]` is already stored as `line_color`.
- Keywords `objects span`: the segments are pieces of the grid, and each segment's extent bounds its diamond.
- No hints appeared. The first `run` and the first audit's relabelings check each took about a minute, and later runs took a few seconds. That points to a cold compile, so I flag no performance issue.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
