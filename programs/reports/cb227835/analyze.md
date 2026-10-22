# cb227835

## Concept
- Fits every pair: train0, train1, train2 and test0 each match the concept's output (`work/task/cb227835/probe.py`).
- Every rule has a relational form. The two paths are a straight run along the axis of the larger offset and a diagonal run, taken in both orders, and their lengths are |dr − dc| and min(|dr|, |dc|).
- No witness has the verdict `other`.
- The concept is defined where the markers share a row, a column or a diagonal. There, both paths are the same straight or diagonal line. No branch differs from the concept on those inputs.
- With fewer than two cells of `marker_color`, the concept draws nothing and returns the input.

## Choice points
- `marker-cells`: which cells are the two markers
    - `concept`: the cells of the stored `marker_color`
        - `marker-color-source`: where `marker_color` gets its value
            - `concept`: stored, 8
            - `marker_color=RarestColor`: replaces the stored value in `two-markers` with the input's least frequent colors, derived on each input; undefined where the derived colors cover more than two cells. Fits every pair. Witness `marker_color=RarestColor`: two marks of color 2 and no 8 cell. It breaks `two-markers`, stands at the stored assignment, plausibility `variant`, verdict `marker_color=RarestColor`. It breaks the invariant that every input's two marks are 8.
            - `marker_color=DominantColor`: derives 0, so every background cell is a marker. Undefined on train0, so it fails Fit at train0.
            - `marker_color=SharedColor`: derives 0 and 8, so every cell is a marker. Undefined on train0, so it fails Fit at train0.
            - `marker_color=<a proposer that reads train outputs>` (`OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs`, `VanishedNewPairs`): gives no value when `ex_out` is empty, so it is undefined on every input and fails Fit at train0.
    - `$NonBackground`: replaces `two-markers` with "the input holds exactly two cells not of `background`, of any colors". It reads `background` as a parameter (stored 0) in place of `marker_color`, and is undefined where the count of non-background cells is not two. Fits every pair. Witness `markers-mixed-colors`: one mark is 8 and one is 2. It breaks `two-markers`, stands at the stored assignment, plausibility `borderline`, verdict `$NonBackground`. It breaks the invariant that both marks in every input have one color, 8. The witness `marker_color=RarestColor` also separates this branch from the concept, at `variant`.
        - `background-source`: where `background` gets its value
            - `concept`: stored, 0
            - `background=DominantColor`: derives the input's most frequent color; undefined where two colors tie for it. Fits every pair. Witness `background=DominantColor`: two 8 marks on a field of 5. It breaks `two-markers` (the field is not `background`), stands at the stored assignment, plausibility `variant`, verdict `concept`. It breaks the invariant that every input's field is 0. On that witness, `$NonBackground` at the stored 0 is undefined, and this branch gives the concept's output.
            - `background=RarestColor`: derives 8, so the 0 cells are the markers. Undefined on train0, so it fails Fit at train0.
            - `background=SharedColor`: derives 0 and 8, so no cell is a marker. Undefined on train0, so it fails Fit at train0.
            - `background=<a proposer that reads train outputs>`: gives no value with `ex_out` empty. Undefined on every input, so it fails Fit at train0.
- `path-color-source`: where `path_color` gets its value
    - `concept`: stored, 3
    - `path_color=RarestColor`: derives 8 and draws the paths in 8. Fails Fit at train0.
    - `path_color=DominantColor`: derives 0 and draws the paths in 0. Fails Fit at train0.
    - `path_color=SharedColor`: derives 0 and 8, which gives two outputs that are both wrong. Fails Fit at train0.
    - `path_color=<a proposer that reads train outputs>` (`OutNewColor`, `AnyOutNewColor` and the rest): gives no value with `ex_out` empty. Undefined on every input, so it fails Fit at train0.
- `marker-cells` & `path-color-source`, `marker-color-source` & `path-color-source`, `background-source` & `path-color-source`: the two branches' changes applied together. Every branch of `path-color-source` fails Fit at train0, so each combination fails Fit there too.

## Open parameters
- none

## Not formed
- Outline of the filled region the two paths bound, read as the region's 4-adjacency rim: on every input it gives the same cells as the two paths, so it is equivalent to the concept.
- Union of every shortest king-move path between the markers: on train0 the union fills a rectangle tilted 45 degrees, with no straight sides. Its outline is no candidate of any pair, so it is not a reading of the pairs.
- Single-turn paths with two straight runs, the elbow form of 0e671a1a: the pairs show diagonal sides, so no pair fits.
- A rule that pairs off more than two markers: every input holds exactly two, and no pair, solver header or proposer gives a rule for which markers join. The property has no answer that the pairs support.
- Markers on one row, column or diagonal, drawn as nothing: no source gives that reading, and the concept's single line is what both paths give.

## Tickets filed
- none
