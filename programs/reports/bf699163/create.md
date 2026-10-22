# bf699163

## Departures
- The concept case reads a drawn line as a frame cell with another frame cell next to it along the line's axis, not as "a row or column that holds at least two frame cells": in train1, rows 14 and 16 each hold two frame cells ((14,1), (14,7) and (16,1), (16,7)) that are not next to each other. Under the Analyze wording, row 14 would be a line with frame cells on both sides, so the region would be empty and train1 would be undefined. The Analyze probe also counted a line only at 3 or more cells.
- The inside of a drawn line is the side toward which some frame cell lies past it, not "the side toward which the perpendicular lines run": every frame cell lies on a side of the rectangle (`dashed-frame`), so the two readings agree on every input that holds the scene.
- In the witness file, witness `shape=stored` is renamed `ring-4x4`, and its branch name `shape=stored` is renamed `$StoredShape`: Write gives that branch a constructor, and that constructor name has no `=`. On a copy of the Analyze file with that name rewritten, `witness --file` shows no difference.

## Judgments
- Lint finding `long-clause` (the `$FrameBbox` clause): fixed by wrapping the body.
- Hint `common-subexpr` on the four clauses of the hollow-square test: merged into one clause with a disjunction.
- Hint `single-consumer` on `not_hollow_square`: the relation was inlined into `frame_by_shape.item`. Later that test moved into `Parse` as `not_ring` because the determination also uses it.
- Not formed, a stored output grid or a stored output color: each fails Fit, because the output color differs in every pair (1, 4, 2) and no input key selects a stored entry. No case was added.
- `derive`: `background` DominantColor fits, and it is a `@derive` branch, `variant derived`, `@relaxed background`.
- `store`: `frame_by_shape.item`, `frame_by_shape.value` and `parse.not_ring` are 7 on every input, under `$FrameColorByShape`. If one of them is stored, the model is the `$StoredFrameColor` model with one more non-concept branch, so it fails Equivalence. Each has an `@ignore: store` line. `ring_cell` gives no case.
- Sweep: under `$Crop & $StoredFrameColor`, `background` also fits 2, 3, 6, 7 and 8. The concept fixes `background` as the field, so it is not an open parameter, and the solver stores only 5.
- Determination: `frame_color` is the one color that forms no hollow square in every train input. The solver uses the `not_ring` test in `Parse`, and the program uses the same test for `$FrameColorByShape`. `background` has no determination relation, because DominantColor gives it from the same fact as the concept's `background` claim: the field is the most common color. The plan leaves `shape` to the values at which the model fits every train pair.
- `$StoredShape` takes its output frame from the stored mask's extent (`Frame2D`), and it paints the mask's other cells `background`.
- `$MostFramedSides` counts a frame cell toward d when that cell shares a row or a column with a ring cell and lies past the ring's box toward d (`nearer(D, G, B)`).
- Deletions: 9 deletions change no output. These are the disjuncts of the hollow-square test, `perp`, `interior` in `has_hole`, `framed.domain`, `nearer` in `framed.item`, and `ex_out` in the determination. Each one states a part of its claim that the pairs do not exercise one by one, so each stays.
- Keywords: `color-class border select crop` for the concept, `rank` for `$MostFramedSides`, and `lookup` for `$StoredShape`.
- Witnesses: the solver uses the five Analyze witnesses unchanged and builds no new ones. `witness` reports no pair of cases that no witness separates. 6 of the 24 cases are witnessed.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-634_task_bf699163_create.md
