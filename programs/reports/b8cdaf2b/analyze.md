# b8cdaf2b

## Concept
- Fits every pair (probe `probe.py`). The rule applies as stated, and no rule is an approximation. No witness has the verdict `other`. In every input, the base row is full and its flanks are equal, so rays that run to the frame edge always end at a side edge after as many cells as the flank is long. `$RayLenFlank` reads the task the other way, and the pairs can't separate the two readings. At `cell-on-ray`, the verdict goes to `$RayStopAtObstacle`, so the concept's overpainting of a non-background cell on a ray is the judged weak spot (plausibility `borderline`).

## Choice points
- `base-side`
    - `concept`: `base_side` stored, bottom
    - `$BaseSideDerived`: replaces the stored `base_side` with a derived value: the one edge whose line holds no `background` cell. It is undefined where no edge, or more than one edge, has such a line. Fits every pair. Witness `base-on-top`, which breaks `base-row` (read at bottom, the bottom line is all background). Plausibility `variant`, verdict `$BaseSideDerived`. Invariant broken: the base lies along the bottom edge in every input.
- `background`
    - `concept`: `background` stored, 0
    - `background=DominantColor`: `background` is derived as the commonest color of the input. It is undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor` (train1 with 0 recolored to 5), which breaks `background`. Plausibility `variant`, verdict `background=DominantColor`. Invariant broken: the field is 0 in every input.
    - `background=SharedColor`: on one input it gives every color of that input. At 2 and 4 the cap line holds no single run. Fails Fit at train0.
    - `background=RarestColor`: gives 4 on train0, and the cap line then holds no single run. Fails Fit at train0.
    - `background=OutNewColor`, `background=AnyOutNewColor`, `background=VanishedColor`, `background=ChangedColor`, `background=UnchangedColor`: with `ex_out` empty, each gives no value, so the model is undefined. Fails Fit at train0.
- `ray-extent`
    - `concept`: `diagonal-rays` runs each ray to the frame edge
    - `$RayLenFlank`: replaces the ray length in `diagonal-rays` with the length of the outer-color run on the base line beside the cap's end, clipped to the frame. It is defined wherever the concept is. Fits every pair. Witness `base-short-of-edges`, which breaks `base-row` (the line is not full). Plausibility `borderline`, verdict `concept`. Invariant broken: the base row spans the full width.
    - `$RayLenCapWidth`: replaces the ray length with the cap's width. Fails Fit at train1 (cap width 1, rays of 2).
- `ray-color`
    - `concept`: `cap` reads the inner color as the one color of the base-line cells under the cap
    - `$RayColorRarest`: replaces the inner color with the color that has the fewest cells in the input. It is undefined where two colors tie for fewest. Fits every pair. Witness `rarer-stray-cell`, which breaks `background`. Plausibility `borderline`, verdict `concept`. Invariant broken: no non-background cell lies outside the base.
    - `$RayColorBaseCenter`: replaces the inner color with the color of the base-line cell at the middle column. It is undefined where the line has even length. Fits every pair. Witness `base-off-center`, which breaks `base-row` (flanks of 3 and 1). Plausibility `borderline`, verdict `concept`. Invariant broken: the middle run is centered, with equal flanks.
    - `$RayColorStored`: stores one ray color. Fails Fit at train1 (train0's rays are 4 and train1's are 3).
    - `$RayColorLookup`: a table from inner color to ray color. Fails Fit at test0 (unseen key 2).
- `ray-anchor`
    - `concept`: `cap` anchors the rays at the ends of the one non-background run on the line next to the base
    - `$RayFromMiddleRun`: replaces `cap`. The rays anchor at the ends of the base line's middle run (the cells whose color differs from the line's end color), and they take that run's color. This model reads no `background`. It is undefined where the line's two ends differ in color, or where the middle is not one run of one color. Fits every pair. Witness `cap-narrower-than-middle`, which breaks `cap-row`. Plausibility `borderline`, verdict `concept`. Invariant broken: the cap covers exactly the middle run.
- `obstacle`
    - `concept`: `diagonal-rays` paints every ray cell, over any color
    - `$RayStopAtObstacle`: adds a rule: a ray stops before its first non-`background` cell. Fits every pair. Witness `cell-on-ray`, which breaks `background`. Plausibility `borderline`, verdict `$RayStopAtObstacle`. Invariant broken: no non-background cell lies outside the base.
    - `$RayBehindObstacle`: adds a rule: a ray keeps the color of each non-`background` cell on it and continues past that cell. Fits every pair. Witness `cell-on-ray`, which breaks `background`. Plausibility `borderline`, verdict `$RayStopAtObstacle`. Invariant broken: no non-background cell lies outside the base.
- `base-side` & `background`, `base-side` & `ray-extent`, `base-side` & `ray-color`, `base-side` & `ray-anchor`, `base-side` & `obstacle`, `background` & `ray-extent`, `background` & `ray-color`, `background` & `obstacle`, `ray-extent` & `ray-color`, `ray-extent` & `ray-anchor`, `ray-extent` & `obstacle`, `ray-color` & `ray-anchor`, `ray-color` & `obstacle`, `ray-anchor` & `obstacle`: the two branches' changes applied together
- `background` & `ray-anchor`: `$RayFromMiddleRun` reads no `background`, so where a case takes `$RayFromMiddleRun` and the concept branch at `base-side` and `obstacle`, the `background` property does not exist. That point stands at the concept. A case that takes `$RayFromMiddleRun` takes a `background` branch only together with `$BaseSideDerived`, `$RayStopAtObstacle` or `$RayBehindObstacle`, and it then applies both changes.
    - `background=DominantColor` & `$RayFromMiddleRun`: the model of `$RayFromMiddleRun` alone

## Open parameters
none

## Not formed
- Rays on the cardinal directions, or on both diagonal types: every output paints only the two diagonals that lead away from the base, so these readings use another orientation type and fail every pair.
- A single ray, toward one stored diagonal: every output holds both rays, so this reading fails every pair.
- `square-grid`: no rule reads the grid's shape, so no branch replaces this claim.
- `background` derived by `ChangedPairs`, `VanishedNewPairs`, `CountRankAsc`, `CountRankDesc`, or the dimension and tiling proposers: these proposers give no single color for the background.

## Tickets filed
none
