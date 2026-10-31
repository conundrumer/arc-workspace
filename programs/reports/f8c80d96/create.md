# f8c80d96

## Departures
- The branch `background=DominantColor` is the `@derive DominantColor` line on `bg`, named `bg=DominantColor` in the witness file. The analyze witness of that name is kept, under the new name, as the witness the line records (`variant concept`). The witness that `derive` wrote for the branch (train0 with 0 and 1 swapped) is removed: it duplicates the recorded one. Rests on Develop step 5 and the Witness rule on `@derive` duplicates.
- `$PerAxisStep` has no case with `$Outward`: no input shows `$Outward & $PerAxisStep` defined and different from `$Outward & $PerSideStep`, so it fails Subsumption. This agrees with `analyze.md`. A defined per-axis step makes every side's gaps agree, so the per-side steps are the same.
- `$GrowInward & $Uniform` is not a case: it fails Subsumption by `$GrowInward & $PerAxisStep`. Where `$Uniform` is defined, every gap is one value, and every axis that has a side the drawing grows from has a gap on that axis. The one way for an axis to have no gap is an outer outline whose only sides in the grid lie on one axis, and such an outline is one row or two separate components, which the parse does not read as one enclosing outline. So `$PerAxisStep` gives the same steps. The `$GrowInward` branch keeps its cases `$GrowInward & $PerAxisStep` and `$GrowInward & $PerSideStep`. The verdicts `$GrowInward` and `$PerAxisStep` on `@witness` lines denote models that are not cases of the solver.
- `$GrowInward & $PerAxisStep` stays as a case, which `analyze.md` does not give, because the new witness `inner-side-unobserved` separates it. On that input, the innermost outline's top side lies in the grid and the next outline's top does not, so no top gap is seen. `$PerAxisStep` takes the top step from the bottom gap and draws an inward outline (row 3, cols 7–9). `$PerSideStep` has no top step and is undefined. `$Outward` draws no inward outline.
- The solver makes a case undefined only where a side it grows from has no step: the outermost outline's sides in the grid, and for `$GrowInward` also the innermost one's. A side that only some middle outline has in the grid needs no step.

## Judgments
- Concept encoding: each outline is a 4-component of the line color, and its visible box is its Bbox. A side of that box is the outline's own side when every cell on it is an outline cell. Otherwise the outline runs past the grid edge there, and that side takes no part in the drawing. The gap on a side comes from two consecutive outlines, by `relative` and `dist`, where the outer one has that side in the grid. A cell lies on the outline N steps out when, on some side of the outermost outline, it is N whole steps outside that side (`stride(M, S, 0, N, 0)`) and on no side is it further out than that. `$GrowInward` reads the same per-side form inward from the innermost outline. This rests on the per-cell ring distance from the anchor box, measured on its in-grid sides alone.
- A one-row or one-column outline, or one whose visible part is one cell, gets a visible box with every side in the grid. This is a parse limit on degenerate outlines that no input of the task has.
- Witness `inner-side-unobserved`: plausibility `variant`, verdict `$PerAxisStep`, `@relaxed uniform-step`. Unequal axis steps are the case `analyze.md` judges `variant` for `unequal-axis-steps`. The generator grows outward, so the output it pairs is the outward per-axis output.
- Witness `recolored-background` (a further witness of `bg=DominantColor`): `missing-inner-outline` with 0 recolored 1. A color permutation of the task is a variant task, so plausibility `variant`. The generator would pair the output of `bg=DominantColor`. With the stored background 0, the cases have two other colors and are undefined. It shows `$GrowInward & bg=DominantColor` defined and different from `$GrowInward`.
- Hint `single-consumer` on `outermost`: it has two consumers after `unstepped` came to read it, and the hint no longer fires.
- `deletions` reports 21 deletions that change nothing on the pairs. They are the inward drawing, the definedness checks and the nesting order, which the pairs do not exercise and the witnesses do. None is removed. The two comment lines added after the `deletions` run change no clause.
- Determination: `bg` is the input color whose cells the outputs change. `fill_color` is an output color its input lacks. The plan reports both determined.
- Keywords: `objects` for the outline components, and `rings` for the cell's ring around the anchor outline.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
