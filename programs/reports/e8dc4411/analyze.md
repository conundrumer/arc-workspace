# e8dc4411

## Concept
- The concept fits every pair: train0, train1, train2 and test0 (`work/task/e8dc4411/check_concept.py`, `work/task/e8dc4411/probe.py`).
- No witness has the verdict `other`. No rule of the concept is an approximation: the step counts the diagonal lines the template spans, and the copies are translates of the template.
- The concept case is undefined where the input holds no unique diagonal direction with the marker diagonally next to a template cell and past every template cell, where the template spans an odd number of projection units along that diagonal (so that no whole step exists), and where the input does not hold exactly one marker cell.
- On `bar-template`, the concept steps by the bar's diagonal extent (2) and leaves the marker apart from the copies. The verdict there is `$NoOverlapStep`, which is the output of `$NoOverlapStep` and `$MarkerInCopyStep`. On the other witnesses, the concept case is undefined or its output is the verdict.
- Every template in the evidence is symmetric under all eight D4 transforms. That symmetry is the reason why the step and copy-transform branches agree with the concept on every pair.

## Choice points
- `step`: how far each copy moves along the diagonal
    - `concept`: the template's extent along the diagonal, which is half of the projection span plus one (rule `step`)
    - `$NoOverlapStep`: replaces `step`. The step is the least k at which the template translated by k diagonal steps shares no cell with the template. It is defined also where the span is odd. Later copies can paint over template cells. It fits every pair. Witness `bar-template`: breaks no scene claim; stored assignment; plausibility `variant`; verdict `$NoOverlapStep`; it breaks the invariant that every template is symmetric under all of D4.
    - `$MarkerInCopyStep`: replaces `step`. The step is the largest k at which the template translated by k diagonal steps holds the marker. It is defined also where the span is odd. It fits every pair. Witness `bar-template`, as for `$NoOverlapStep`. It is not equivalent to `$NoOverlapStep`: on a template of cells (1,1) and (3,3) with the marker at (4,4), `$NoOverlapStep` steps by 1 and `$MarkerInCopyStep` steps by 3.
    - `$BboxStep`: replaces `step`. Each copy moves by the template's bounding-box height and width. It fails Fit at train0 (step 3 in place of 2).
    - `$MarkerAnchorOffset`: replaces `step`. The first copy is the template translated so that its cell nearest the template's far side along the opposite diagonal lands on the marker, and the later copies repeat that offset. It is undefined where two template cells tie for that place. It fails Fit at train0, where (3,4) and (4,3) tie.
- `copy-transform`: what each copy is, relative to the copy before it
    - `concept`: the template translated unchanged (rule `step`)
    - `$MirroredCopies`: replaces `step`. Each copy is the previous copy reflected across the diagonal line, perpendicular to the direction, that lies one cell past it. Thus the odd copies are mirror images of the template. It is undefined where the concept case is undefined. It fits every pair. Witness `asymmetric-template`: breaks no scene claim; stored assignment; plausibility `variant`; verdict `concept`; it breaks the invariant that every template is symmetric under all of D4.
    - `$RotatedCopies`: replaces `step`. Each copy is the previous copy turned a half turn in its bounding box, then moved one step. It is undefined where the concept case is undefined. It fits every pair. Witness `asymmetric-template`, as for `$MirroredCopies`.
- `repeat`: how many copies
    - `concept`: copies at one, two, three and more steps, until a copy is fully outside the grid (rule `repeat`)
    - `$SingleCopy`: replaces `repeat`. Only the first copy is painted. It fails Fit at train0.
- `edge-clip`: a copy that is partly outside the grid
    - `concept`: its cells inside the grid are painted (rule `repeat`)
    - `$WholeCopiesOnly`: replaces `repeat`. The copies stop at the first copy that does not fit fully in the grid. It fails Fit at train0 (the copy at 8 steps, of which only (11,12) is inside).
- `copy-color`: the color of the copies
    - `concept`: the marker's color, read from the input (rule `paint`)
    - `$TemplateColorCopies`: replaces `paint`. The copies take `shape_color`. It fails Fit at train0.
    - `$StoredCopyColor`: replaces `paint` with a stored copy color. It fails Fit at train1, since the marker color is 2 in train0 and 3 in train1.
- `background`: the background color
    - `concept`: the most common color of the input (scene claim `background`)
    - `$StoredBackground`: replaces `background` with a stored color. It fails Fit at train1, since the background is 8 in train0 and 1 in train1.
