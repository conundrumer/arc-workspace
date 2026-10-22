# bcb3040b

## Departures
- Only the concept base takes `$TwoMarkers`. Every other base takes `$EveryAlignedPair`, and `impl_choice` excludes the non-concept bases that take `$TwoMarkers`: Subsumption. A case that takes `$TwoMarkers` is defined only where exactly two markers share a line. On those inputs, its `$EveryAlignedPair` twin joins the same pair and gives the same output at every assignment. So the Analyze branch models `$ExtendFullLine`, `$CrossAnyFg`, `$LineInMarkerColor` and `marker_color=RarestColor`, each of which takes the concept branch `$TwoMarkers`, are no case of the solver. Their `$EveryAlignedPair` twins stand for them. `witness --file work/task/bcb3040b/witnesses.json` reports that these names denote no case, which is expected.
- The `marker_color=RarestColor` cases on `$TwoMarkers` are dropped by `// @ignore: derive $TwoMarkers`: Subsumption, as above.
- `$LineInMarkerColor` cases share `line_paint` {0 → 2, 1 → 3} with the concept, and the Analyze report gives {1 → 3}. `$LineInMarkerColor` never reads a `bg` key of `line_paint`, so both values give one model. By "One parameter" in [Parameters across cases](docs/handbook/principles.md#parameters-across-cases), both cases admit the common value.
- A new choice point, `MarkerSource`, comes from the Not formed item "`marker_color` read as the color with exactly two cells, or as the color outside `field_colors`". Each reading states one model, fits every pair, and has a relational form: `$TwoCellColor` (the one color of exactly two cells, with `Unanimous`), and `$NonFieldColor` (cells of a color outside the parameter `field_colors` {0, 1}).
- `@derive RarestColor` on `bg_paint` (`$CrossAnyFg & $StoredPaint`) is held as a branch: `derive` lists it as a fit.
- New witnesses in the witness file are `sparse-ones`, `stray-cell`, `four-color-markers`, `stray-pair`, `line-paint-reassigned` and `unaligned-markers`, and `derive` wrote `bg_paint=RarestColor`. The group names of every witness are rewritten by `record --all`.

## Judgments
- The Not formed item "a segment between unaligned markers (rasterized line or a path with a turn)" is not formed. A rasterized line has no relational form, because its cells come from a rounded slope that counts nothing in the task. A path with a turn does not state one model, because the item does not say at which corner the path turns. Also, a turn path between diagonal markers fails Fit at train0, unless it is limited to unaligned markers.
- The Not formed items "subset of line axes" and the `ex_out` derivations fail Fit, as the Analyze report gives. They are not formed.
- `sparse-ones` (borderline, concept): this grid is a 0 field with two 1 cells off the diagonal, and markers of 2 at opposite corners. It breaks no scene claim, but random 0/1 noise does not readily give only two cells of 1. The generator would join the 2s. `$TwoCellColor` sees two colors of exactly two cells and is undefined.
- `stray-cell` (borderline, concept, relaxes `noise-field`): this grid has one 5 cell in column 0, in line with the marker at (0,0). The generator would treat the 5 as noise. `$NonFieldColor` joins the 5 to that marker.
- `four-color-markers` (variant, `$NonFieldColor & $LineInMarkerColor`): this grid has markers of 4 and no 2. This verdict follows the Analyze verdict on `marker-color-line`, which is the same input at `marker_color` = 4. It has no `@witness` line, because it only separates `$NonFieldColor & $LineInMarkerColor` from `$StoredColor & $EveryAlignedPair & $LineInMarkerColor`.
- `stray-pair` (borderline, concept, relaxes `noise-field`): this grid is `stray-cell` with the 5 off every marker line and two more 7 cells. It separates the `$StoredColor` and `$TwoCellColor` cases that take `$CrossAnyFg & bg_paint=RarestColor`.
- `line-paint-reassigned` (variant, concept, reassigns `line_paint` to {0 → 2, 1 → 6}): this witness shows that `$KeyedPaint & $LineInMarkerColor` is not subsumed by `$CrossAnyFg & bg_paint=RarestColor` under `marker_color=RarestColor`.
- `unaligned-markers` (foreign, concept): this grid has two 2s on no common line, and the generator never gives such a grid. It separates the `$TwoMarkers` and `$EveryAlignedPair` readings of `$TwoCellColor`, which the dropped-cases audit asked for.
- `@derive RarestColor` on `bg_paint` is variant `derived`. Its witness is the `marker-color-line` input at `marker_color` = 4, where it paints the background crossings 4, the same as `$LineInMarkerColor`. The Analyze report judges that output as the generator's.
- The `determination-plan` gives `line_paint` as covered by `ChangedPairs`, which reads the same fact as the concept: in → out color at changed cells. So `line_paint` has no determination relation. `marker_color` is determined as the color of exactly two cells in every train input, through `Parse`, which the program's `$TwoCellColor` shares. `bg`, `bg_paint`, `cross_paint` and `field_colors` are determined from the changed segment cells.
- Sweep: `line_paint` and `field_colors` admit added rows for colors absent from every input. No reader of the concept could take such a value, so none are stored.
- Deletions: the guards `unsourced`, `unpaired`, `extra`, `!marker_color` in `$CrossAnyFg`, `!params.bg` in `$KeyedPaint & $LineInMarkerColor`, and both `lines.ray` atoms of `$Segment` change no pair. They state undefinedness or scene limits that the pairs do not exercise (`extend-past-markers` exercises the `$Segment` atoms), so they stay. `marker(S, P)` in `aligned` was implied by the `lines.ray` source, and it is removed.
- Keywords: `markers span mapping noise`. `noise` applies because the line marks the noise cells it crosses with a second color.
- No lint hint appeared, and no performance issue was seen. Each run took under 10 s.

## Open
- The `@derive RarestColor` line on `bg_paint` cannot record that its witness stands at `marker_color` = 4: settled by a handbook form for that line, ticket 10-588.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-588_task_bcb3040b_create.md
- 10-589_task_bcb3040b_create.md
