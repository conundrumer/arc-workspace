# dd6b8c4b

## Concept
- The concept fits every train pair and both test pairs (`probe.py`, interpretation `concept`). The concept case meets every case condition.
- Reach and distance are a 4-adjacent walk over the cells that are not `wall`, with marks passable, and the walk starts at the box cells. "Nearest first" is a rank over that walk distance. Both have a relational form (a fewest-hop distance and an order), so the concept has no approximation.
- When the last mark taken and the first mark left are at one distance from the box, the concept does not say which mark is taken, and the concept model is undefined on that input. In every input of the evidence, the marks at the cut are at different distances: train1 cuts between 19 and 20, and test1 cuts between 18 and 19.
- No witness with verdict `other` was found.

## Choice points
- `reach`
    - `concept`: a mark reaches the box by a 4-adjacent walk through cells that are not `wall`, and marks are passable
    - `$Reach8`: replaces `reach` with 8-adjacent walks, so a walk can step diagonally between two wall cells, and the distance counts 8-adjacent steps. Fails Fit at train1: two marks tie at the cut, and the output differs from the pair's output.
    - `$MarksBlock`: replaces `reach` with walks through `background` cells only, and a mark is reached when it borders such a walk. Fails Fit at train0: the mark at (8,8) borders only walls and the mark at (8,7), so it is not reached, and one mark is taken in place of two.
    - `$IgnoreWalls`: replaces `reach`, so every mark is reached and walls do not block a walk. Fails Fit at train0: nine of the twelve marks are taken in place of two.
- `take-order`
    - `concept`: the reached marks are ranked by a distance
        - `metric`
            - `concept`: walk distance from the nearest box cell
            - `$WalkFromCenter`: replaces `take` with a walk that starts at the `center_color` cell and passes through the box cells. Fits every pair. Witness `center-breaks-tie` stands at the stored assignment. It breaks no scene claim. Plausibility is `borderline`, and the verdict is `any`. The witness breaks this invariant of the inputs: in each input where the reached marks outnumber the box cells, the last mark taken is strictly nearer than the first mark left. Where both models are defined, the two models agree: the two walk distances of a mark differ by 1 or 2, so the two orders differ only where one of them has a tie. The case that takes this branch alone is subsumed by the case `$WalkFromCenter & $TieReading`, so it fails Subsumption, and the case `$WalkFromCenter & $TieReading` is the one that is included.
            - `$BoxManhattan`: replaces `take` with straight taxicab distance to the nearest box cell, among the reached marks. Fails Fit at train1 (tie at the cut, and a wrong taken set).
            - `$CenterEuclid`: replaces `take` with squared straight distance to the `center_color` cell. Fails Fit at train1: (1,7) at 20 is kept, and (3,0) at 29 is taken.
            - `$CenterChebyshev`: replaces `take` with Chebyshev distance to the `center_color` cell. Fails Fit at train1.
        - `tie`
            - `concept`: undefined when the last mark taken and the first mark left tie
            - `$TieReading`: adds a rule that, among marks at one distance, the mark earlier in reading order is taken first. Fits every pair, because no pair has a tie at the cut. Witness `tie-at-cut` stands at the stored assignment. It breaks no scene claim. Plausibility is `borderline`, and the verdict is `any`. The witness breaks the invariant that `$WalkFromCenter` states. On that witness, the concept model and the `$WalkFromCenter` model are undefined.
    - `$ReadingTake`: replaces `take`, so the reached marks are taken in reading order. Fails Fit at train1: (0,6), (0,7), (0,8), (1,6), (1,7), (1,10) and (2,10) come before the marks that the pair takes.
- `capacity`
    - `concept`: the box holds one mark per box cell, the center included
    - `$CenterKept`: replaces `fill`, so the `center_color` cell keeps its color and the box holds 8. Fails Fit at train1: the center takes `mark`, and nine marks are taken.
- `fill-order`
    - `concept`: the box cells fill in `fill_order`
    - `$FillRing`: replaces `fill`, so the ring fills clockwise from the top-left corner and the center fills last. Fails Fit at train2: the fourth mark goes to (5,6), and the pair puts it at (5,4).
    - `$FillFromEntry`: replaces `fill`, so the box cells nearest the opening that the marks come through fill first. Fails Fit at train0: the opening is below the box, and the pair fills (4,4) and (4,5).
- `vacate`
    - `concept`: each taken mark becomes `background`
    - `$VacateAllReached`: replaces `vacate`, so each reached mark becomes `background`. Fails Fit at train1: six reached marks keep `mark`.
- `reach` & `take-order`, `reach` & `tie`, `reach` & `capacity`, `reach` & `fill-order`, `reach` & `vacate`, `take-order` & `capacity`, `take-order` & `fill-order`, `take-order` & `vacate`, `metric` & `tie`, `metric` & `capacity`, `metric` & `fill-order`, `metric` & `vacate`, `tie` & `capacity`, `tie` & `fill-order`, `tie` & `vacate`, `capacity` & `fill-order`, `capacity` & `vacate`, `fill-order` & `vacate`: the two branches' changes applied together
- `reach` & `metric`: the two branches' changes applied together
    - `$IgnoreWalls` & `$BoxManhattan`: the model of `$IgnoreWalls`. When no wall blocks a walk, the walk distance from the box is the taxicab distance to the nearest box cell.

## Open parameters
- none

## Not formed
- Marks taken as whole groups of touching marks: in train1, (1,6) is taken, and (0,6), (0,7) and (1,7), which touch it, are kept.
- The marks move into the box as one rigid shape: in train2, the marks lie far apart, and the box fills in reading order.
- A count of marks that differs from the count of box cells, or from the count of reached marks when there are fewer: every pair takes exactly the smaller of the two counts.
- More than one box: every input has one box, and no source gives a rule for several.
- `fill_order` at another D4 value: this is a reassignment of a parameter and not a branch. train0 fixes it to the top-left corner along rows, because the first two cells are (4,4) and (4,5).

## Tickets filed
- none
