# d4c90558

## Concept
- The concept fits every pair, and the program reproduces each train and test output (`check_concept.py`, `probe2.py`).
- Each rule has a relational form. Frames are one-color 4-connected outline components (`Components`) that enclose cells (`Closed`), and the count is a cell count. No rule is approximated.
- No witness has verdict `other`.
- The concept is undefined on two inputs. One is an input where two frames hold the same count, which breaks `distinct-counts` (see `$TiesEitherOrder`). The other is an input where every frame holds no mark, so the output width is 0.

## Choice points
- `counted-cells`
    - `concept`: the cells of `mark_color` in a frame's region are counted.
        - `mark_color`
            - `concept`: stored, `5`.
            - `mark_color=RarestColor`: derives `mark_color` as the rarest color of the input, and replaces the stored value in `count`. It is undefined where two colors tie for rarest, and where no frame holds a cell of the derived color. It fits every pair. Witness `mark_color=RarestColor` (the `stray-other-color` grid): a color-3 cell inside the 6-frame breaks `marks-inside`. Plausibility `borderline`, verdict `concept`. Invariant broken: every non-background cell inside a frame is color 5.
            - `mark_color=SharedColor`: derives `mark_color` from one input alone, which gives every color of that input. It fails Fit at train0.
            - `mark_color=VanishedColor`: with `ex_out` empty, this gives every color of the input. It fails Fit at train0.
    - `$CountAnyColor`: replaces `count`. Every non-background cell in the region, other than the frame's own cells, is counted, and there is no `mark_color` parameter. A frame is any non-background component that encloses cells. It fits every pair. Witness `stray-other-color`: a color-3 cell inside the 6-frame breaks `marks-inside`. Plausibility `borderline`, verdict `concept`. Invariant broken: every non-background cell inside a frame is color 5.
- `count-area`
    - `concept`: the region the frame's outline encloses.
    - `$CountInBbox`: replaces `count` and the enclosure part of `frames`. A frame is any non-mark component of more than one cell, and its count is the `mark_color` cells in its bounding box. It fits every pair. Witness `broken-outline`: a gap in the 6-frame's top side breaks `frames`. Plausibility `foreign`, verdict `$CountInBbox`. Invariant broken: every frame's outline is closed.
- `frame-unit`
    - `concept`: one bar per outline component.
    - `$FramePerColor`: replaces `bar`. One bar per frame color, whose count is the sum over the frames of that color. It fits every pair. Witness `two-frames-one-color`: two frames of color 2 break `frames`. Plausibility `borderline`, verdict `concept`. Invariant broken: no two frames share a color.
- `order-key`
    - `concept`: lines ascend by count.
    - `$OrderBySize`: replaces `order`. Lines ascend by the area of the frame's bounding box. It fits every pair. Witness `larger-frame-fewer-marks`: the 2-frame holds 5 marks in a smaller box than the 6-frame, which holds 4. Plausibility `ordinary`, verdict `concept`.
    - `$OrderByInterior`: replaces `order`. Lines ascend by the cell count of the enclosed region. It fails Fit at train2 (interiors 12, 30, 35, 42 order the frames 8, 2, 3, 4).
    - `$OrderByFrameCells`: replaces `order`. Lines ascend by the frame's cell count. It fails Fit at train2 (18, 28, 39, 42 order the frames 8, 3, 4, 2).
    - `$OrderByTop`: replaces `order`. Lines follow the frames' top rows. It fails Fit at train0 (top rows order the frames 8, 1, 7).
- `tie-order`
    - `concept`: undefined where two lines have one key.
    - `$TiesEitherOrder`: adds a rule. Lines with equal keys take either order, and the output holds each order. It fits every pair. Witness `tied-counts`: both frames hold 4, which breaks `distinct-counts`. Plausibility `variant`, verdict `$TiesEitherOrder`.
- `empty-frame`
    - `concept`: a frame with count 0 gives a line of background.
    - `$DropEmpty`: replaces `size`. Frames with count 0 give no line. It fits every pair. Witness `empty-frame`: the 2-frame holds no mark, which breaks `marks-inside`. Plausibility `variant`, verdict `concept`.
- `background_color`
    - `concept`: stored, `0`.
    - `background_color=DominantColor`: derives `background_color` as the commonest color of the input, and replaces the stored value in `count`, `bar` and `frames`. It is undefined where two colors tie for commonest. It fits every pair. Witness `background_color=DominantColor` (the `frame-outnumbers-background` grid): a thick 6-frame covers more cells than the background. Plausibility `borderline`, verdict `concept`. Invariant broken: the background is the commonest color of every input.
    - `background_color=SharedColor`: derives `background_color` from one input alone, which gives every color of that input. It fails Fit at train0.
- `counted-cells` & `count-area`, `counted-cells` & `frame-unit`, `counted-cells` & `order-key`, `counted-cells` & `tie-order`, `counted-cells` & `empty-frame`, `counted-cells` & `background_color`, `count-area` & `frame-unit`, `count-area` & `order-key`, `count-area` & `tie-order`, `count-area` & `empty-frame`, `count-area` & `background_color`, `frame-unit` & `order-key`, `frame-unit` & `tie-order`, `frame-unit` & `empty-frame`, `frame-unit` & `background_color`, `order-key` & `tie-order`, `order-key` & `empty-frame`, `order-key` & `background_color`, `tie-order` & `empty-frame`, `tie-order` & `background_color`, `empty-frame` & `background_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `bar_start` and `short_end` as choice points: every pair fixes the bars to start at the left and the shortest bar to sit at the top.
- Bar length as the frame's rank, not its count: train0 has lengths 2, 4 and 8, and ranks would give 1, 2 and 3.
- Output width as a constant: the widths are 8, 4 and 6, and each one is the largest count.
- The thick sides of a frame as a direction or a count: no output reads them, and their sides differ from frame to frame with no link to the output.
- Marks outside every frame counted toward the nearest frame: no input has a mark outside a frame, so no pair separates a reading.
- Nested frames, with the inner frame's marks counted in the outer frame or not: no input nests frames, and the region the concept reads includes everything that the outline encloses.

## Tickets filed
- none
