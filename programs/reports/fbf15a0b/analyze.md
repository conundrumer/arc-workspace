# fbf15a0b

## Concept
- Fits every pair (the probe `work/task/fbf15a0b/probe.py` checks train0–3 and test0–1). The generator draws the grid as `part_count` = 2 equal halves along one axis and puts the two markers on an edge line inside one half. The output is that half with the markers erased. The concept rule does what the generator does on every input that meets the scene claims, so it is no approximation.
- No witness has verdict `other`.
- The points at the concept's stored values (`marker_color` 5, `background` 8, `part_count` 2) each have a fitting derived branch. The concept is undefined where the cut is uneven, and two rounding branches fill that gap.

## Choice points
- `cut-axis`
    - `concept`: the axis of the line the marker cells share. A shared column halves the rows, and a shared row halves the columns.
    - `$CrossAxis`: replaces `halve-along-pair` and cuts the axis across the pair's line. No parameter of its own. Undefined where the concept is. Fails Fit at train0 (it gives 20×10, but the output is 10×20).
    - `$StoredAxis`: replaces `halve-along-pair` with a stored parameter `cut_axis` (Axis). Undefined where the marker cells are not collinear. Fails Fit: train0 halves rows and train3 halves columns, so no stored value fits both (DivisorRatioAxis proposes no axis).
    - `$EdgeLine`: replaces `halve-along-pair` and reads the axis of the grid edge line that holds both markers. Undefined where the pair lies on no edge line. Fails Subsumption: wherever it is defined, the concept gives the same output, so no witness shows it is not subsumed.
- `kept-part`
    - `concept`: the part holding the markers.
    - `$FarHalf`: replaces `keep-marker-half` and keeps the end part away from the markers. Undefined where the concept is. Fails Fit at train0 (it keeps rows 10–19).
    - `$StoredSide`: replaces `keep-marker-half` and keeps the end part toward a stored `kept_side` (Dir). Fails Fit: train0 keeps the top and train2 the bottom.
- `marker-cells`
    - `concept`: each marker cell becomes `background`.
    - `$KeepMarkers`: replaces `erase-markers` and copies the marker cells. Fails Fit at train0 (output (0,0), (2,0) would be 5).
    - `$RepairPattern`: replaces `erase-markers`. A marker cell takes the color that the dot lattice's period along the marker line gives it. Fails Fit at test0: it gives 9 at output (0,1), (0,3), and the expected output has 8 there.
- `part-count`
    - `concept`: `part_count` is stored as 2. DivisorRatio determines it.
    - `$CountMarkers`: derives `part_count` as the number of marker cells, by clauses, in place of the stored value in `halve-along-pair`. Undefined where the end part does not hold every marker. Fits every pair. Witness `marker-count`:
        - breaks `marker-pair` (three marker cells down column 0 of an 18-row grid)
        - stored assignment; plausibility `borderline`; verdict `concept`
        - invariant broken: every input has exactly two marker cells. Two cells are what a corner pair needs to give the axis, so the count says nothing about the parts.
    - `$MarkerSpacing`: derives `part_count` as the step between consecutive marker cells, by clauses. Undefined where the steps differ. Fits every pair. Witness `marker-spacing`:
        - breaks `marker-pair` (gap 2 against `marker_gap` 1)
        - stored assignment; plausibility `variant`; verdict `concept`
    - `part_count=DivisorRatio`, `part_count=Period`: on one input with `ex_out` empty, DivisorRatio gives no value. Period gives none either, because the markers break every period of each input. So both are undefined on every input and fail Fit at train0.
    - `part_count=TileCount`: several counts fit an extent of 20, so the model gives more than one grid on train0 and fails Fit there.
- `uneven-cut`
    - `concept`: undefined where the extent along the cut axis is not a multiple of `part_count`.
    - `$FloorPart`: replaces `even-extent`. The kept part runs ⌊n/`part_count`⌋ lines from the marker end. Undefined where the markers fall outside that part. Fits every pair. Witness `odd-extent`:
        - breaks `even-extent` (7 rows)
        - stored assignment; plausibility `borderline`; verdict `any`
        - invariant broken: every input's extent along the cut axis is even
    - `$CeilPart`: replaces `even-extent`, with ⌈n/`part_count`⌉ lines. Fits every pair. Witness `odd-extent`, same items as `$FloorPart`.
- `marker_color`
    - `concept`: stored as 5.
    - `marker_color=RarestColor`: each input's rarest color, ties included. Undefined where those colors' cells are not collinear in one end part. Fits every pair. Witness `marker_color=RarestColor`:
        - breaks no scene claim
        - stored assignment; plausibility `borderline`; verdict `concept`
        - invariant broken: in every input the pattern color has more cells than the marker color
    - `marker_color=VanishedColor`, `marker_color=ChangedColor`, `marker_color=SharedColor`: on one input with `ex_out` empty, each gives every color of the input. Every cell is then a marker and there is no marker line, so each is undefined and fails Fit at train0.
- `background`
    - `concept`: stored as 8.
    - `background=DominantColor`: each input's commonest color, ties included. Fits every pair. Witness `background=DominantColor`:
        - breaks no scene claim
        - stored assignment; plausibility `borderline`; verdict `concept`
        - invariant broken: background is the commonest color of every input
    - `background=SharedColor`: gives every input color, so train0 gets three grids. Fails Fit at train0.
    - `background=UnchangedColor`: with `ex_out` empty it gives no color, so it is undefined. Fails Fit at train0.
- `cut-axis` & `kept-part`, `cut-axis` & `marker-cells`, `cut-axis` & `part-count`, `cut-axis` & `uneven-cut`, `cut-axis` & `marker_color`, `cut-axis` & `background`, `kept-part` & `marker-cells`, `kept-part` & `part-count`, `kept-part` & `uneven-cut`, `kept-part` & `marker_color`, `kept-part` & `background`, `marker-cells` & `part-count`, `marker-cells` & `uneven-cut`, `marker-cells` & `marker_color`, `marker-cells` & `background`, `part-count` & `uneven-cut`, `part-count` & `marker_color`, `part-count` & `background`, `uneven-cut` & `marker_color`, `uneven-cut` & `background`, `marker_color` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Cropping to an object or to the content's bounding box: train2's output keeps parts of both dot blocks plus three empty rows, and train3's keeps the empty columns 7–10. No object or bounding-box crop gives those frames.
- The kept part chosen by the corner the markers sit at: a corner leaves the axis open. With the axis taken from the pair, this is the concept's `kept-part`.
- Other proposers (ScaleRatio, DimDiff, ConstInDim, ConstOutDim, TileD4, PanelCombine, SepTile*, CountRank*, the color-pair proposers): each gives a value of a type that no parameter of the program has, or that varies across pairs. Train output dims are 10, 10, 8 and 10, and the inputs have no separators.

## Tickets filed
- none
