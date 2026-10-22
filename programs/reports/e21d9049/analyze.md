# e21d9049

## Concept
- Fits every pair (train0, train1, test0). Each strip repeats its own color sequence with a period of its own length, anchored on the strip's cells, to both grid edges. The rule has a relational form: a line cell takes the color of the strip cell at a distance that is a multiple of the strip's length.
- No witness has the verdict `other`.
- Two scene claims hold in every input and the concept does not read them: `distinct-colors-per-strip` and `equal-length`. Each pair also uses one color set for both strips. Several branches rely on these invariants, and their witnesses break them.

## Choice points
- `repeat-unit`: what repeats along each strip's line
    - `concept`: the whole strip, with a period of its own length
    - `$ShortestPeriod`: replaces `repeat-unit` in `repeat-along-line`. The period is the strip's shortest period, the least p at which the strip's colors repeat. It is defined wherever the concept is. It fits every pair. Witness `alternating-strip` (a 1 2 1 2 1 strip) breaks `distinct-colors-per-strip`. It stands at the stored assignment, plausibility `borderline`, verdict `$ShortestPeriod`. The invariant it breaks is that no color occurs twice in one strip.
    - `$SharedPeriod`: replaces `repeat-along-line` and reads `equal-length`. One period, the length that both strips share, serves both lines. It is undefined where the two strips differ in length. It fits every pair. Witness `unequal-strips` (lengths 3 and 4) breaks `equal-length`. It stands at the stored assignment, plausibility `variant`, verdict `concept`. The invariant it breaks is that the two strips have the same length. Where it is defined, it gives the concept's output, so it fails Subsumption.
    - `$ColorCount`: replaces `repeat-unit` in `repeat-along-line`. The period is the number of non-background colors in the input. It is undefined where that period exceeds a strip's length, or where it conflicts with the strip's own colors. It fits every pair. Witness `count-period` (a 1 1 2 1 1 row, and a 3 4 1 2 column that gives four colors) breaks `distinct-colors-per-strip` and `equal-length`. On that witness the branch is defined and differs from both the concept and `$ShortestPeriod`. It stands at the stored assignment, plausibility `foreign`, verdict `concept`. The invariants it breaks are distinct colors in each strip, equal lengths, and one color set for both strips.
    - `$ColorCycle`: replaces `repeat-along-line`. A walk outward from each end of the strip gives each cell the cyclic successor (or, walking back, the predecessor) of its neighbor's color, read off the strip with its last cell followed by its first. It is undefined where a color has two successors. It fits every pair. It has no witness on which it is defined: a strip whose cyclic successor is unique is a repeat of a cycle whose length divides the strip's length, so the walk gives the concept's output there. That means it fails Subsumption. Witness `repeated-color-strip` (a 1 2 2 3 strip, where it is undefined) breaks `distinct-colors-per-strip`. It stands at the stored assignment, plausibility `borderline`, verdict `concept`. The invariant it breaks is that no color occurs twice in one strip.
    - `$Reflect`: replaces `repeat-unit` in `repeat-along-line`. The strip and its mirror image alternate along the line, with a period of twice the strip's length. It fails Fit at train0: the row continues 8 3 2 2 3 8, and the output gives 8 3 2 8 3 2.
- `extent`: how far each line extends
    - `concept`: to both grid edges, painting over whatever lies on the line
    - `$StopAtObstacle`: replaces `repeat-along-line`. From each end of the strip, the repetition extends outward until the first non-background cell. That cell and every cell past it keep their input colors. It fits every pair. Witness `stray-cell` (a 5 on the horizontal strip's row) breaks `crossing-strips`. It stands at the stored assignment, plausibility `foreign`, verdict `concept`. The invariant it breaks is that the only non-background cells are those of the two strips.
- `background`: the field color
    - `concept`: stored, 0
    - `background=DominantColor`: the background is the commonest color of the input. It fits every pair. Witness `background=DominantColor` (train0 input, with the field recolored to 5) breaks `crossing-strips` at the stored background 0. It stands at the stored assignment, plausibility `variant`, verdict `background=DominantColor`. The invariant it breaks is that the field is 0.
- `repeat-unit` & `extent`, `repeat-unit` & `background`, `extent` & `background`: the two branches' changes applied together

## Open parameters
none

## Not formed
- A repetition whose phase is taken from the grid's top or left edge, in place of from the strip: no reading of the pairs takes it. Every output keeps each strip cell's color, and train0's column (rows 2–4) restarted from row 0 would give row 0 the color 8 where the output gives 3.
- A repetition anchored at the crossing cell: it is equivalent to the concept, because the crossing cell lies in each strip and the period is the strip's length.
- `background` derived by `RarestColor` or `SharedColor`: on one input, `RarestColor` gives a strip color, which fails Fit at train0. `SharedColor` gives every color of the input, so no single background is derived, and each case that takes it is undefined on every pair.

## Tickets filed
none
