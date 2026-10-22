# b0039139

## Concept
- The concept fits every train and test pair (`check_concept.py`). Each rule has a relational form: the count is the number of 4-connected components, the box is the bounding box of one color's cells, and the line of copies is a placement along the panel axis.
- No witness of the concept case has the verdict `other`.
- Both solid panels can take the shape color or the mark color: train1's far panel is solid 3, and train2's far panel is solid 4. The concept therefore finds panels by content, as solid or not solid, and reads the shape and the marks only inside their own panels.

## Choice points
- `mark-count`
    - `concept`: N is the number of 4-connected components of `mark_color` in the count panel.
    - `$MarkCells`: replaces `count`. N is the number of `mark_color` cells in the count panel divided by a stored `mark_size` (2), and the branch is undefined where that number of cells is not a multiple of `mark_size`. It fits every pair. Its witness is `mixed-mark-sizes`, which breaks `count-panel` and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the invariant that every mark is a domino.
    - `$Marks8`: replaces `count`. The marks are the 8-connected components of `mark_color`. It fits every pair. Its witness is `marks-touch-at-corner`, which breaks `count-panel` and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the invariant that no two marks touch, even at a corner.
    - `$MarksAnywhere`: replaces `count`. N is the number of `mark_color` components over the whole input. It fails Fit at train1, where the far solid panel is color 3, so it gives four copies where the output has three.
- `shape-source`
    - `concept`: the bounding box of the `shape_color` cells in the shape panel.
    - `$ShapeAnywhere`: replaces the box in `tile-shape` with the bounding box of the `shape_color` cells over the whole input. It fails Fit at train2, where the far solid panel is color 4, so the box spans that panel.
    - `$PanelInset`: replaces the box in `tile-shape` with the shape panel inset by a stored `margin` (1) on every side. The branch is undefined where the panel is no wider than twice the margin on an axis. It fits every pair. Its witness is `wide-margin`, which breaks no scene claim and stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant that the shape sits one cell in from each side of its panel.
- `panel-roles`
    - `concept`: roles come from content. The shape panel is the end panel that is not solid, the count panel is next to it, the fill panel is the solid panel next to the count panel, and the field panel is the far end.
    - `$PanelOrder`: replaces how `shape-panel`, `count-panel` and `recolor` find the panels. In order from a stored corner `start_corner` (top-left), along the panel axis, the panels are the shape, count, fill and field panels. The branch is undefined where the third or fourth panel is not solid, and this includes every input whose shape panel is at the bottom or right end. On each input that meets the concept's scene claims, it gives the concept's output or is undefined. It fits every pair. Its witness is `solid-shape-panel`, which breaks `shape-panel` and stands at the stored assignment. Plausibility `foreign`, verdict `$PanelOrder`. It breaks the invariant that the shape panel holds a shape on background.
    - `$FillLarger`: replaces the fill and field roles in `recolor`. The fill panel is the larger solid panel, and the field panel is the smaller one. The branch is undefined where the two solid panels are the same size. It fails Fit at train2, where both solid panels are 6×6.
- `gap`
    - `concept`: the stored `gap_width` (1).
    - `$GapFromMarkSpacing`: replaces `gap_width` in `tile-shape`. The gap is the shortest run of background between two different marks along a row or column of the count panel. The branch is undefined where no two marks face each other along a row or column. It fits every pair. Its witness is `marks-two-apart`, which breaks no scene claim and stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant that neighbor marks are one cell apart.
    - `$GapFromDivider`: replaces `gap_width` in `tile-shape`. The gap is the thickness of the divider lines, and the branch is undefined where the dividers differ in thickness. It fits every pair. Its witness is `thick-dividers`, which breaks `panels` and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the invariant that the divider lines are one cell wide.
    - `gap_width=SepThickness`: it fails Fit at train0, where the derivation gives 2 on that input alone.
    - `gap_width=Period`: it fails Fit at train0, where the derivation gives no value.
    - `gap_width=TileDim`: it fails Fit at train0, where the derivation gives several values.
- `recolor`
    - `concept`: a shape cell takes the fill panel's color, and every other cell takes the field panel's color.
    - `$ColorMap`: replaces `recolor` with a stored mapping on the box's colors: `shape_color` to the fill panel's color, and `background` to the field panel's color. The branch is undefined where the box holds any other color. It fits every pair. It fails Subsumption: wherever it is defined, it gives the concept case's output, and the concept case is defined where it is not. No witness exists on which it is defined and differs. Its witness is `stray-color-in-shape`, which breaks `shape-panel` and stands at the stored assignment. Plausibility `foreign`, verdict `concept`. It breaks the invariant that the shape panel holds only `shape_color` and `background`.
- `divider_color`
    - `concept`: stored (1).
    - `divider_color=SharedColor`, `divider_color=DominantColor`, `divider_color=RarestColor`: each fails Fit at train0. On that input alone they give six colors, 0, and 4.
- `shape_color`
    - `concept`: stored (4).
    - `shape_color=RarestColor`: it fails Fit at train2, where it gives 3.
    - `shape_color=DominantColor`, `shape_color=SharedColor`: each fails Fit at train0. They give 0, and six colors.
- `mark_color`
    - `concept`: stored (3).
    - `mark_color=RarestColor`, `mark_color=DominantColor`, `mark_color=SharedColor`: each fails Fit at train0. They give 4, 0, and six colors.
- `mark-count` & `shape-source`, `mark-count` & `panel-roles`, `mark-count` & `gap`, `mark-count` & `recolor`, `shape-source` & `panel-roles`, `shape-source` & `gap`, `shape-source` & `recolor`, `panel-roles` & `gap`, `panel-roles` & `recolor`, `gap` & `recolor`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored repetition axis: train0 repeats down and the other pairs repeat across, so a stored axis fails Fit. The panel axis is the only reading that fits.
- Copies that alternate a D4 transform: train2's shape has no symmetry, and its copies are identical.
- A gap in the fill color, or copies that touch: every output fixes the gap's color as the field color and its width as one line.
- N as the number of lines that hold marks: train2 has marks in five columns and four copies.
- A gap read from the shape's margin in its panel: the copies are bounding boxes, not panels, and no reading of the pairs ties their spacing to the panel's border.

## Tickets filed
- 10-137_task_b0039139_analyze.md
