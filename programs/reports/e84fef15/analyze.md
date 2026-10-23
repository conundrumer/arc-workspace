# e84fef15

## Concept
- Fits every pair. The full lines of 3 cut each input into 5 by 5 tiles, 5 on each axis; 24 tiles are one pattern, and the one other tile differs from it only at pattern marks that are 8 there: train0 tile (2,4) at (2,2), (3,0); train1 tile (2,1) at (0,2), (4,2), (4,4); train2 tile (4,2) at (0,2), (1,0), (2,1), (3,3); test tile (1,3) at (1,1), (1,2), (1,4).
- No witness has the verdict `other`.
- The rule as the generator applies it: the generator draws one tile, copies it into every cell of a lattice cut by lines of `divider`, sets some marks of one copy to `background`, and paints those marks `fill` in a copy of the tile. The rule `mark-lost` paints each cell where the damaged tile differs from the pattern, which on every input the generator produces is exactly the set of erased marks.

## Choice points
- `tile-cut`: how the grid is cut into tiles
    - `concept`: the runs between full lines of `divider` (`divided-grid`)
        - `divider`: the color of the dividing lines
            - `concept`: `divider` stored, 3
            - `$DividerFromLines`: replaces `divided-grid` with the divider derived as the one color that forms a full row or column; no parameter `divider`; undefined where no color or more than one color forms a full line. Fits every pair. Witness `divider-recolored`: train0 input with 3 recolored to 5; breaks `divided-grid`; at the stored assignment; `variant`, verdict `$DividerFromLines`; breaks the invariant that the lines are 3.
            - `divider=SharedColor`: replaces `divided-grid` with the divider derived as each color of the input; undefined on every input, since a color that forms no line leaves one tile and no damaged tile. Fails Fit at train0.
            - `divider=DominantColor`: replaces `divided-grid` with the divider derived as the commonest color, 8 on every pair; undefined where 8 forms no line. Fails Fit at train0.
            - `divider=RarestColor`: replaces `divided-grid` with the divider derived as the rarest color, 0 and 2 on train0; undefined where those form no line. Fails Fit at train0.
    - `$CutBySize`: replaces `divided-grid` with tiles of stored size `tile_size` (5) on each axis and a stored `gap` (1) between each two, read without the divider; undefined where an axis is no whole number of tiles and gaps, or where the cut tiles do not hold one pattern and one damaged tile. Fits every pair. Witness `divider-broken`: train0 input with (5,2) set to 8; breaks `divided-grid`; at the stored assignment; `borderline`, verdict `$CutBySize`; breaks the invariant that each divider line is full.
    - `$CutByCount`: replaces `divided-grid` with a stored `tile_count` (5) on each axis and a stored `gap` (1), read without the divider; undefined where an axis does not divide into that count. Fits every pair. Witness `divider-broken`, as for `$CutBySize`; verdict `$CutBySize`, which gives the same output.
- `damage-count`: how many tiles may differ
    - `concept`: exactly one tile differs from the pattern (`damaged-tile`)
    - `$Disagreement`: replaces `repeated-tile`, `damaged-tile`, `output-tile` and `mark-lost` with: each output cell takes the value every tile holds there, and `fill` where the tiles disagree; undefined where the tiles are unequal in size or agree at every cell. Fits every pair. Witness `two-damaged-tiles`: train0 input with tile (0,0) also losing its mark at (2,4); breaks `damaged-tile`; at the stored assignment; `variant`, verdict `$Disagreement`; breaks the invariant that one tile differs.
- `damage-kind`: which differing cells take `fill`
    - `concept`: each cell where the damaged tile differs from the pattern (`mark-lost`)
    - `$LostMarkOnly`: replaces `mark-lost` with: each cell where the pattern is not `background` and the damaged tile is `background` takes `fill`, and each other cell keeps the pattern; reads `background`, which moves from the scene parameters to the parameters. Fits every pair. Witness `added-mark`: train0 input with the damaged tile gaining a 2 at (1,1); breaks `damaged-tile`; at the stored assignment; `variant`, verdict `concept`; breaks the invariant that each differing cell is a lost mark.
        - `background`: the field color the branch reads
            - `concept`: `background` stored, 8
            - `background=DominantColor`: replaces the stored `background` with the commonest color of the input, 8 on every pair. Fits every pair. Witness `background=DominantColor`: train0 input with 8 recolored to 7; breaks `repeated-tile`; at the stored assignment; `variant`, verdict `background=DominantColor`; breaks the invariant that the field is 8.
- `fill`: the color of a lost mark
    - `concept`: `fill` stored, 1
    - `fill=OutNewColor`: replaces the stored `fill` with each color in every train output and no input; on an input alone, with no train output, it gives no single color. Fails Fit at train0.
    - `fill=AnyOutNewColor`: as `fill=OutNewColor`, with a color in some train output. Fails Fit at train0.
- `tile-cut` & `damage-count`, `tile-cut` & `damage-kind`, `tile-cut` & `fill`, `damage-count` & `fill`, `damage-kind` & `fill`, `divider` & `damage-count`, `divider` & `damage-kind`, `divider` & `fill`, `background` & `tile-cut`, `background` & `fill`, `divider` & `background`: the two branches' changes applied together
- `tile-cut` & `divider`: `divider` stands under the concept branch of `tile-cut`; the cuts by stored geometry read no divider, so a case of `$CutBySize` or `$CutByCount` with a non-concept `divider` branch is that cut's model alone
- `damage-count` & `damage-kind`: each cell where the tiles disagree takes `fill` when some tile is `background` there and the value most tiles hold there is not `background`, and otherwise the value most tiles hold there; each cell where the tiles agree takes that value
    - `$Disagreement` & `$LostMarkOnly` & `background=DominantColor`: the same model, with `background` the commonest color of the input

## Open parameters
- none

## Not formed
- The output as the damaged tile with its differing cells painted `fill`: equivalent to the concept, since every cell outside the painted ones is the same in the damaged tile and the pattern.
- The pattern as the per-cell commonest value in place of the commonest tile: under the concept's one damaged tile the two give one pattern, and under `$Disagreement` the pattern is not read, since every cell where the tiles disagree takes `fill`.
- The tiles cut at the input's period (6 on each axis): each period holds a divider line, which the output does not hold, so the cut needs the divider that `tile-cut` already reads.
- `divider` derived by proposers that read train outputs (VanishedColor, ChangedColor, UnchangedColor): on an input alone, with no train output, these give no color, or every color of the input, as `divider=SharedColor` does.
- `tile_size`, `tile_count` and `gap` derived by proposers: on an input alone, TileDim and TileCount give several values for each axis (29 at one tile among them), so the derived cut gives several outputs and fails Fit at train0; SepTileDim, SepTileCount and SepThickness read the separator lattice, which is the line cut of the concept branch of `tile-cut`.

## Tickets filed
- none
