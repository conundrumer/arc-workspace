# cfb2ce5a

## Concept
- Fits every pair, train and test, at `source_corner` TL, `background` 0 and `border` 1 (`probe.py`).
- No witness has the verdict `other`, and the rules have a relational form, so the concept file's rules approximate nothing.
- Every tile in the evidence is symmetric across its diagonal through TL. The scene claim `diagonal-symmetric-tile` records that, and because of it the mirrors and the quarter turns give one output on every pair.

## Choice points
- `copy-transform`
    - `concept`: each other quadrant takes the tile reflected across the midline or midlines that part it from the source quadrant (`mirror-into-quadrants`).
    - `$RotatedCopies`: replaces `mirror-into-quadrants`: each other quadrant takes the tile turned about the square's center by the quarter turns that bring the source quadrant onto it, and markers are read through the same turn. It is undefined where the concept is. It fits every pair. Witness `asymmetric-tile` (train0's input with (1,2) set to 2) breaks `diagonal-symmetric-tile`. Plausibility `borderline`, verdict `concept`. It breaks the invariant that every tile is symmetric across its diagonal through the source corner.
    - `$TranslatedCopies`: replaces `mirror-into-quadrants`: each other quadrant takes the tile shifted onto it, and markers are read through the same shift. It is undefined where one quadrant's markers disagree. It fails Fit at train0, where it is undefined: TR (1,8) and (4,5) both sit over tile color 1 and carry 8 and 3.
- `mapping-scope`
    - `concept`: each quadrant has its own tile-color-to-marker-color mapping (`recolor-by-marker`).
    - `$GlobalMapping`: replaces `recolor-by-marker`: one mapping, read from every quadrant's markers, recolors every copy. It is undefined where markers over one tile color disagree anywhere. It fails Fit at train0, where it is undefined: tile color 2 takes 8 in TR and 4 in BL.
- `unmarked-color`
    - `concept`: a tile color with no marker in a quadrant becomes `background` there (`unmarked-to-background`).
    - `$UnmarkedKeepsColor`: replaces `unmarked-to-background`: that tile color keeps its own color in the copy. It fails Fit at train0: in BR, tile color 1 has no marker and the output holds 0 where this branch gives 1.
- `square-location`
    - `concept`: the square is the grid inset by `border`, cut in half on each axis (`square-in-border`).
    - `$SquareFromContentBox`: replaces `square-in-border` and drops `border`: the square is the bounding box of the non-`background` cells. It is undefined where that box is not a square of even side, or where its quadrants' markers disagree. It fails Fit at train1, where the box is rows 1–6, cols 1–6 and quadrants of side 3 make the markers disagree.
    - `$SquareFromFullTile`: replaces `square-in-border` and drops `border`: the tile is the largest square of non-`background` cells at the `source_corner` corner of the non-`background` bounding box. The square has twice the tile's side, drawn from that corner. It is undefined where that square leaves the grid. It fits every pair. Witness `off-center-square` (train0's input with two background rows added below and two columns added to the right) breaks `square-in-border`. Plausibility `borderline`, verdict `$SquareFromFullTile`. It breaks the invariant that every input's square is the grid inset by one cell on each side.
- `source-corner`
    - `concept`: `source_corner` is stored (TL).
    - `$SourceFromFullQuadrant`: replaces the stored `source_corner` in `source-tile`: the source corner is the corner whose quadrant holds no `background` cell. It is undefined where not exactly one quadrant does. It fits every pair. Witness `tile-in-other-corner` (train0's input mirrored left to right) breaks `source-tile` at TL. Plausibility `variant`, verdict `$SourceFromFullQuadrant`. The concept is undefined on it.
- `background`
    - `concept`: `background` is stored (0).
    - `background=DominantColor`: `background` takes the commonest color of the input. It is undefined where two colors tie. It fits every pair. Witness `background=DominantColor` (train0's input with 0 recolored to 6) breaks `square-in-border` and `sparse-markers` at `background` 0. Plausibility `variant`, verdict `background=DominantColor`. The concept is undefined on it.
- `copy-transform` & `mapping-scope`, `copy-transform` & `unmarked-color`, `copy-transform` & `square-location`, `copy-transform` & `source-corner`, `copy-transform` & `background`, `mapping-scope` & `unmarked-color`, `mapping-scope` & `square-location`, `mapping-scope` & `source-corner`, `mapping-scope` & `background`, `unmarked-color` & `square-location`, `unmarked-color` & `source-corner`, `unmarked-color` & `background`, `square-location` & `background`, `source-corner` & `background`: the two branches' changes applied together
- `square-location` & `source-corner`: the two branches' changes applied together, with the full quadrant looked for in the square that the `square-location` branch gives
    - `$SquareFromFullTile` & `$SourceFromFullQuadrant`: the source corner is the corner of the non-`background` bounding box where a full square of non-`background` cells sits, such that the square of twice its side drawn from that corner stays in the grid and has no other full quadrant. That square is the square. The model is undefined where no corner or more than one corner qualifies.

## Open parameters
- none

## Not formed
- Markers read through a shift while copies mirror: in this task a marker shows what the copy's cell under it becomes, so no reading of the concept matches a marker to a different tile cell than the copy does. The probe shows this reading is undefined on every train input, because the markers disagree.
- A stored table of the D4 transform per quadrant: across the generator's tasks, each table agrees with the concept or with `$RotatedCopies` at one source corner, so it fails Equivalence. A table that mirrors into one quadrant and turns into another is no reading of the concept.
- `background` by the other Color proposers: on one input with `ex_out` empty, `SharedColor` and `VanishedColor` give every color of the input, and `RarestColor` gives a marker color. `OutNewColor`, `AnyOutNewColor`, `ChangedColor` and `UnchangedColor` give no value, so each fails Fit at train0.
- `border` by a proposer: no proposer gives an edge margin.
- `tile_size` as a parameter: it is half the side of the grid inset by `border`, a redundant value.

## Tickets filed
- none
