# fcc82909

## Concept
- Fits every pair (train0–2, test0), checked by `work/task/fcc82909/probe.py pairs`. No witness has verdict `other`. The rule as the generator applies it is the same as `bar`: under each block, a bar in `bar_color`, as wide as the block's columns, with one row for each distinct color in the block. It starts at the row just below the block toward `direction`. The count is a count of the block's colors, so the rule has a relational form, and no approximation is used.
- The concept program finds blocks as 4-connected components of non-`background` cells. It paints the bar over whatever lies in its cells, and drops bar cells that fall outside the grid. Under the scene claims (`blocks` apart and square, `room-below` holding), every branch below gives the concept's output.

## Choice points
- `bar-height`
    - `concept`: the bar's row count is derived as the block's distinct color count
    - `bar_height=stored`: a stored table from distinct count to row count (here {2:2, 3:3, 4:4}) replaces the derivation in `bar`. Parameter `bar_height`. Undefined on a block whose count is not a key. Fits every pair, because test0's counts 2, 3, 4 are all train keys. Witness `bar_height=stored`: the test0 input at `bar_height` {2:2, 3:3, 4:5}. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
- `block-parse`
    - `concept`: blocks are 4-connected components of non-background cells
    - `$Corner_join`: blocks are 8-connected components, so blocks meeting at a corner join. This replaces the parse under `blocks`. Never undefined. Fits every pair. Witness `corner-touch`: two blocks meeting at one corner. It breaks scene claim `blocks` (blocks apart). Plausibility `borderline`, because every input's blocks sit apart. Verdict `concept`.
    - `$Square_blocks`: the non-background cells are tiled into `block_size`×`block_size` squares, each square a block. This replaces the parse under `blocks`, and the program reads `block_size` (2). Undefined where the cells do not tile into such squares. Fits every pair. Witness `side-touch`: two blocks sharing an edge. It breaks `blocks` (blocks apart). Plausibility `borderline`, because every input's blocks sit apart. Verdict `$Square_blocks`, since a person sees two squares, each with its own bar.
    - `$Column_bars`: each column of a block hangs its own bar below that column's lowest cell, with the block's distinct count as its height. This replaces `bar`. Never undefined. Fits every pair. Witness `column-bars`: an L-shaped 3-cell block. It breaks `blocks` (full squares). Plausibility `foreign`, because every block in every input is a full 2×2 square. Verdict `concept`.
- `bar-meets-block`
    - `concept`: bar cells take `bar_color` over any cell, a block's included
    - `$Bar_behind`: bar cells that land on a non-background cell keep that cell. This replaces `bar`. Never undefined. Fits every pair. Witness `bar-meets-block`: a 4-row bar whose right column runs into a lower block. It breaks `room-below`. Plausibility `borderline`, because no input's bar reaches another block. Verdict `$Bar_behind`.
    - `$Bar_stops`: the bar ends at the row before the first row where any of its columns meets a non-background cell. This replaces `bar`. Never undefined. Fits every pair. Witness `bar-meets-block`, as above: `borderline`, verdict `$Bar_behind`.
- `bar-leaves-grid`
    - `concept`: bar cells past the grid edge are dropped
    - `$Bar_must_fit`: adds the condition that every bar fit inside the grid. Undefined on an input whose bar would leave the grid. Fits every pair. Its model is subsumed by the concept's: wherever it is defined it gives the concept's output. So it fails Subsumption. Witness `bar-leaves-grid`: a 4-color block two rows above the bottom edge. It breaks `room-below`. Plausibility `borderline`, because every input's bars fit inside the grid. Verdict `concept`.
- `background`
    - `concept`: `background` stored as 0
    - `background=DominantColor`: `background` derived as the commonest color of the input. This replaces the stored value under `background`. Undefined where several colors tie for commonest. Fits every pair, because 0 is the commonest color of each input. Witness `background=DominantColor`: the 3×2 grid `5 5 / 5 5 / 0 0`. It breaks no scene claim. Plausibility `borderline`, because it breaks the input invariants that the grid is 10×10 and that background holds most cells. Verdict `concept`.
    - `background=SharedColor`: derived from one input, it gives every color of that input, so every cell is background and no bar is drawn. Fails Fit at train0.
    - `background=RarestColor`: gives 8 and 4 on train0, so the 0 cells become one block. Fails Fit at train0.
- `bar-color`
    - `concept`: `bar_color` stored as 3
    - `bar_color=OutNewColor`: derived from one input with `ex_out` empty, it gives no value, so the model is undefined on every input. Fails Fit at train0.
    - `bar_color=AnyOutNewColor`: likewise gives no value without outputs. Fails Fit at train0.
    - `bar_color=SharedColor`, `bar_color=DominantColor`, `bar_color=RarestColor`: each gives only colors present in the input, never 3. Fails Fit at train0.
- `bar-height` & `block-parse`, `bar-height` & `bar-meets-block`, `bar-height` & `bar-leaves-grid`, `bar-height` & `background`, `bar-height` & `bar-color`, `block-parse` & `bar-meets-block`, `block-parse` & `bar-leaves-grid`, `block-parse` & `background`, `block-parse` & `bar-color`, `bar-meets-block` & `bar-leaves-grid`, `bar-meets-block` & `background`, `bar-meets-block` & `bar-color`, `bar-leaves-grid` & `background`, `bar-leaves-grid` & `bar-color`, `background` & `bar-color`: the two branches' changes applied together. For `$Bar_stops` with `$Bar_must_fit`, the fit test reads the bar's full height before the stop.

## Open parameters
- none

## Not formed
- Height as the cell count less the repeated cells: this equals the distinct count on every block, so it is the same model.
- Height as the distinct count of the block's bottom row plus one: it gives 2 for train0's `8 4 / 7 7` block, whose bar has 3 rows. Fails every reading of train0.
- Derived `direction`: no proposer gives a Dir. The value is stored, and every pair puts the bar below.

## Tickets filed
- none