- `shape-color`: how the template's color is found
    - `concept`: the stored parameter `shape_color` (scene claim `template-shape`)
    - `$TemplateByCount`: replaces `template-shape` and `single-marker` with a derivation. The template's color is the one color other than the background that has more than one cell, and the marker is the cell of any other color. It is undefined where the number of such colors is not one. It fits every pair. Witness `template-in-other-color`: breaks `template-shape`; stored assignment; plausibility `variant`; verdict `$TemplateByCount`; it breaks the invariant that the template is 0 in every input.
    - `shape_color=DominantColor`: on one input it gives the background color, so the template is the whole background. It fails Fit at train0.
    - `shape_color=RarestColor`: on one input it gives the marker's color, so no single marker cell is left. It fails Fit at train0.
    - `shape_color=SharedColor`: on one input it gives every color of that input, so no cell is a marker. It fails Fit at train0.
- `template-extent`: which cells of `shape_color` make up the template
    - `concept`: every cell of `shape_color` (scene claim `template-shape`)
    - `$TouchingComponentTemplate`: replaces `template-shape`. The template is the 8-connected component of `shape_color` cells that holds the cell diagonally next to the marker. It is undefined where the marker is diagonally next to cells of more than one component, or of none. It fits every pair. Witness `second-blob`: breaks `template-shape`; stored assignment; plausibility `borderline`; verdict `$TouchingComponentTemplate`; it breaks the invariant that the cells of color 0 form one 8-connected piece.
        - `adjacency`: the adjacency of the component
            - `concept`: 8-adjacency
            - `$FourAdjacency`: the component is 4-connected. It fails Fit at train0, where the diamond outline falls into four one-cell components.
- `marker-count`: how many markers
    - `concept`: exactly one marker cell (scene claim `single-marker`)
    - `$EachMarker`: replaces `single-marker`. Each cell of a color other than the background and `shape_color` is a marker, and each marker gets its own line of copies in its color. It is undefined where some marker has no direction, and where two lines of copies of different colors share a cell. It fits every pair. Witness `two-markers`: breaks `single-marker`; stored assignment; plausibility `borderline`; verdict `$EachMarker`; it breaks the invariant that every input holds one marker cell.
- `direction`: how the diagonal direction is found
    - `concept`: the diagonal direction from the template to the marker, with the marker past every template cell along it (scene claim `marker-past-diagonal-tip`, rule `direction`)
    - `$AdjacentCellDirection`: replaces `direction` and drops the condition of `marker-past-diagonal-tip` that the marker is past every template cell. The direction is the diagonal from the one template cell that is diagonally next to the marker. It is undefined where the marker is diagonally next to more than one template cell, or to none. It fits every pair. Witness `notch-marker`: breaks `marker-past-diagonal-tip`; stored assignment; plausibility `foreign`; verdict `$AdjacentCellDirection`; it breaks the invariant that the marker lies outside the template's bounding box.
- `step` & `copy-transform`, `step` & `repeat`, `step` & `edge-clip`, `step` & `copy-color`, `step` & `background`, `step` & `shape-color`, `step` & `template-extent`, `step` & `marker-count`, `step` & `direction`, `copy-transform` & `repeat`, `copy-transform` & `edge-clip`, `copy-transform` & `copy-color`, `copy-transform` & `background`, `copy-transform` & `shape-color`, `copy-transform` & `template-extent`, `copy-transform` & `marker-count`, `copy-transform` & `direction`, `repeat` & `edge-clip`, `repeat` & `copy-color`, `repeat` & `background`, `repeat` & `shape-color`, `repeat` & `template-extent`, `repeat` & `marker-count`, `repeat` & `direction`, `edge-clip` & `copy-color`, `edge-clip` & `background`, `edge-clip` & `shape-color`, `edge-clip` & `template-extent`, `edge-clip` & `marker-count`, `edge-clip` & `direction`, `copy-color` & `background`, `copy-color` & `shape-color`, `copy-color` & `template-extent`, `copy-color` & `marker-count`, `copy-color` & `direction`, `background` & `shape-color`, `background` & `template-extent`, `background` & `marker-count`, `background` & `direction`, `shape-color` & `template-extent`, `shape-color` & `marker-count`, `shape-color` & `direction`, `template-extent` & `marker-count`, `template-extent` & `direction`, `marker-count` & `direction`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Copies paint over background cells only, in place of over every cell: under the concept, the copies lie past the template along the diagonal, and the marker's cell takes its own color. Thus the two models give one output on every input and are equivalent.
- A copy stops at the grid edge only when it leaves the grid fully, in place of while any of its cells is inside: these are one condition, stated two ways.

## Tickets filed
none
