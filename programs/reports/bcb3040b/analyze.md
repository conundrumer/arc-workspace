# bcb3040b

## Concept
- Fits every pair at the stored assignment (`marker_color` 2, `line_paint` 0 → 2, 1 → 3).
- Its rules have a relational form, and no witness has the verdict `other`.
- It is undefined where the scene claims fail: a count of markers other than two, two markers off one line, or a segment cell whose color has no `line_paint` entry.

## Choice points
- `segment-extent`
    - `concept`: the cells strictly between the two markers
    - `$ExtendFullLine`: replaces `draw-segment`; the whole line through the two markers, from grid edge to grid edge, takes `line_paint`, the markers excepted; parameters `marker_color`, `line_paint`; undefined where the concept is. Fits every pair.
        - witness `extend-past-markers`: markers at `(3,2)`, `(3,7)` inside a 10×10 grid; breaks `markers-on-opposite-edges`; stored assignment; plausibility `variant`; verdict `concept`; breaks the invariant that both markers sit on grid edges in every input.
- `marker-set`
    - `concept`: exactly two markers, joined to each other
    - `$EveryAlignedPair`: replaces `two-markers` and `markers-aligned`; every pair of marker cells on one row, column or diagonal is joined; parameters `marker_color`, `line_paint`; undefined where a segment crosses a cell with no `line_paint` entry, a third marker in line included. Fits every pair.
        - witness `four-markers`: markers at the four corners of a 10×10 grid; breaks `two-markers`; stored assignment; plausibility `variant`; verdict `$EveryAlignedPair`; breaks the invariant that every input holds exactly two cells of 2.
- `crossing-paint`
    - `concept`: a segment cell's paint is keyed by its input color
    - `$CrossAnyFg`: replaces `draw-segment` and `noise-field`; a segment cell of `bg` takes `bg_paint`, and a cell of any other color takes `cross_paint`; parameters `marker_color` 2, `bg` 0, `bg_paint` 2, `cross_paint` 3; undefined where a segment crosses a marker cell, and where the concept's marker claims fail. Fits every pair.
        - witness `third-noise-color`: noise in 0, 1 and 5, with 5 on the diagonal between the markers at `(4,4)`; breaks `noise-field`; stored assignment; plausibility `variant`; verdict `$CrossAnyFg`; breaks the invariant that the noise uses only 0 and 1.
- `line-color`
    - `concept`: the paint for a background segment cell is stored in `line_paint`
    - `$LineInMarkerColor`: replaces `draw-segment`; a segment cell of `bg` takes `marker_color`, and `line_paint` keeps only 1 → 3; parameters `marker_color` 2, `bg` 0, `line_paint` 1 → 3; undefined where a segment crosses a color other than 0 and 1, and where the concept's marker claims fail. Fits every pair.
        - witness `marker-color-line`: markers of 4 at the corners `(0,0)`, `(9,9)`; breaks no scene claim at its assignment; stands at `marker_color` = 4; plausibility `variant`; verdict `$LineInMarkerColor`; breaks the invariant that the markers are 2 in every input.
- `marker_color`
    - `concept`: stored, 2
    - `marker_color=RarestColor`: replaces `two-markers` by deriving `marker_color` as the one color of fewest cells in the input; undefined where colors tie for the fewest, and where the concept is. Fits every pair.
        - witness `marker_color=RarestColor`: three unaligned cells of 2 and two cells of 1 on row 8 of a blank 10×10 grid; breaks `two-markers`; stored assignment; plausibility `borderline`; verdict `$EveryAlignedPair`; breaks the invariants that every input holds exactly two cells of 2 and that color 1 covers about half the grid.
- `segment-extent` & `marker-set`, `segment-extent` & `crossing-paint`, `segment-extent` & `line-color`, `segment-extent` & `marker_color`, `marker-set` & `crossing-paint`, `marker-set` & `line-color`, `marker-set` & `marker_color`, `crossing-paint` & `line-color`, `crossing-paint` & `marker_color`, `line-color` & `marker_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A segment between two markers that share no row, column or diagonal (a rasterized line, or a path with a turn): no pair and no reading of the concept gives one, and every input aligns its markers.
- A subset of the line axes: rows (train1), columns (train2), the main diagonal (train0) and the anti-diagonal (test0) all occur, so the program enumerates every `Axis4` value.
- `line_paint` derived by `ChangedPairs` or `VanishedNewPairs`, and its paint colors by `OutNewColor` or `AnyOutNewColor`: each reads `ex_out`, which is empty in a run on one input, so the model is undefined on every input and fails Fit at train0.
- `marker_color` derived by `SharedColor`, `DominantColor`, `ChangedColor`, `UnchangedColor` or `VanishedColor`: on one input the first two give noise colors as markers, and the others read `ex_out` and give none, so each model is undefined on every pair and fails Fit at train0.
- `marker_color` read as the color with exactly two cells, or as the color outside `field_colors`: no proposer gives either derivation, and `RarestColor` is the built-in derivation that gives `marker_color` on every pair.

## Tickets filed
- none
