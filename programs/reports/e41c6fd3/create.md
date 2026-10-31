# e41c6fd3

## Departures
- The witness file has two witnesses that `witnesses.json` does not have, `field-of-five` and `corner-touching-copies`: `witness` reported that no run showed `background=DominantColor`, or the `$ObjectComponents & $Adjacency4` side of the adjacency pair, defined and differing from the other case of its pair. Each witness shows that, so both cases stay under Subsumption.
- `$KeepOriginals` has no constructor: it fails Fit at train0 (analyze.md).
- The anchor derivations (SharedColor, RarestColor, DominantColor, VanishedColor) are recorded by one `@ignore: derive` line on `anchor`, because each one fails Fit at train0. `derive` lists VanishedColor where analyze.md names UnchangedColor.

## Judgments
- `field-of-five`, a field of 5 with no 0 cell: plausibility `variant`, because a color-permuted variant task gives this input; it breaks `copies-of-one-shape` at the stored assignment. Verdict `background=DominantColor`, because the generator would align the 2 copy with the anchor on the 5 field.
- `corner-touching-copies`, two one-cell copies of color 2 that touch at a corner: plausibility `borderline`, because it needs two copies of one color that touch diagonally; it breaks `copies-of-one-shape`. Verdict `$ObjectComponents`: the generator drew two copies, and each one aligns with the anchor.
- The `@witness` lines and the verdicts of the branches are as analyze.md gives them. `witness --file witnesses.json` matched every branch's output.
- Undefinedness is encoded as an empty `out` for the case. The `failed` relation covers a copy with no translation at one edge, and two edges that give different grids. `anchor_split` covers a reading that finds more than one anchor copy. A collision gives two colors at one cell. The pairs do not exercise any of these checks (`deletions`), but the witnesses need them, so they stay.
- A copy is keyed by `CopyKey = [r: CopyReading, k: number]`, the record type argument of `Bbox`. `k` holds a Color under ColorClass and an Ident under ObjectComponents.
- I dropped the `copy` color column after the `head-repeat` hint. The color is read through `in`.
- The three `determine prediction` hints are kept with `@ignore`. Each determination reads the evidence the concept names: the anchor is the color a train pair leaves in place, the background is the color on one side of every changed cell, and the slide axis is the line that every output cell shares with an input cell of its color. Each of these is a fact of an input and its output together.
- The `deletions` findings were judged as follows. The `failed` and `anchor_split` checks, `landed.d`, the AxisFromLayout atoms and the `not_kept` rules are needed off the pairs, so they stay. I made these changes: `slide_axis` became `axis_of` in the AlignCenter clause, `copy_reading_choice` left the AxisFromLayout clause (span_overlap binds R), and `!params.background` left the Determine `anchor` and `off_line` clauses (the changed background cells already exclude it).
- `deletions` ran once, before those edits. Those edits are the only solver edits after it, and the last pairs run and `witness` pass after them.
- 24 cases are formed, and 6 of them are witnessed.
- `store` printed no line to add, so no `@store` branch was added.
- Run status: every pair passes, and lint, determination, witness and audit are ok.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
