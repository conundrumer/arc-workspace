# ddf7fa4f

## Concept
- Fits every pair (`probe.py`). No witness has the verdict `other`. The rule `recolor-by-marker` has a relational form: a block's span along the marker line is the interval of its columns, and a marker falls in it or not, so the concept file's rule is the rule as the generator applies it.
- The concept is undefined on a block whose span holds no marker or more than one. `$KeepUnmarked` and `$NearestMarker` each give the concept's output wherever the concept is defined, so the concept's model is subsumed by each of them. The concept case is exempt from Subsumption.
- A 4-connected block's columns form an interval with a cell in every column, so a marker's column meets a block exactly when the marker falls in the block's span. A reading of the rule as a ray down the marker's column that meets every block on it is therefore the concept itself, and only the ray that stops at the first block (`$FirstHit`) is a branch.

## Choice points
- `matching`: how a block is paired with a marker
    - `concept`: by position, the marker's place along the marker line against the block's span
    - `$Rank`: replaces `recolor-by-marker`; the blocks, ordered by the edge of their span that `rank-edge` gives, pair one to one with the markers, ordered along the marker line; parameter `rank-edge`, left or right, and the case runs both values; undefined where the block count and the marker count differ, or where two markers share a place on the line or two blocks share a ranking edge, or where the two values give different outputs (`shadowed-marker`). Fits every pair. Witness `two-blocks-one-marker`: breaks `one-marker-per-block`; stored assignment; plausibility `borderline`; verdict `concept`; breaks the invariant that each marker stands over exactly one block and each block's span holds exactly one marker.
    - `reach`: under `concept` of `matching`, which blocks a marker reaches
        - `concept`: every block whose span holds the marker
        - `$FirstHit`: replaces `recolor-by-marker`; each marker paints the first block its column meets going away from the marker line, and a block met by two markers' columns is undefined; no parameter of its own. Fits every pair. Witness `shadowed-marker`: breaks `one-marker-per-block`; stored assignment; plausibility `borderline`; verdict `$FirstHit`; breaks the invariant that each block's span holds exactly one marker.
    - `unmarked-block`: under `concept` of `matching`, what a block that no marker reaches takes
        - `concept`: nothing; the model is undefined on that input
        - `$KeepUnmarked`: adds a rule that the block keeps `block-color`; no parameter of its own. Fits every pair. Witness `marker-beside-block`: breaks `one-marker-per-block`; stored assignment; plausibility `borderline`; verdict `$NearestMarker`; breaks the invariant that each block's span holds exactly one marker.
        - `$NearestMarker`: adds a rule that the block takes the color of the marker nearest its span along the marker line, and is undefined where two markers tie; no parameter of its own. Fits every pair. Witness `marker-beside-block`: breaks `one-marker-per-block`; stored assignment; plausibility `borderline`; verdict `$NearestMarker`; breaks the invariant that each block's span holds exactly one marker.
- `connectivity`: the adjacency that joins block cells into one block
    - `concept`: 4-adjacency
    - `$Adj8`: replaces `blocks` with 8-connected components; no parameter of its own. Fails Fit at train2: the blocks at train2 input rows 2–4, cols 1–2 and rows 5–7, cols 3–5 touch at (4,2), (5,3) and join, and the joined span holds the 1 and 6 markers.
- `marker-source`: which cells are markers
    - `concept`: the cells of the marker line of colors other than `bg` and `block-color`
    - `$MarkersAnywhere`: replaces `marker-line` and `recolor-by-marker`; every cell of a color other than `bg` and `block-color`, wherever it lies, is a marker at its place along the marker line's axis; undefined where a block's span holds two such cells. Fits every pair. Witness `marker-in-field`: breaks `marker-line` and `one-marker-per-block`; stored assignment; plausibility `borderline`; verdict `$MarkersAnywhere`; breaks the invariant that every marker lies in the top row.
- `fill-color`: the color a block takes from its marker
    - `concept`: the marker's own color
    - `$StoredColorMap`: replaces `recolor-by-marker`; a stored lookup table from marker color to fill color, the value the program derives as the identity; undefined at a marker color the table has no key for. Fails Fit at test0: its marker colors 3 and 9 are keys of no train pair (Unseen key).
