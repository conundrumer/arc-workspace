# c97c0139

## Concept
- The concept fits every pair: `work/task/c97c0139/probe.py` reproduces train0, train1 and test0. The diamond rule has a relational form (the two cells d steps along the line from the foot are in the segment), so no approximation stands in for it. No witness has verdict `other`.
- Under the concept, a line-cell component that isn't straight is no segment and gets no fill. Only `bent-line` and `background=DominantColor` reach that behavior.

## Choice points
- `line-cells`: which cells form the lines
    - `concept`: every cell that isn't `background`
        - `fill-source`: where a diamond's fill color comes from
            - `concept`: the one stored `fill_color`
            - `$FillByLineColor`: replaces `diamond-fill`'s color with a stored table `fill_by_line` from the segment's color to its fill color (`2 → 8`); undefined on an input that has a segment whose color isn't a key. It fits: the test's only line color, 2, is a train key. Witness `mapped-second-color` stands at `fill_by_line` = `{2 → 8, 3 → 4}` and breaks `segments` (one `line_color`). It is `borderline`, and its verdict is `concept`. The invariant it breaks is that every line in every input has color 2.
    - `$LineColorCells`: replaces `segments`' "non-background cells" with the cells of a stored `line_color` (2), which the program now reads; the fill still takes only `background` cells. It fits. Witness `two-colors` stands at the stored assignment and breaks `segments` (one `line_color`). It is `borderline`, and its verdict is `concept`. The invariant it breaks is that every line in every input has color 2.
        - `line_color`: how the line color is determined
            - `concept`: stored, 2
            - `line_color=RarestColor`: derived as the input's rarest color. It fits (2 is the rarest color in every input). Witness `line_color=RarestColor` stands at the stored assignment and breaks `segments` (one `line_color`). It is `borderline`, and its verdict is `concept`. The invariant it breaks is that every line in every input has color 2.
- `segment-identity`: what makes line cells one segment
    - `concept`: one 4-connected component that is a single row or a single column
    - `$StraightRuns`: replaces `segments` (straight components) with every maximal straight run of line cells in a row or a column, whatever its component. It fits. Witness `bent-line` stands at the stored assignment and breaks `segments` (each line is straight). It is `foreign`, and its verdict is `$StraightRuns`. The invariant it breaks is that every line-cell component is a straight run.
    - `$Components8`: joins line cells into components by 8-adjacency (`Components8`), so two segments that touch at a corner form one bent component and get no fill. It fits. Witness `corner-touch` stands at the stored assignment and breaks no scene claim. It is `ordinary`, and its verdict is `concept`.
    - `$CellPairs`: replaces the segment with any two line cells: a `background` cell fills when the two cells d steps along a line from its foot are both line cells, whether or not they are in one segment. It fails Fit at test0: the cell (4,5) of the row-4 segment pairs with the cells of the col-5 segment, and this fills cells such as (8,1) and (8,9), which are 0 in the test output.
- `fill-target`: which cells of a diamond take the fill
    - `concept`: the diamond's `background` cells (`keep`)
    - `$PaintOverLines`: replaces `keep` for line cells: every diamond cell outside the diamond's own segment takes the fill, which includes the cells of another segment. It fits. Witness `line-in-diamond` stands at the stored assignment and breaks `apart`. It is `borderline`, and its verdict is `concept`. The invariant it breaks is that no segment lies inside another segment's diamond.
- `background`: how the background is determined
    - `concept`: stored, 0
    - `background=DominantColor`: derived as the input's most common color. It fits. Witness `background=DominantColor` (a segment of 2 on a field of 5) stands at the stored assignment and breaks `segments` (a `background` field of 0). It is `variant`, and its verdict is `background=DominantColor`. The invariant it breaks is that the field is 0 in every input.
    - `background=SharedColor`: derived as the colors present in every input, 0 and 2. It fails Fit at train0, because the value 2 gives a second output grid there.
    - `background=RarestColor`: derived as 2. It fails Fit at train0: the 0 field becomes the line cells and the segment's diamond isn't filled.
- `fill_color`: how the fill color is determined
    - `concept`: stored, 8
    - `fill_color=OutNewColor`: derived as a color in every train output and in no input. It fails Fit at train0: a run has an empty `ex_out`, so the derivation gives no value and the model is undefined on every input. Every proposer that reads the inputs alone gives 0 or 2, never 8.
- `line-cells` & `segment-identity`, `line-cells` & `fill-target`, `line-cells` & `background`, `line-cells` & `fill_color`, `segment-identity` & `fill-target`, `segment-identity` & `background`, `segment-identity` & `fill_color`, `fill-target` & `background`, `fill-target` & `fill_color`, `background` & `fill_color`, `line_color` & `segment-identity`, `line_color` & `fill-target`, `line_color` & `background`, `line_color` & `fill_color`, `fill-source` & `segment-identity`, `fill-source` & `fill-target`, `fill-source` & `background`: the two branches' changes applied together
- `fill_color` & `fill-source`: the model of `$FillByLineColor` alone, which reads no `fill_color`
- `line_color` & `fill-source`: no case takes both, because the two points stand under different branches of `line-cells`
- `background` with `$LineColorCells` & `$PaintOverLines`: under those two branches together, no step reads `background`, so a case that also takes a `background` derivation has the model of `$LineColorCells` & `$PaintOverLines`

## Open parameters
- none

## Not formed
- A stored axis for the lines (one member of `Axis`): train1 has a vertical segment and a horizontal segment, and both get a diamond. So the program enumerates both axes, and no variant task narrows that set.
- A fill on one side of the line only: every segment in the pairs gets a fill on both sides.
- Another fill shape, such as a band at a fixed distance from the segment or the segment's bounding square: in train0, row 1 has 2 fill cells and row 6 has 12, and only the diamond gives that.
- A diamond read as a taxicab ball around the segment's midpoint: an even-length segment's midpoint isn't a cell, so that claim has no relational form. On every straight segment it gives the concept's cells.
- A model that is undefined when a diamond reaches past the grid edge: no reading of the task gives that, and no pair's diamond reaches the edge.
- A derivation of `line_color` under the concept branch of `line-cells`: there the program doesn't read `line_color`, which is a scene parameter.

## Tickets filed
- 10-572_task_c97c0139_analyze.md
