# f0afb749

## Departures
- The witness `background=DominantColor` of `witnesses.json` is removed from the witness file: `derive` recorded the witness `bg=DominantColor` for the same `@derive DominantColor` branch (train0 with 0 and 2 swapped), and Witness removes a witness of a `@derive` branch that duplicates that one.
- The name `background=DominantColor` is written `bg=DominantColor` in the witness file: the parameter is `bg`, after the concept file's `background`, and the name takes the parameter's name.
- `$RayStopsAtBlock` is not in the solver, and its name is removed from every group: `analyze.md` gives it no witness and finds it fails Equivalence with the concept case.
- The `@scene` lines `background-field` and `square-grid` are left out of the header: no `@claim` or `@relaxed` line denotes them, no rule text depends on them, and no branch replaces them.
- Concept branch constructor names of my own: `PassBehind` (point `line-at-other-block`) and `StoredScale` (point `scale`).

## Judgments
- No Determine comp: `determination-plan` reports every value covered by a proposer (bg DominantColor, line_color AnyOutNewColor, scale ScaleRatio) or by the 2-value enumeration (line_axis). Each proposer reads the fact the concept reads the value from: the field color, the color new in the output, the output-to-input size ratio. So no determination relation is needed.
- The line is found as the output cells in line, along `line_axis`, with a block corner on that axis (`diag_axis_of`, `corner_dist(P_intile, D, 0)`). Both corners of the axis lie on one line, so the line comes out the same from either.
- `$ScaleByColorCount` shares the `Frame2D<ScaleSource>` block frame with the concept case. The block size is a `block_size` relation keyed by the `ScaleSource` field, stored for `$StoredScale` and counted by `Tally` for `$ScaleByColorCount`.
- Keywords `scale cast`: the output scales the input, and a line extends from each block out to the edges.
- The pairs run passes train0–2 and test0 at 4 witnessed cases of 8. `witness` reports no unseparated pair and no unwitnessed case. The audit is clean.
- No Not formed item of `analyze.md` states a model that fits, so no branch was formed from them. `store` printed no line to add.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
