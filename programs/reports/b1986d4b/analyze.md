# b1986d4b

## Concept
- Fails Fit at train0 and train1. Each of those outputs draws four 2x2 squares, and each input holds five (train0: color 6 at (6,23), (7,10), (14,25), (15,3), (24,11); train1: color 3 at (8,19), (9,0), (16,15), (19,24), (26,9)). The concept gives train2 and test0 exactly (`check_concept.py`).
- `probe_features.py` prints, for every square, the noise in its 4-ring, 8-ring and second ring, its distance to the edge, and its gap to the nearest square. No feature sets apart one 2x2 square in train0 and one in train1 and also keeps every 2x2 square of train2 and test0. Train2 (20,15) touches noise at (21,14) and is drawn. Train1 has two 2x2 squares on the edge.
- The only readings found that fit every pair cap the smallest size's count by a number that counts nothing the task has, and they fail Relational form. So no case of the task as given meets every case condition. The outputs of train0 and train1 read as errors in the task data.
- The generator's rule, as train2 and test0 show it, is the concept file's `count-per-size`: every square counts.
- Witnesses with verdict `other`: none.

## Choice points
- `square-reading`
    - `concept`: the background is the commonest color, the noise is the other color in the most pieces, and the squares are the pieces of the remaining colors
    - `$NoiseMostCells`: replaces `square-reading` and `noise`. The noise is the non-background color with the most cells. Undefined where a piece of a remaining color is not a solid square. Fails Fit at train2, where color 4 has 96 cells and the noise 52; also at train0 and train1 by the count.
    - `$NoiseNotSquare`: replaces `square-reading` and `noise`. The noise is the non-background color that has a piece that is not a solid square. Undefined where no color, or more than one color, has such a piece. Fails Fit at train0 and train1.
    - `$SquaresByShape`: replaces `square-reading`, `noise` and `squares`. The squares are the solid square pieces, with each side at least `min_side` (2), of any non-background color. Undefined where one size has two colors. Fails Fit at train0 and train1.
- `count`
    - `concept`: every square counts
    - `$StoredCap`: replaces `count-per-size`. Each size's count is capped at a stored maximum per size (`cap`: size 2 to 4). Fails Fit at test0, which draws five 2x2 squares.
    - `$DropOneSmallest`: replaces `count-per-size`. The smallest size's count is one less than its squares. Fails Fit at train2.
    - `$CapSmallestTwiceLargest`: adds to `count-per-size`. The smallest size's count is capped at twice the largest size's count. Fits every pair. Fails Relational form: the factor counts nothing the task has. Witness `one-largest-square`, at the stored assignment, breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$CapSmallestLargestPlusTwo`: adds to `count-per-size`. The smallest size's count is capped at the largest size's count plus two. Fits every pair. Fails Relational form: the offset counts nothing the task has. Witness `one-largest-square`, at the stored assignment, breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$CountByArea`: replaces `count-per-size`. A size's count is the cell count of its color divided by the size's area. Undefined where that count is not whole. Fails Fit at train0 and train1.
- `size-color`
    - `concept`: each size takes the color its squares have in the input
    - `$StoredSizeColor`: replaces the color part of `nesting`. A stored mapping from size to color. Fails Fit: train0 colors size 2 with 6 and train1 with 3.
- `background`
    - `concept`: the commonest color of the input
    - `$StoredBackground`: replaces the background part of `square-reading`. A stored background color (1). Fails Fit at test0, whose background is 4.
- `stack-width`
    - `concept`: each stack is as wide as its largest square
    - `$FixedSlot`: replaces the width part of `layout`. Every stack is as wide as the largest size. Fails Fit at train0, whose lone 2x2 stacks are 2 wide.
- `trailing-gap`
    - `concept`: a gap follows every stack, the last one included
    - `$GapBetweenOnly`: replaces the gap part of `layout`. A gap stands only between stacks. Fails Fit at train0, whose col 15 is a trailing gap.
- `draw-order`
    - `concept`: a smaller square is drawn over a larger one
    - `$LargerOnTop`: replaces the order part of `nesting`. A larger square is drawn over a smaller one. Fails Fit at train0.
- `extent`
    - `concept`: the largest size plus `gap`
    - `$StoredExtent`: replaces `extent`. A stored extent across `axis` (5). Fails Fit at train0 and train1.
    - `$SeparateMargin`: replaces `extent`. The largest size plus a parameter of its own, `margin` (1). Fails Fit at train0 and train1.
- Every two points: the two branches' changes applied together.

## Open parameters
none

## Not formed
- A start of the line of stacks apart from `corner`: under every variant task, the end the line starts from follows the corner, so it is a redundant value and not a second parameter.
- An order of stacks other than fullest first, with squares still in `corner`: this is the same model as the start apart from `corner`.
- A rule that drops one 2x2 square by its position or its neighbors: `probe_features.py` finds no feature that separates the dropped square in train0 and in train1 and that keeps every 2x2 square of train2 and test0.

## Tickets filed
none
