# e8686506

## Concept
- The concept fits every pair, and each pair gives one output grid: the frame colors are {3} at train0, {1, 2} at train1 and {8} at test0, and the pieces cover the background cells of that box exactly one way (probe `work/task/e8686506/probe.py`).
- The search for frame colors and the exact cover have a relational form. Candidate frame sets are sets of colors, and the cover can be done by the elimination that CoverForcing does. No number is computed.
- No witness has the verdict `other`.
- At train0 the frame is two mirror halves, and the halves do not touch, not even at a corner. At train1 the frame has two colors. So the frame is found by color and not by connectivity.
- The pieces have to cover every background cell of the frame's bounding box. A cell outside the frame's outline also counts: at train1 the four box corners take the 5 cells, and at train0 the cells at output (3,0) and (3,4) take 4 cells.

## Choice points
- `frame-colors`
    - `concept`: the frame colors are the color set at which `exact-fit` holds, found by search (`find-frame`).
    - `$FrameMostCells`: replaces `find-frame`. The frame colors are the colors that have the most cells in the input, ties included. The branch is undefined where the other colors' pieces do not cover that box's background exactly. It fits every pair, because train1 ties 1 and 2 at 11 cells each.
        - Witness `dotted-rows`: two dotted rows, each of which covers the other's gaps. It breaks no scene claim. It stands at the stored assignment. Plausibility `foreign`, verdict `any`. It breaks the invariant that exactly one color set of each input meets `exact-fit`. At this witness, the concept gives both boxes, and `$FrameMostCells` gives only the box of the row of 3 cells, which has more cells.
        - A further witness, where this branch is undefined: train0 with its bottom frame row recolored 2. That frame has 10 cells of 3 and 4 cells of 2. The branch takes {3} alone, and no cover exists. The concept finds {2, 3} and gives train0's output with a bottom row of 2 2 6 2 2. Plausibility `ordinary`, verdict `concept`. The grid is `accent-frame` in `work/task/e8686506/witness_grids.json`.
    - `$FrameObject`: replaces `find-frame` and `frame`. The frame is the largest multicolor 8-connected object, as in 42f14c03. It fails Fit at train0: that object is one 7-cell half of the frame, and its box has 3 gaps for 18 piece cells.
- `hole-cells`
    - `concept`: the gaps are the background cells of the frame's bounding box (`exact-fit`).
    - `$HolesEnclosed`: replaces `exact-fit`. The gaps are the background cells of the box that no 4-connected walk from the grid edge reaches, as in 97a05b5b. It fails Fit at train0, where no background cell is enclosed and the probe gives no grid. It also fails at train1, where the box corners are open.
- `piece-parts`
    - `concept`: a piece is a 4-connected one-color part (`pieces`).
    - `$Pieces8`: replaces `pieces`. A piece is an 8-connected one-color part. It is undefined where no cover exists. It fits every pair, because no two piece cells in the evidence touch at a corner.
        - Witness `diagonal-piece`: two 4 cells touch at a corner beside a frame whose gaps are a diagonal pair and a lone corner cell. It breaks the scene claim `pieces`. It stands at the stored assignment. Plausibility `borderline`, verdict `$Pieces8`. It breaks the invariant that every piece touches no other non-background cell, not even at a corner. The concept gives three grids, and `$Pieces8` gives one.
    - `$PiecesColorClass`: replaces `pieces`. All cells of one non-frame color are one rigid piece, as in 681b3aeb. It fails Fit at train0: the three 4 cells, moved as one unit, fit no gap set.
- `output-frame`
    - `concept`: the output is the frame's bounding box, with the gaps filled (`crop`, `fill`).
    - `$InPlace`: replaces `crop`. The output keeps the input's frame, the pieces move into the gaps, and their old cells clear, as in 6a1e5592. It fails Fit at train0, where the output is 5×5 and the input is 13×13.
- `frame-colors` & `hole-cells`, `frame-colors` & `piece-parts`, `frame-colors` & `output-frame`, `hole-cells` & `piece-parts`, `hole-cells` & `output-frame`, `piece-parts` & `output-frame`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `piece_turns` at a value other than SYM_1: SYM_C4, SYM_D4 and SYM_TB fail Fit at train1. There, the turned T pieces 8 and 4 change places, and the turned 6 bars lie flat, which gives 7, 9 and 2 output grids. SYM_LR fits every pair, because every piece in the evidence is symmetric left to right. But a reader of "slide each piece, unturned" does not take a mirror-only reading, so SYM_LR is not an open value.
- Background as the color at a grid corner: no source gives it. The background changes between pairs (8, 3, 4), and the commonest color is the only derivation of it that the proposers give.
- A frame limited to cells inside its outline, such as the cells between two frame cells on a row: this is the hole rule that train1 rules out, because its four box corners lie outside every frame row's span and still take 5 cells.

## Tickets filed
- none
