# e8593010

## Concept
- The concept fits every pair: 4-connected pieces of `hole_color` take the color `size_color` gives for their cell count, and every other cell passes through.
- The concept is undefined on an input with a piece of 4 or more cells, because `size_color` has no entry for that size.
- No witness has verdict `other`. The rule has a relational form (Components and Tally over the hole cells, then a stored lookup), so the concept file states no approximation.

## Choice points
- `piece adjacency`
    - `concept`: pieces join hole cells through the four cardinal neighbors
    - `$Adjacency8`: replaces `color-by-size` with pieces joined through the eight neighbors (Components8), with parameters `hole_color` and `size_color`, undefined where an 8-connected piece has a size with no `size_color` entry. Fails Fit at train1: the cells (6,6), (6,7), (7,7), (8,6) of train1 input form one 8-connected piece of 4 cells, which has no entry.
- `color key`
    - `concept`: the piece's cell count keys `size_color`
    - `$RankBySize`: replaces `color-by-size` with the dense ascending rank of the piece's size among the sizes of the input's pieces (Ordinal) keying a stored `rank_color` (0 → `3`, 1 → `2`, 2 → `1`), undefined where an input has more distinct piece sizes than `rank_color` has keys. Fits every pair. Witness `no-domino`: train0 input with its dominoes filled with `5`, so only sizes 1 and 3 occur. The branch gives the three-cell pieces `2`, where the concept gives them `1`. It breaks no scene claim. Plausibility `variant`. Verdict `concept`. It breaks the invariant that every input holds pieces of each size 1, 2 and 3.
        - `rank direction`
            - `concept`: ascending rank, the smallest present size at rank 0
            - `$RankDesc`: the rank descends, the largest present size at rank 0, with a stored `rank_color_desc` (0 → `1`, 1 → `2`, 2 → `3`) distinct from `rank_color`. Fits every pair. Witness `no-domino`: the branch gives the single cells `2`, where `$RankBySize` gives them `3` and the concept also gives them `3`. It breaks no scene claim. Plausibility `variant`. Verdict `concept`. It breaks the same invariant as above.
    - `$ShapeKey`: replaces `color-by-size` with the piece's free shape (its cell set up to D4 and translation) keying a stored `shape_color` (single cell → `3`, domino → `2`, L three-cell piece → `1`, straight three-cell piece → `1`), undefined on a piece whose shape has no entry. Fits every pair. Every test shape occurs in a train pair. Witness `i-tromino-color`: train2 input at the assignment where `shape_color` gives the straight three-cell piece `2`, so the vertical piece at train2 input (0,8)–(2,8) takes `2`, where the concept gives it `1`. It breaks no scene claim. Plausibility `ordinary`. Verdict `concept`.
    - `$FixedShapeKey`: replaces `color-by-size` with the piece's shape up to translation alone keying a stored `fixed_shape_color` (single cell, both domino orientations, the four L orientations and the vertical straight piece), undefined on a piece whose shape has no entry, such as a horizontal straight three-cell piece. Fits every pair. Every test shape occurs in a train pair. Witness `vertical-domino-color`: train0 input at the assignment where `fixed_shape_color` gives the vertical domino `3`, so the vertical dominoes take `3`, where the concept gives them `2`. It breaks no scene claim. Plausibility `ordinary`. Verdict `concept`.
    - `$NeighborCount`: replaces `color-by-size` with a per-cell rule, where a hole cell's count of hole neighbors (0, 1, 2) keys the colors `3`, `2`, `1`. Fails Fit at train0: the cell (1,1) of the L piece at rows 1–2, cols 0–1 has one hole neighbor and takes `2`, where the output has `1`.
- `ink selection`
    - `concept`: the ink cells are the cells of the stored `hole_color` `0`
    - `hole_color=RarestColor`: derives `hole_color` per input as the rarest color, undefined on an input where colors tie for rarest. Fits every pair. Witness `hole_color=RarestColor`: test0 input with the isolated cell (0,2) set to `4`. The branch recolors only that cell, as a single, to `3`, and keeps the `0` cells, where the concept recolors the `0` pieces and keeps the `4`. It breaks `field-and-holes`. Plausibility `borderline`. Verdict `concept`. It breaks the invariant that every input holds only the colors `0` and `5`.
    - `hole_color=ChangedColor`: derives `hole_color` per input from the cells that change color. Fails Fit at train0: the derivation runs with no train outputs and gives no value, so the branch is undefined on every input.
    - `hole_color=VanishedColor`: derives `hole_color` per input as a color absent from the train outputs. Fails Fit at train0, for the same reason as `hole_color=ChangedColor`.
    - `$NonFieldInk`: replaces `field-and-holes` and `color-by-size` with ink as every cell not of `field_color` (which the program now reads, `5`), joined into 4-connected pieces whatever their colors, and keyed by size in `size_color`, undefined where a piece has a size with no entry. Fits every pair. Witness `stray-third-color`: the same input as the witness `hole_color=RarestColor`. The branch takes the `4` cell as a single and gives it `3`, where the concept keeps it `4`. It breaks `field-and-holes`. Plausibility `borderline`. Verdict `concept`. It breaks the invariant that every input holds only the colors `0` and `5`.
        - `field color`
            - `concept`: `field_color` stored as `5`
            - `field_color=DominantColor`: derives `field_color` per input as the commonest color, undefined on an input where colors tie for commonest. Fits every pair. Witness `field_color=DominantColor`: train1 input with its `5` cells recolored `7`. The branch recolors the holes and keeps the `7` field, as the concept does. `$NonFieldInk` takes every cell as ink and finds one 100-cell piece with no entry, so it is undefined. It breaks `field-and-holes` at the stored `field_color`. Plausibility `variant`. Verdict `concept`. It breaks the invariant that every input's field is `5`.
- `piece adjacency` & `color key`, `piece adjacency` & `ink selection`, `color key` & `ink selection`, `piece adjacency` & `rank direction`, `piece adjacency` & `field color`, `color key` & `field color`, `ink selection` & `rank direction`, `rank direction` & `field color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A `size_color` derived from the size, so that a color is 4 minus the cell count: it treats colors as numbers, and colors have identity and no other properties, so the claim has no relational form.
- `hole_color=SharedColor`, `hole_color=DominantColor`: on the pairs neither proposer gives `0` alone. Each gives `5`, whose field piece has no `size_color` entry, so neither can fit.
- Same-color pieces under `$NonFieldInk`, with ink cells of different colors kept apart: the two differ only where a cell of a third color touches a hole. That input breaks `field-and-holes`, and `stray-third-color` already separates the reading of a third color.
- A rule for pieces of 4 or more cells, such as a threshold at which every larger piece takes `1`: no pair has such a piece, and a variant task with larger pieces extends `size_color` by reassignment.

## Tickets filed
- none
