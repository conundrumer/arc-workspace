# bf32578f

## Concept
- The concept case fits every pair (`work/task/bf32578f/check_concept.py`, `probe.py`). It stores `bg` = 0 and `mirror-dir` = R, and it reads the inside as the cells that no 4-walk through cells off the outline reaches from the frame edge (lib `Closed`).
- It is undefined where the non-`bg` cells hold other than one color, and where the mirror image leaves the grid.
- No witness has the verdict `other`. The rule is relational, so the concept file's rule approximates nothing.

## Choice points
- `inside`: which cells of the closed outline's frame take the shape's color
    - `concept`: each cell off the outline that no 4-walk through cells off the outline reaches from the frame edge
    - `$Enclosed8`: replaces `fill-inside`; the walk from the frame edge also takes diagonal steps. Undefined where the concept is. Fails Fit at train0: the walk passes between the diagonal edge cells, so nothing is enclosed.
    - `$SpanAlong`: replaces `fill-inside`; each cell off the outline with outline cells on both sides along `mirror-dir`'s axis. Undefined where the concept is. Fits every pair. Witness `top-notch`: breaks no scene claim, at the stored assignment, `ordinary`, verdict `concept`.
    - `$SpanAcross`: replaces `fill-inside`; each cell off the outline with outline cells on both sides along the other axis. Undefined where the concept is. Fits every pair. Witness `left-dent`: breaks no scene claim, at the stored assignment, `ordinary`, verdict `concept`.
    - `$SpanBoth`: replaces `fill-inside`; each cell off the outline with outline cells on both sides along each axis. Undefined where the concept is. Fits every pair. Witness `curl-pocket`: breaks no scene claim, at the stored assignment, `borderline`, verdict `concept`. Invariant broken: each row and each column of every input's closed outline meets its inside in one run.
    - `$SpanEither`: replaces `fill-inside`; each cell off the outline with outline cells on both sides along some axis. Undefined where the concept is. Fits every pair. Witness `top-notch`: breaks no scene claim, at the stored assignment, `ordinary`, verdict `concept`.
    - `$ErodeFilled`: replaces `fill-inside`; the outline with its enclosed cells, less that set's rim (lib `Rim`), so an outline cell with all four neighbors in the set takes the color. Undefined where the concept is. Fits every pair. Witness `hanging-tip`: breaks no scene claim, at the stored assignment, `ordinary`, verdict `concept`.
- `mirror-axis`: where the mirror line lies
    - `concept`: the line just past the shape's edge toward `mirror-dir`, so the image doubles the edge column
    - `$AxisOnEdge`: replaces `mirror`; the line runs through the shape's edge column, which the image shares. Undefined where the concept is. Fails Fit at train0.
- `mirror-dir`: the side the shape is mirrored toward
    - `concept`: stored, R
    - `$MirrorDirFromEnds`: replaces `half-outline` and the stored `mirror-dir`; the program derives the direction as the one side of the shape's bounding box whose line holds both ends of the curve, an end being a shape cell with one 8-neighbor in the shape. Undefined where the shape has other than two ends, where no side or more than one side holds both, and where the concept is undefined at the derived direction. Fits every pair. Witness `opens-left`: breaks `half-outline` and `room`, at the stored assignment, `variant`, verdict `$MirrorDirFromEnds`. Invariant broken: every input's shape opens to the right.
- `bg`: the background color
    - `concept`: stored, 0
    - `bg=DominantColor`: replaces the stored `bg` and `one-shape`'s field color; the commonest color of the input. Undefined where that color ties, and where the concept is undefined at it. Fits every pair. Witness `bg=DominantColor`: breaks `one-shape`, at the stored assignment, `variant`, verdict `bg=DominantColor`. Invariant broken: every input's background is 0.
    - `bg=SharedColor`: replaces the stored `bg`; on one input it gives every color of that input, so the shape's color is a `bg` value too. Undefined on every pair's input, where the image at that value leaves the grid. Fails Fit at train0.
    - `bg=RarestColor`: replaces the stored `bg`; the least common color of the input, which is the shape's color. Undefined on every pair's input, where the image leaves the grid. Fails Fit at train0.
- `inside` & `mirror-axis`, `inside` & `mirror-dir`, `inside` & `bg`, `mirror-axis` & `mirror-dir`, `mirror-axis` & `bg`, `mirror-dir` & `bg`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Keeping the outline in the output: every train output erases it, so the pairs determine it.
- A stored fill color: the shape's color is 7, 8 and 6 in the train pairs, so no stored value fits, and the fill takes the shape's color.
- A span along a diagonal axis: no reading of the pairs ties the inside to a diagonal line, and the outlines in train0, train2 and the test run along diagonals.

## Tickets filed
- 10-490_task_bf32578f_analyze.md
