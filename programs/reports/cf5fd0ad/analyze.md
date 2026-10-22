# cf5fd0ad

## Concept
- Fits every pair (`probe.py`). The rules have a relational form and approximate nothing. No witness has the verdict `other`.

## Choice points
- `arrangement-grain`
    - `concept`: each quadrant applies one D4 element (`quadrant_transform`) to the input, and that element repeats `copies` × `copies` across the quadrant
    - `$TileTable`: replaces `quadrant-turn` and `quadrant-repeat`. It uses a per-tile D4 table `tile_transform` over a 4 × 4 layout of input-sized tiles, as the `TileD4` proposer gives it and as 7953d61e uses at 2 × 2. It is undefined on a non-square input. It fits every pair. Witness `three-copies`, at `copies` = 3: it breaks no scene claim, plausibility `ordinary`, verdict `concept`. The concept and `$CounterSpin` repeat each turn three times (18 × 18), and `$TileTable` keeps its 12 × 12 layout.
        - `quadrant-transform-source`: a choice point under the concept branch of `arrangement-grain`
            - `concept`: the stored table `quadrant_transform`
            - `$CounterSpin`: replaces `quadrant-turn`. The quadrant at `anchor` (`DIAG_BR`) holds the input. Each quadrant one clockwise step further around the arrangement holds the input turned one more quarter turn counterclockwise. The walk sense needs no parameter, because a walk counterclockwise with clockwise turns gives the same arrangement. It is undefined on a non-square input. It fits every pair. Witness `off-spin-table` reassigns `quadrant_transform` to a table that no anchor gives (top-left `D4_ID`) and changes none of this branch's parameters: it breaks no scene claim, plausibility `ordinary`, verdict `concept`.
            - `$CoSpin`: replaces `quadrant-turn`. The quadrant at `anchor` holds the input, and each step around the arrangement in `sense` turns the input a further quarter turn in that same sense, as in 7fe24cdd. It is undefined on a non-square input. It fails Fit at train0 for every anchor and sense.
            - `$MirrorFlip`: replaces `quadrant-turn`. The quadrant at `anchor` holds the input, and each other quadrant flips it along every axis on which that quadrant sits away from the anchor, as in 67e8384a. It fails Fit at train0 for every anchor. At anchor `DIAG_BR`, its top-right quadrant is the top-bottom flip, and the pair's is the clockwise turn.
        - `quadrant-repeat`: a choice point under the concept branch of `arrangement-grain`
            - `concept`: each quadrant repeats its own turn `copies` times on each axis
            - `$WholeRepeat`: replaces `quadrant-repeat`. The 2 × 2 arrangement of the four turns repeats `copies` times on each axis as a whole. It fails Fit at train0: in train0 output row 0, cols 3–5 hold the top-left turn again (`1 5 8`), and this branch puts the top-right turn there.
- `quadrant-transform-source` & `quadrant-repeat`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `copies` derived from the input's side, such as `side` − 1: no proposer, solver header or probe reading gives it. Every input has side 3, so the pairs give no evidence for one function of the side over another.
- `quadrant_transform` derived by the `TileD4` proposer as a `@derive` branch: that proposer reads `ex_out`, so on an input alone it gives no value and the branch is undefined on every input. It is the determination of the stored table.
- Reflections in place of turns in any quadrant: no non-identity D4 element fixes train0's input, so each quadrant's element is unique, and the pairs give the four turns.
- A claim on colors, such as the background `8`: the program reads no color, and each cell keeps its color under the D4 elements.

## Tickets filed
- 10-624_task_cf5fd0ad_analyze.md
- 10-625_task_cf5fd0ad_analyze.md
- 10-626_task_cf5fd0ad_analyze.md
