# ea959feb

## Concept
- Fits every pair (train0–2 and test0, `work/task/ea959feb/check_concept.py`). The smallest consistent axis periods are (6,6), (7,7), (8,4), (9,9). Mask color 1 is also a pattern color, so every 1 cell counts as unknown, and a phase class with no non-1 cell keeps 1, which is its pattern color in every pair.
- Rule as the generator applies it: the generator draws a doubly periodic pattern, then paints solid patches of 1 over it, and the output is the pattern. In the pattern, each column steps through one cyclic order of the colors down the rows, and each row's period is a palindrome. Where a patch covers every copy of a phase pair, the cells outside the patches no longer fix the color, so the concept's `restore-period` only approximates the generator's rule.
- Witness `fully-covered-phase`, verdict `other`: full-height strips over columns 7 and 16 cover every copy of the self-mirror column phase 7 of the test pattern. The concept, `$ColorCycle` and `$MirrorSymmetry` all leave those cells 1, and the generator's output is the pattern. It breaks `phase-uncovered`. Plausibility `borderline`. It breaks the invariant that every phase pair has an uncovered cell, and that every patch is a block 2–7 cells wide that does not span the grid.

## Choice points
- `vertical-structure`
    - `concept`: the pattern repeats down the rows with a period read off the non-mask cells (`periodic-pattern`, `restore-period`).
    - `$ColorCycle`: replaces `periodic-pattern` and `restore-period` on the axis in parameter `cycle_axis` (V) with `color-cycle`: each column steps through one cyclic order of all the input's colors, read off adjacent non-mask cells and completed through the mask color. A cell takes the step from a known cell of its column, or else of its column phase. Undefined where the non-mask cells admit no single cycle. Fits every pair. Witness `cycle-restores-covered-phase`: four 3x3 patches cover every copy of phases (4,7), (4,8), (5,7), (5,8) of the test pattern. The concept leaves 16 cells 1, `$MirrorSymmetry` leaves the 8 in column phase 7 at 1, and `$ColorCycle` restores the pattern. It breaks `phase-uncovered`. Plausibility `borderline`, verdict `$ColorCycle`. Invariant broken: every phase pair has an uncovered cell.
- `counterparts`
    - `concept`: a cell's counterparts are the cells its axis periods reach.
    - `$MirrorSymmetry`: adds to `restore-period` the row and column reflections, taken modulo the period, that some pair of known cells witnesses and none contradicts (the 0dfd9992 form). Undefined where the concept is undefined. Fits every pair, each with one column reflection. Witness `mirror-restores-covered-column`: full-height strips over columns 8 and 17 cover column phase 8. The concept and `$ColorCycle` leave them 1, and the mirror about column 7 restores them from column phase 6. It breaks `phase-uncovered`. Plausibility `borderline`, verdict `$MirrorSymmetry`. Invariant broken: every phase pair has an uncovered cell, and no patch spans the grid's height.
- `mask-color`
    - `concept`: `mask_color` stored, 1.
    - `mask_color=DominantColor`: derives `mask_color` as the input's commonest color, with every tied color counting as a mask color. Replaces nothing in the scene. Undefined where the periods it then finds are inconsistent. Fits every pair, where 1 has 110–161 cells against at most 84 for any other color. Witness `mask_color=DominantColor`: one 1x2 patch over the two 4 cells (3,2), (3,3) of the test pattern leaves 4 (67 cells) commoner than 1 (64). The derived mask is 4, so phases (3,2) and (3,3) fill with 1 at all 18 copies. Breaks no scene claim. Plausibility `borderline`, verdict `concept`. Invariant broken: every input has at least three patches of at least 9 cells each, and 1 is the commonest color.
    - `mask_color=SharedColor`: derives every color of the input as a mask color, so every cell is unknown. Fails Fit at train0.
    - `mask_color=RarestColor`: derives the input's rarest color, which is never 1, so the 1 patches read as pattern and no period is consistent. Fails Fit at train0.
- `period-source`
    - `concept`: the program derives each axis period per input.
    - `$StoredPeriods`: stores (pv, ph). Fails Fit: every vertical period that fits train0 is a multiple of 6 and every one that fits train1 is a multiple of 7, and no assignment fits all three train pairs.
- `vertical-structure` & `counterparts`, `vertical-structure` & `mask-color`, `counterparts` & `mask-color`, `period-source` & `vertical-structure`, `period-source` & `counterparts`, `period-source` & `mask-color`: the two branches' changes applied together. For example, `$ColorCycle & $MirrorSymmetry` restores the pattern on both `cycle-restores-covered-phase` and `mirror-restores-covered-column`.

## Open parameters
- none

## Not formed
- Mask cells found by shape (solid rectangles of 1, with pattern 1s kept as known): the pairs give no size or shape criterion, and pattern 1s touch the patches. The model gives the concept's output wherever its criterion is defined.
- Periods from the `Period` proposer: periods are derived by the program, not stored. The proposer's raw repeat test, with the patches in place, admits no short shift on any input, so it is the `$StoredPeriods` point's failure again.
- Vertical period equal to the color count: under `$ColorCycle` the vertical period is the cycle length, which is the color count, so this adds no other model.
- Off-axis lattice translations: no pair's pattern has a translation off the axes beyond the lattice of its axis periods.
- Any consistent multiple of the smallest periods: wherever every phase pair has a known cell, it gives the smallest periods' output.

## Tickets filed
- none
