# af24b4cc

## Concept
- The concept case fits every pair: the probe `probe.py` gives each train and test output from the dividers, the commonest color of each block counted over all its cells, and a stored border of width 1.
- Every claim has a relational form. Full lines of `bg` give the dividers (`DividerTiles`), and `Mode` gives the commonest color. No rule is approximated. The generator draws each block in one or two colors, and the commonest color fills 4 or more of the 6 cells, so `unique-mode` holds in every input.
- No witness with verdict `other` was found.
- Concept is undefined where a block has a tie (`Mode` keeps every tied color). No pair shows a tie.

## Choice points
- `bg`
    - `concept`: `bg` stored as 0
    - `bg=DominantColor`: `bg` derived as the commonest color of the input; undefined where two colors tie for commonest. Fits every pair. Witness `bg=DominantColor`: three solid 5×5 blocks of 5 outnumber the 0 cells, so the derived `bg` is 5, no line divides the input, and the output is a 3×3 grid of 5. Breaks `block-size` (blocks are 3×2 in every input). Plausibility `variant`, verdict `concept`.
    - `bg=SharedColor`: `bg` derived as each color of the input. Fails Fit at train0, because every color of the input becomes `bg`.
    - `bg=RarestColor`: `bg` derived as the rarest color of the input. Fails Fit at train0, because 8 and 9 tie as rarest there and neither is 0.
- `block-parse`
    - `concept`: the blocks are the tiles of a tiling, and each tile is one output cell at its tile row and column
        - `tiling-source`
            - `concept`: the tiling is cut by the full lines of `bg`
            - `tile_size=stored`: tiles stored as 3×2, with a 1-wide edge and gap; undefined where an input extent is not 1 + n·(size + 1). Fits every pair. Witness `tile_size=stored`: 3×5 blocks, which the stored 2-wide tiles cut into four columns, so the output has 4 columns where the dividers give 2. Breaks `block-size`. Plausibility `variant`, verdict `concept`.
            - `tile_count=stored`: tile count stored as 2 rows by 3 columns, with a 1-wide edge and gap, and the tile size derived from the input extent; undefined where the extent does not divide. Fits every pair. Witness `tile_count=stored`: three rows of 3×2 blocks, which the stored count cuts into two rows of 5-high tiles across a divider. Breaks `block-layout` (2 rows by 3 columns of blocks in every input). Plausibility `variant`, verdict `concept`.
        - `mode-domain`
            - `concept`: a block's commonest color counts all of the block's cells, `bg` included
            - `$NonBgMode`: a block's commonest color counts only its non-`bg` cells; undefined on a block with no non-`bg` cell. Fits every pair. Witness `sparse-block`: train0 with block (0,0) holding one 3 and five 0 cells (`train0 input (1,1)` = 3). The concept gives 0 there, and `$NonBgMode` gives 3. Breaks `no-bg-in-block` (no block cell is `bg` in any input). Plausibility `variant`, verdict `$NonBgMode`.
    - `$Components`: the blocks are the 4-adjacent components of non-`bg` cells. Each component is placed at the rank of its top row and the rank of its left column, and a slot with no component takes `bg`. Undefined where two components of different colors share a slot. Fits every pair. Witness `split-block`: train0 with block (0,0) holding 3 at `train0 input (1,1), (2,2)` and 0 elsewhere. The two cells touch only at a corner, so they are two components on different ranks, and the output grows to 5×6. Breaks `no-bg-in-block`. Plausibility `variant`, verdict `$NonBgMode`.
        - `adjacency`
            - `concept`: 4-adjacency
            - `$DiagonalJoin`: 8-adjacency (`Components8`). Fits every pair. Witness `split-block`: the two cells of 3 form one component, so the output is the 4×5 picture with 3 at block (0,0), which differs from the 5×6 output of `$Components`. Breaks `no-bg-in-block`. Plausibility `variant`, verdict `$NonBgMode`.
- `color-pick`
    - `concept`: the commonest color (`Mode`)
    - `$StrictMajority`: the color that holds more than half of the block's cells; undefined where no color does. Fits every pair. Fails Subsumption: wherever it is defined, it gives the concept's output. Witness `three-color-block`: train0 with block (0,0) = `3 3 / 8 2 / 3 8`. The concept gives 3, and `$StrictMajority` is undefined. Breaks `two-colors` (each block holds one or two colors). Plausibility `variant`, verdict `concept`.
    - `$LargestPiece`: the color of the block's largest 4-adjacent single-color piece; undefined where two colors tie. Fails Fit at train1: block (0,1) `5 5 / 3 3 / 5 5` has three pieces of 2 cells.
- `output-margin`
    - `concept`: `margin` stored as 1
    - `$InputMargin`: each side of the output border is as wide as the input's margin of full `bg` lines on that side. Fits every pair. Witness `wide-border`: train0 with a 2-wide border of 0, for which `$InputMargin` gives a 6×7 output with a 2-wide border. Breaks `block-grid` (a 1-wide `bg` line along every edge in every input). Plausibility `variant`, verdict `concept`.
- `output-extent`
    - `concept`: the output extent is the block layout plus the margins
    - `out_dims=stored`: output extent stored as 4×5; undefined where the block picture and its border do not fill exactly 4×5. Fits every pair. Fails Subsumption: wherever it is defined, it gives the concept's output. Witness `out_dims=stored`: two columns of 3×2 blocks, where the concept gives a 4×4 output and `out_dims=stored` is undefined. Breaks `block-layout`. Plausibility `variant`, verdict `concept`.
- `bg` & `block-parse`, `bg` & `tiling-source`, `bg` & `mode-domain`, `bg` & `adjacency`, `bg` & `color-pick`, `bg` & `output-margin`, `bg` & `output-extent`, `block-parse` & `color-pick`, `block-parse` & `output-margin`, `block-parse` & `output-extent`, `tiling-source` & `mode-domain`, `tiling-source` & `color-pick`, `tiling-source` & `output-margin`, `tiling-source` & `output-extent`, `mode-domain` & `color-pick`, `mode-domain` & `output-margin`, `mode-domain` & `output-extent`, `adjacency` & `color-pick`, `adjacency` & `output-margin`, `adjacency` & `output-extent`, `color-pick` & `output-margin`, `color-pick` & `output-extent`, `output-margin` & `output-extent`: the two branches' changes applied together
- `tiling-source` & `adjacency`, `mode-domain` & `adjacency`: no case takes a non-concept branch at both, because the two points stand under different branches of `block-parse`.
- `mode-domain` stands under the concept branch of `block-parse`, because `$Components` & `$NonBgMode` is the `$Components` model alone: a component holds no `bg` cell.

## Open parameters
- none

## Not formed
- A tiebreak for blocks with no unique commonest color: no source gives a tie reading. `Mode` keeps every tied color, and no pair shows a tie.
- A derivation of `bg` by `OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs` or `VanishedNewPairs`: each one compares inputs with outputs or reads aligned positions. A `@derive` run has no output, and the output of this task does not align with the input.
- An output border color stored apart from `bg`: in every variant task it is the input's `bg`, so it is a redundant value.
- Derivations of `margin` or of the tile values by `DimDiff`, `ConstOutDim`, `TileDim`, `TileCount`, `SepTileDim`, `SepTileCount` or `SepThickness`: the stored branches above state the tile and extent values these proposers give. `margin` (1) is not the output-to-input difference that `DimDiff` gives (5 on each axis).

## Tickets filed
- none
