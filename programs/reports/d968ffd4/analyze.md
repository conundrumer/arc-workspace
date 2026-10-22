# d968ffd4

## Concept
- The concept fits every train and test pair. It has an empty parameterization: the background, the two block colors and the axis on which the blocks face differ from pair to pair, and the program derives each of them from the input.
- No witness has the verdict `other`. The concept's rules have a relational form: the gap is the set of lines between the two blocks, and a gap line takes the color of the block it is strictly nearer to, counted in lines. A line at equal distance from the two blocks keeps the background.

## Choice points
- `axis`
    - `concept`: the axis on which the blocks face is the axis on which the two blocks sit at opposite ends, read from the input
    - `$AxisByShape`: replaces `facing-ends`, so that the blocks face along the frame's longer axis; no parameter; undefined on a square frame and where the two blocks do not sit at the two ends of the longer axis. Fits every pair. Witness `short-axis-facing`: breaks no scene claim, plausibility `variant`, verdict `concept`, and it breaks the invariant of the inputs that the blocks face along the longer axis. The model is undefined on it. Where `$AxisByShape` is defined, its output is the concept's, so the concept subsumes it and it fails Subsumption.
    - `$StoredAxis`: replaces `facing-ends` with a stored parameter `axis`; fails Fit at train2, where the blocks face along the vertical axis and train0 and train1 store the horizontal axis
- `split-line`
    - `concept`: the gap divides at its own midpoint, between the two blocks
    - `$FrameMidline`: replaces `split-gap` and `odd-middle`: a gap line takes the color of the block on its side of the frame's center line, and the center line of an odd-extent frame keeps the background; no parameter; defined wherever the concept is. Fits every pair. Witness `unequal-thickness`: breaks the scene claim `thickness`, plausibility `borderline`, verdict `concept`, and it breaks the invariant of the inputs that both blocks have one thickness and one margin, which puts the gap's midpoint on the frame's center line.
- `fill-across`
    - `concept`: each filled gap line is filled across the whole frame, the side margins included
    - `$BlockSpan`: replaces `split-gap`, so that the fill covers only the block's extent across the axis and the side margins keep the background; no parameter. Fails Fit at train0: train0 output (0,3)–(0,7) are `1` and (0,8)–(0,12) are `6`, in the margin row.
- `end-margins`
    - `concept`: the lines between each block and its near edge keep the background
    - `$FillEndMargin`: adds a fill of the lines between each block and its near edge in that block's color; no parameter. Fails Fit at train0: train0 output col 0 and col 15 stay `4`.
- `odd-middle`
    - `concept`: the middle line of an odd gap keeps the background
    - `$MiddleTaken`: replaces `odd-middle`, so that the middle line takes the color of the block on a stored side; parameter `middle_side`. Fails Fit at train1: train1 output col 8 stays `2`.
- `axis` & `split-line`, `axis` & `fill-across`, `axis` & `end-margins`, `axis` & `odd-middle`, `split-line` & `fill-across`, `split-line` & `end-margins`, `split-line` & `odd-middle`, `fill-across` & `end-margins`, `fill-across` & `odd-middle`, `end-margins` & `odd-middle`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Nearest block over the whole frame, each background cell taking the color of the nearer block: on every cell between the blocks it gives the concept's output, and on the end margins it is the branch `$FillEndMargin`.
- Each block grows by a fixed count of lines, or by its own thickness: the pairs grow each block by 5, 5, 6, 8 and 5 lines with thickness 2 throughout, so a fixed growth count fails Fit at train2, and growth by thickness fails Fit at train0.
- Each half taking the far block's color: no reader takes it, and it fails Fit at every pair.
- The way the background is found (the most common color, the corner color, the color off both blocks): every such reading gives one color on each input that the scene claims allow, and the program reads no stored value for it.
- The middle line of an odd gap keeping its input color in place of the background: the gap holds only background cells, so the two readings give one output on every input.

## Tickets filed
- none
