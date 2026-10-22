# b0722778

## Concept
- Fits every pair, train and test, at `background` 0 and `read-from` L. The task is a nested task: each band is an inner task whose demonstrated pair, the sample and its image, selects a change from a catalog, and the query is the object left to complete. The catalog has three kinds of change: a recoloring (the cell-by-cell color map), a mirror across a vertical or horizontal axis, and a turn (a quarter turn either way, or a half turn). On an odd-cell block an axis mirror and a quarter turn give one image, so a priority among the kinds is part of the model: a recoloring when the map is a function, else an axis mirror, else a turn. train0 band at rows 9–10 and train1 band at rows 0–1 fix mirror before turn: the query there has the odd cell at another corner, and the two kinds disagree on it. On a stripes block a quarter turn and a diagonal mirror give one image, and no pair separates them, since every stripes demonstration has a stripes query. The blocks are found as the 4-connected components of non-`background` cells, grouped into bands by their rows and ordered from `read-from`; the scene sizes (`block-size`, `gap-1`, `gap-2`, `band-gap`) are scene parameters that no rule reads. No witness has verdict `other`, and no rule is an approximation.

## Choice points
- `block-location`: how the three blocks of a band are found
    - `concept`: the 4-connected components of non-`background` cells, grouped by rows; undefined where a component is not a solid square or a band has other than three
    - `$LatticeBlocks`: the blocks are read at stored positions: replaces `bands` and `three-blocks` by positions from `block-size`, `gap-1`, `gap-2` and `band-gap`, which become parameters; undefined where a position lies off the grid. Fits every pair. Witness `wide-query-gap`: the query three columns past the image; breaks `three-blocks`; variant; verdict concept.
        - `band-gap`: the gap between bands under `$LatticeBlocks`
            - `concept`: stored, 1
            - `band-gap=SepThickness`: derived as the separator thickness of a witnessed lattice on the input alone; undefined where the input has no lattice. Fits every pair. Witness `band-gap=SepThickness`: a one-band input, no lattice on either axis; breaks no scene claim; borderline, breaks the invariant that an input holds at least three bands; verdict concept.
        - `block-size`: the block extent under `$LatticeBlocks`
            - `concept`: stored, 2
            - `block-size=SepTileDim`: fails Fit at train0, where the derivation on that input alone gives 2 and 5 (row 5 is blank, so a 2-segment lattice of 5-row segments is witnessed as well).
            - `block-size=ConstOutDim`: fails Fit at every pair: the derivation reads `ex_out`, which a run on an input leaves empty, so it gives no value.
- `role-order`: which block is the sample, the image, and the query
    - `concept`: `read-from` stored, L: the blocks in order from that edge
    - `$QueryByGap`: `read-from` derived from the gaps: the query is the end block beside the wider gap, the image the middle block, the sample the other end; undefined where the two gaps are equal. Fits every pair. Witness `query-first`: the band runs query, image, sample from the left, with the wide gap beside the query; breaks `three-blocks`; variant, a mirrored variant task; verdict `$QueryByGap`.
- `background`: the blank color
    - `concept`: stored, 0
    - `background=DominantColor`: derived as the color with the most cells on the input alone. Fits every pair. Witness `background=DominantColor`: one band whose blocks hold nine cells of color 4 against six blank cells; breaks no scene claim; borderline, breaks the invariant that an input holds at least three bands; verdict concept.
    - `background=SharedColor`: fails Fit at every pair: on an input alone every color present is shared, so the derivation gives every color of the input.
- `change-priority`: which change is read when several fit the demonstration
    - `concept`: a recoloring when the cell-by-cell map is a function, else the axis mirror that fits, else the turn that fits
    - `$TurnFirst`: replaces `find-change`: the turn before the axis mirror. Fails Fit at train0 (band at rows 9–10: the clockwise turn gives `7 9 / 9 9` where the output holds `9 9 / 9 7`) and train1 (band at rows 0–1).
    - `$AnyFit`: replaces `find-change`: every fitting change applies, and the band is defined only where they agree on the query. Fails Fit at train0 and train1 on the same bands: the mirror and the turn disagree there.
    - `$RecolorLast`: replaces `find-change`: the axis mirror or turn first, a recoloring only where none fits. Fits every pair. Witness `stripes-swap`: a stripes block whose image swaps its two colors, with an odd-cell query of the same colors; breaks `image-of-sample` (a recoloring introduces colors the sample lacks); borderline, breaks the invariant that no demonstration is both a recoloring and a mirror; verdict `any`.
