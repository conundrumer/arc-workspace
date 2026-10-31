# ff2825db

## Departures
- `$Majority` has no constructor, and the witness `three-colors-plurality` is gone from the witness file: `witness` reported that no run shows `$Majority` defined and differing from the concept. Wherever a color holds more than half of the scattered cells, it is also the unique plurality, so no input separates them. The case fails Subsumption, as `analyze.md` states. With `$Majority` gone, `three-colors-plurality` separates nothing. The `tie` point then stands directly in `Choice` as the field `tie`, because it no longer sits under a `Plurality` constructor.
- `witness --file programs/reports/ff2825db/witnesses.json` reports only that the name `$Majority` denotes no case. Every other branch gives the output that `witnesses.json` gives it.

## Judgments
- Frame and box: the frame is the rim (`Rim<StripSide>`) of the cells past the strip, and the box is the rest of those cells. This is equivariant, and it gives the frame with no stored geometry.
- `$TieBoth`: the solver gives one grid per tied color through the `TiebreakResolution` column `[winner: Color]`. The solver is undefined where three colors tie (`three_way`), as `analyze.md` states. Each fact in `out` holds the winner it is drawn for, strip cells included, so every resolution is a total grid.
- `$CountWithStrip` counts every strip cell that is not background, as `analyze.md` states ("the count reads the strip's cells as well as the box's").
- `$Majority & $CountWithStrip` is not in `impl_choice`, because `analyze.md` gives a Fit failure at train0. That point is moot now that `$Majority` is gone.
- `store` offered `@store` lines on `most_colors.high`, `strip_edge.item` and `strip_edge.value` under `$StripSideDerived`. Each one stores the top edge, which gives the model of `$StripSideStored`. Each such case takes more non-concept branches than the concept case and fails Equivalence, so each has `@ignore …: store`.
- `derive`: no built-in derivation fits. `background=DominantColor` fails Fit, as `analyze.md` states.
- Determine: the sweep gives `background` = 0 and `strip_side` = DIR_T as unique. The plan reports both as covered by the pairs-exact enumeration, and it names no proposer whose fact the concept does not use, so the solver has no `Determine` comp.
- Deletions: the `impl_choice` atoms in the `winner` clauses and `edge_colors.domain` were removed. Every edge line holds cells, and `winner` fixes the full `Choice`. These kept atoms change no pair, and they are needed: `!params.background(Col)` on strip cells (background cells are not votes), `three_way` (the `$TieBoth` undefined condition), and `impl_choice` in `out` (the case enumerator). `deletions` ran before these removals and was not run again, because the step allows one run.
- Keywords: `color-class` (the winner's cells form one unit for its bounding box), `rank` (an extremum over counts picks the winner), `bbox`, and `border` (the drawn outline).

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
