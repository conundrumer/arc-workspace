# f18ec8cc

## Concept
- Fits every train and test pair at `from` = DIR_L, `shift` = 1 (probe `work/task/f18ec8cc/probe.py`). No witness has verdict `other`. The rule is exact as the generator applies it (the first stripe goes to the far end, carried whole with its dots), so no approximation.
- The concept's parse finds stripes as runs of lines that share one unique commonest color. It is undefined where a line has no unique commonest color. So it reads every stripe, and `$RotateColumns` subsumes it: both witnesses show this. That is allowed for the concept case.

## Choice points
- `stripe-parse`: how the stripes are found
    - `concept`: a stripe is a maximal run of lines that share one unique commonest color. The model is undefined where some line has no unique commonest color.
    - `$SolidLines`: replaces `stripes` and `dots`. A cut falls between two adjacent solid lines of different colors, and the stripes are the runs between cuts. It reads `from` and `shift`. It is undefined where one run holds solid lines of two colors. It fits every pair. Witness `tie-in-first-stripe`: it breaks the scene claim `dots` (the first stripe's center line holds 5, 1 and 7 once each), plausibility `borderline`, verdict `$SolidLines`. The invariant it breaks: in every input, each line's commonest color is unique and is its stripe's color, and the inputs are 7 to 9 lines tall with more lines than stripes. It fails Subsumption against `$SolidLines & $RotateColumns`: wherever it is defined, its first run is that model's first stripe, and that model is also defined where a later run is mixed.
    - `$TopRow`: replaces `stripes`. The stripes are read off the top row's color runs. It reads `from` and `shift` and is never undefined. It fails Fit at train1: row 0 holds dots, so the first run is 1 cell wide.
- `rearrangement`: how the stripe sequence is reordered
    - `concept`: every stripe moves `shift` places toward `from`, and the stripes that pass that edge wrap to the opposite end
    - `$RotateColumns`: replaces `cycle-stripes`. Only the first `shift` stripes at the `from` edge are found, and the lines are rotated toward `from` by their combined width. It reads nothing past them, and it is undefined where the first stripe's extent is not found, for example where one of its lines has no unique commonest color. It fits every pair. Witness `tie-in-later-stripe`: it breaks the scene claim `dots` (the center lines of the 7 and 1 stripes have no unique commonest color), plausibility `borderline`, verdict `$RotateColumns`. It breaks the same invariant of the inputs as `$SolidLines`. Nothing subsumes it: where every line of the first stripe holds a dot, `$SolidLines & $RotateColumns` puts its first cut later.
    - `$Reverse`: replaces `cycle-stripes`. The stripe order is reversed, and neither `from` nor `shift` is read. It fails Fit at train0 (it gives 9,7,5 where the output has 7,9,5).
    - `$SwapEnds`: replaces `cycle-stripes`. The two end stripes trade places. It fails Fit at train0 (9,7,5).
    - `$MoveWidest`: replaces `cycle-stripes`. The widest stripe goes to the end opposite `from` and the rest close up. It fails Fit at train0 (it moves the 6-wide 7 stripe).
- `dot-carry`: what happens to the dots
    - `concept`: each dot moves with its stripe
    - `$DotsStay`: replaces `cycle-stripes`. Only the stripes' background colors cycle, and the dots keep their cells. It fails Fit at train0: (6,11) is 7 in the output and 5 in this model.
- `stripe-parse` & `rearrangement`: the two branches' changes applied together. `$SolidLines & $RotateColumns` rotates the lines by the width up to the first cut between adjacent solid lines of different colors. It fits every pair, and on both witnesses it gives the `$SolidLines` grid.
- `stripe-parse` & `dot-carry`, `rearrangement` & `dot-carry`: none. `$DotsStay` fails Fit, so no case takes a non-concept branch at both.

## Open parameters
- none

## Not formed
- `from` derived from the input: no input feature marks a direction, and every input reads the same from the left. The value is stored.
- `shift` derived, or open: the pairs have 3 and 4 stripes, which fix `shift` ≡ 1 mod 12. No count in the inputs equals 1 in every pair (stripe count minus 2 gives 2 at train1), and 1 is the only value a reader takes.
- Moving n−1 stripes from the right edge: the same model as the concept, which is equivalent.
- Dot-based selection or order: in every input, each stripe holds exactly one dot of each other stripe's color, so the dots single out no stripe. Their rows give no order that holds across the pairs (train1 dot rows read 9,8,3,1, and the output order is 9,1,3,8), and in train2 a color's dots do not share a row.
- Stripes as 4-connected regions of their background color: in every input every stripe is whole lines with its edge lines solid, so the region parse and the line parse give the same stripes on every input the generator produces. Where an edge dot would join a region to its neighbor, the region parse gives no run of lines to move, and no claim of the pairs moves a region that is not whole lines.

## Tickets filed
- none