- `diagonal-mirrors`: where mirrors across the diagonals stand in the catalog
    - `concept`: nowhere; the stripes change is a quarter turn
    - `$DiagMirror`: replaces `image-of-sample` and `find-change`: the catalog is a recoloring and the four mirrors, the diagonal mirrors in place of the turns. Fits every pair. Witness `stripes-demo-odd-query`: stripes turned to vertical, with an odd-cell query; breaks no scene claim; ordinary; verdict concept.
    - `$DiagLast`: adds to `image-of-sample` and `find-change`: the diagonal mirrors after the turns. Fits every pair. On 2×2 two-color blocks it agrees with the concept, since every diagonal image of such a block is a turn's image. Witness `diagonal-mirror-3x3`: 3×3 blocks whose image is the sample across the main diagonal, which no axis mirror or turn gives, so the concept is undefined; breaks `image-of-sample` and `three-blocks` (block size); borderline, breaks the invariant that blocks are 2×2; verdict `$DiagLast`.
- `recolor-trigger`: when a demonstration is a recoloring
    - `concept`: when the cell-by-cell map is a function
    - `$NewColorRecolor`: replaces `find-change`'s recoloring condition: only when the image holds a color the sample lacks; otherwise the geometric changes are read, and the band is undefined where none fits. Fits every pair. Witness `odd-cell-swap`: an odd-cell block whose image swaps the two colors with the layout kept; breaks `image-of-sample`; borderline, same invariant as `stripes-swap`; verdict concept. On `stripes-swap` it gives `$RecolorLast`'s output.
- `composite-change`: whether a mirror or turn combines with a recoloring
    - `concept`: no; such a demonstration is undefined
    - `$Composite`: adds to `image-of-sample` and `find-change`: after the single changes, each axis mirror or turn followed by a recoloring, where the map from the moved sample to the image is a function. Fits every pair. Witness `flip-and-recolor`: an image that is the sample flipped top to bottom and recolored to new colors; breaks `image-of-sample`; borderline, breaks the invariant that a demonstration changes colors or layout and not both; verdict `$Composite`.
- `unmapped-query-color`: a recoloring band whose query holds a color outside the map
    - `concept`: undefined
    - `$IdentityOutside`: replaces `apply-change`'s recoloring: a color outside the map keeps itself. Fits every pair. Witness `unmapped-query-color`: a recoloring band whose query holds a color the sample lacks; breaks `image-of-sample` (the query of a recoloring band uses only the sample's colors); borderline, breaks that invariant; verdict `$IdentityOutside`.
- `result-reading`: what the band's result is
    - `concept`: the query under the demonstrated change
    - `$ImageInQueryColors`: replaces `apply-change`: the image's layout in the query's colors, the sample's colors paired with the query's by cell-count rank. Fails Fit at train0 (band at rows 9–10: the image `1 1 / 2 1` in the query's colors gives `9 9 / 7 9` where the output holds `9 9 / 9 7`).
- `block-location` & `role-order`, `block-location` & `background`, `block-location` & `change-priority`, `block-location` & `diagonal-mirrors`, `block-location` & `recolor-trigger`, `block-location` & `composite-change`, `block-location` & `unmapped-query-color`, `role-order` & `background`, `role-order` & `change-priority`, `role-order` & `diagonal-mirrors`, `role-order` & `recolor-trigger`, `role-order` & `composite-change`, `role-order` & `unmapped-query-color`, `background` & `change-priority`, `background` & `diagonal-mirrors`, `background` & `recolor-trigger`, `background` & `composite-change`, `background` & `unmapped-query-color`, `change-priority` & `diagonal-mirrors`, `change-priority` & `recolor-trigger`, `change-priority` & `composite-change`, `change-priority` & `unmapped-query-color`, `diagonal-mirrors` & `recolor-trigger`, `diagonal-mirrors` & `composite-change`, `diagonal-mirrors` & `unmapped-query-color`, `recolor-trigger` & `composite-change`, `recolor-trigger` & `unmapped-query-color`, `composite-change` & `unmapped-query-color`: the two branches' changes applied together. Under `$LatticeBlocks`, `$QueryByGap` reads the roles from the stored gap widths. `$TurnFirst` & `$DiagMirror` puts the diagonal mirrors before the axis mirrors, and `$RecolorLast` & `$NewColorRecolor` reads a recoloring last and only with a new color. Every pair with `result-reading` applies the changes together to a model that fails Fit.

## Open parameters
- none

## Not formed
- The output as the query column cropped from the input with each block replaced by its result: equivalent to `stack`, since the blank rows are `background` in both.
- The roles read from which pair of blocks a change takes onto the third: ambiguous on train0 band at rows 3–4, where the sample to the query is a recoloring as well as the sample to the image a turn, so the reading needs a tiebreak of its own; the role order is an orientation parameter.
- The change as any permutation of the block's cells: a 2×2 block with repeated colors fits many permutations, and a person reads mirrors and turns, not permutations.
- The recoloring read by cell-count rank (commonest to commonest): on a block whose layout is kept it agrees with the cell-by-cell map, and on stripes the ranks tie; a weaker form of the concept's map, not a reading of its own.
- `background=VanishedColor`, `ChangedColor`, `UnchangedColor`, `OutNewColor`: 0 is in every output, and the task changes shape, so these give no value.

## Tickets filed
- none
