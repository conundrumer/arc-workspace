# de493100

## Concept
- The concept case fits every pair (`probe_models.py`). In train2 the mask hides `train2 input rows 14–17, cols 0–1`, whose side-mirror images are off the grid (cols 30–31) or inside the mask (rows 14–17). The diagonal mirror fills those cells from `train2 input rows 0–1, cols 14–17`. A reading with the side mirrors alone therefore fails train2.
- In every input, the diagonal mirrors hold on the tiles off the quarter's diagonal and fail on the tiles along it (`probe_diagonal_map.py`). So the evidence determines `tile_groups` as `SYM_BOX` on tiles (0,0) and (1,1) and `SYM_D4` on tiles (0,1) and (1,0).
- No translation holds on the visible cells. Of the D4 transforms with an offset, only the mirrors about the picture's center lines hold on the whole grid (`probe_symmetries.py`).
- The generator's rule is this: the output is the content of the picture under the mask. The concept's `fill-from-mirror` approximates that rule, and it is undefined where a hidden cell has no visible image under its tile's group.
- `hidden-picture-corner`: the mask covers `rows 0–1, cols 0–1` of train0's picture. Under every mirror, each image of that corner is off the grid or inside the mask, so every reading is undefined there.
    - It breaks `mask-recoverable`.
    - Plausibility `foreign`. It breaks this invariant of the inputs: each masked cell has a visible image under its tile's group.
    - Verdict `other`, with the picture's corner as output:

        ```
        2 9
        5 5
        ```

## Choice points
- `tile-groups`: the mirrors that restore a hidden cell
    - `concept`: the stored per-tile groups of `tile_groups`, at `tile_size` 8
    - `$DiagonalFallback`: replaces `tiled-picture`, `diagonal-mirrors`, `mask-recoverable` and `fill-from-mirror`. A hidden cell takes the color of a visible side-mirror image. Where it has none, it takes the color of a visible image under the diagonal mirrors and turns, at any cell. It reads no `tile_size` or `tile_groups`. It is undefined where a hidden cell has no visible image, or where its images differ. It fits every pair.
        - Witness `hidden-diagonal-block-corner`: the mask covers `row 0, cols 1–3` of train0's picture. `$DiagonalFallback` fills (0,1) from (1,0) and gives `5 2 9`. Every other reading is undefined.
            - It breaks `mask-recoverable`.
            - Plausibility `borderline`. It breaks this invariant of the inputs: each masked cell has a visible image under its tile's group.
            - Verdict `other`, with the picture's content `9 2 9`.
    - `$DerivedTileGroups`: replaces `tiled-picture`. In each input, `tile_groups` is derived as the members of D4 about the picture's center that hold on the visible cells of each tile. It is undefined where a hidden cell has no visible image under its tile's derived group, or where its images differ. It fits every pair.
        - Witness `symmetric-diagonal-block`: the top-left diagonal tile of train0's picture is made to hold the diagonal mirrors, and the mask covers `row 0, cols 1–3`. `$DerivedTileGroups` and `$DiagonalFallback` give `9 2 9`. The stored groups give (0,1) no image.
            - It breaks `tiled-picture` and `mask-recoverable`.
            - Plausibility `variant`. It breaks this invariant of the inputs: the diagonal tiles fail the diagonal mirrors.
            - Verdict `$DerivedTileGroups`.
- `mirror-centers`: where the picture's center lines sit
    - `concept`: stored `picture_size` 32, with the crop at the bottom and right
    - `$FoundAxes`: replaces `square-picture`. On each axis, the center line is derived in each input. It is the mirror line with the most visible pairs, and no visible pair at that line disagrees. The tiles lie `picture_size` / 2 lines out from those lines. It is undefined where no such line exists, or where the row and col lines are at different distances from the grid's corner, which the diagonals need. It fits every pair.
        - Witness `shifted-picture`: train0's picture is cropped one line at the top and left as well, with the mask on the same cells of the picture. `$FoundAxes` gives the hidden content, and the readings at 32 are undefined.
            - It breaks `square-picture`.
            - Plausibility `variant`. It breaks this invariant of the inputs: the center lines sit between rows 15 and 16 and between cols 15 and 16.
            - Verdict `$FoundAxes`.
    - `picture_size=ConstInDim`: the proposer gives 30. It fails Fit at train0.
- `mask-color`: the color of the mask
    - `concept`: stored `mask_color` 7
    - `$MaskFromAsymmetry`: replaces `mask-block`. `mask_color` is derived as the one color that a cell of every side-mirror mismatch carries. It is undefined where the input has no mismatch, or where more than one color qualifies. It fits every pair.
        - Witness `recolored-mask`: in train0's input, the mask is recolored 0. `$MaskFromAsymmetry` and `$MaskByShape` give the hidden content. The readings at 7 find no mask and are undefined.
            - It breaks `mask-block`.
            - Plausibility `variant`. It breaks this invariant of the inputs: the mask is 7.
            - Verdict `$MaskFromAsymmetry`, which `$MaskByShape` shares.
    - `$MaskByShape`: replaces `mask-block`. `mask_color` is derived as the one color whose cells form one solid rectangle. It is undefined where no color qualifies, or where more than one does. It fits every pair.
        - Witness `recolored-mask`, as above, with verdict `$MaskByShape`.
        - Witness `centered-block-color`: in train0's picture, the center 2 × 2 block is recolored 0, a color that occurs nowhere else. `$MaskByShape` finds two solid-rectangle colors and is undefined, and every other reading gives the hidden content.
            - It breaks no scene claim.
            - Plausibility `borderline`. It breaks this invariant of the inputs: every color of the picture occurs at least 30 times.
            - Verdict `concept`.
    - `mask_color=RarestColor`: fails Fit at train0, where 5 (30 cells) is rarer than 7 (48 cells), and at train2.
- `tile-groups` & `mirror-centers`, `tile-groups` & `mask-color`, `mirror-centers` & `mask-color`: the two branches' changes applied together. Under `$FoundAxes` & `$MaskFromAsymmetry`, the color and the center lines are derived jointly: they are the color and the lines at which the cells outside that color mirror with no mismatch.

## Open parameters
- none

## Not formed
- The output as the whole repaired grid: every output has the extent of the mask's bounding box.
- A translation period (`Period`, the wallpaper readings of 0dfd9992 and 29ec7d0e): no translation holds on the visible cells of any input.
- The side mirrors alone: that is the value `SYM_BOX` at every tile of `tile_groups`, a value of the parameter, not a branch. Train2 rules it out.
- A group at a tile that leaves out one diagonal or one turn: that is a value of `tile_groups`, not a branch.
- Other tile sizes: they are values of `tile_size`, not branches (`probe_tile_sizes.py`). With the groups the inputs determine, size 4 refines the 2 × 2 table exactly and gives the same model. Sizes 1 and 2 fit the pairs. Their tiles at the grid's top-left corner keep members that no visible pair of cells tests there. A reader of the concept takes the 8 × 8 blocks the pictures show, so 1 and 2 are not open values. Size 16 fails train2.
- `mask_color` by `DominantColor`, `SharedColor`, `VanishedColor`, `OutNewColor` or `ChangedColor`: on one input with `ex_out` empty, these give a color that the input's 7 block does not carry, or every color of the input.
- `tile_size` by `TileDim` or `TileCount`: on a 30-wide input, these give several values at once (such as 8 beside 10 and 15). A program that puts each cell in one tile cannot read them.

## Tickets filed
- none