- `bg`
    - `concept`: stored, 0
    - `bg=DominantColor`: derives `bg` as the commonest color of the input; undefined where two colors tie. Fits every pair. Witness `bg=DominantColor`: breaks `marker-line` (the line holds 3 between the markers, not `bg` 0); stored assignment; plausibility `variant`; verdict `bg=DominantColor`; breaks the invariant that the background is 0.
- `block-cells`: which cells form the blocks
    - `concept`: the cells of the stored `block-color`, 5
    - `$BlockColorFromField`: derives `block-color` as the commonest color other than `bg`; undefined where two colors tie. Fits every pair. Witness `block-color-permuted`: breaks `blocks` (no block is 5); stored assignment; plausibility `variant`; verdict `$AnyBlockColor`, whose output this branch gives as well; breaks the invariant that the blocks are 5. It differs from `$AnyBlockColor` on a field with blocks of two colors, where it recolors only the commoner color's blocks.
    - `$AnyBlockColor`: replaces `blocks`; the blocks are the one-color 4-connected components, of any color other than `bg`, off the marker line, and `block-color` is dropped. Fits every pair. Witness `block-color-permuted`: breaks `blocks`; stored assignment; plausibility `variant`; verdict `$AnyBlockColor`; breaks the invariant that the blocks are 5.
- `marker-edge`
    - `concept`: stored, top
    - `$EdgeFromMarkers`: derives `marker-edge` as the one edge whose line holds a cell of a color other than `bg` and `block-color` and whose next line holds only `bg`; undefined where no edge or more than one does. Fits every pair. Witness `markers-on-right-edge`: breaks `marker-line` (the top row holds no marker); stored assignment; plausibility `variant`; verdict `$EdgeFromMarkers`; breaks the invariant that the markers lie in the top row.
- `matching` & `connectivity`, `matching` & `marker-source`, `matching` & `fill-color`, `matching` & `bg`, `matching` & `block-cells`, `matching` & `marker-edge`, `reach` & `unmarked-block`, `reach` & `connectivity`, `reach` & `marker-source`, `reach` & `fill-color`, `reach` & `bg`, `reach` & `block-cells`, `reach` & `marker-edge`, `unmarked-block` & `connectivity`, `unmarked-block` & `marker-source`, `unmarked-block` & `fill-color`, `unmarked-block` & `bg`, `unmarked-block` & `block-cells`, `unmarked-block` & `marker-edge`, `connectivity` & `marker-source`, `connectivity` & `fill-color`, `connectivity` & `bg`, `connectivity` & `block-cells`, `connectivity` & `marker-edge`, `marker-source` & `fill-color`, `marker-source` & `bg`, `marker-source` & `marker-edge`, `fill-color` & `bg`, `fill-color` & `block-cells`, `fill-color` & `marker-edge`, `bg` & `block-cells`, `bg` & `marker-edge`, `block-cells` & `marker-edge`: the two branches' changes applied together
- `marker-source` & `block-cells`: with `$BlockColorFromField`, the two branches' changes applied together
    - `$MarkersAnywhere` & `$AnyBlockColor`: no block color tells markers from blocks off the marker line, so the markers are the cells of the marker line other than `bg` and the single-cell components of colors other than `bg` elsewhere, and the blocks are the other components off the marker line

## Open parameters
- none

## Not formed
- Recoloring cell by cell, each cell taking the color of the marker in its column or nearest its column: every pair's output recolors whole blocks, cells under no marker's column included (train0 output (2,4)), so no reading of the pairs takes this.
- Pairing a block with the marker nearest its center: a center is a number that counts nothing the task has, so the claim has no relational form; on spans that hold one marker, `$NearestMarker` gives the same pairing.
- Pairing blocks with markers by block size: train0's blocks by cell count (9, 10, 16) pair with the markers at cols 9, 2, 5, which no order of the marker line gives, and the order differs in train1, so it is no reading of the pairs.
- Changing or removing the markers: every pair's output keeps the marker line as the input has it, and no reading changes it.
- A block whose span holds two markers: no reading of the pairs gives such a block a color, apart from `$FirstHit` and `$Rank`, which pair it by other means.

## Tickets filed
- `10-873_task_ddf7fa4f_analyze.md`
