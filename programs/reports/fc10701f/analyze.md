# fc10701f

## Concept
- It fits all four pairs (`work/task/fc10701f/check.py`, `work/task/fc10701f/probe.py`). Every rule has a relational form: the corridor is the cells between two boxes, and `stamp-gates` is lib `Between` keyed on the cross axis, limited to the corridor. So no rule approximates what the generator applies, and no witness has verdict `other`.
- What the pairs leave open: whether a gate needs both posts, how close the posts must stand, which line a post must share with the cell, whether the mover's own start cells count as passed, and how the mover lands on a target of another length. Three properties are settled: target cells take the mover, not the mark (train2 col 5, test row 11); gates beyond the target are not stamped (test rows 13–23); the start cells go to `background`.
- In every input, gates stand beside the target (train2, test) and never beside the mover. The concept sets no scene claim on this.

## Choice points
- `gate-sides`
    - `concept`: a corridor cell is stamped when a `gate` cell stands on each side of it in its cross line
    - `$EitherSide`: replaces `stamp-gates`: a `gate` cell on at least one side is enough. Parameters unchanged, and defined wherever the concept is. Fits every pair. Witness `one-sided-gate` (train1 with (5,5), (6,5) cleared). It breaks `gates`, the invariant that every gate cell beside the corridor has a mirror across it. Plausibility `borderline`, verdict `concept`.
- `gate-reach`
    - `concept`: the posts may stand at any distance along the cross line
        - `gate-axis`: this point stands here. Under `$AdjacentGate`, no gate cell can touch a corridor end along the motion axis, because the blocks are there. So the model of `$AdjacentGate & $AnyAxis` is `$AdjacentGate`'s alone.
            - `concept`: only the cross line is read
            - `$AnyAxis`: replaces `stamp-gates`: a `gate` cell on each side along either axis is enough (lib `Between` keyed on both axes). Parameters unchanged, and defined wherever the concept is. Fits every pair. Witness `gate-on-motion-line` (train2 with 0 at (7,2), (7,15)). It breaks `gates`, the invariant that no gate cell lies in a corridor line beyond a block. Plausibility `borderline`, verdict `concept`.
    - `$AdjacentGate`: replaces `stamp-gates`: the post cells must touch the corridor's sides (the line just outside the blocks' common span). Parameters unchanged, and defined wherever the concept is. Fits every pair. Witness `gate-off-corridor` (train1 with (3,3), (5,3) cleared). It breaks `gates`, the invariant that every gate's cells touch the corridor. Plausibility `borderline`, verdict `concept`.
- `stamp-region`
    - `concept`: only the corridor is stamped
    - `$StampStart`: replaces `stamp-gates`: the mover's start cells are stamped too, under the same test, and the stamp is applied after `vacate`. Parameters unchanged, and defined wherever the concept is. Fits every pair. Witness `gate-at-start` (train1 with 0 at (3,1), (5,1)). It breaks no scene claim. Plausibility `ordinary`, verdict `concept`: the block leaves that gate, it does not pass through it.
    - `$StampWholeLine`: replaces `stamp-gates`: gates along the blocks' whole line are stamped, beyond both blocks too. Fails Fit at test0: rows 13, 15, 17, 19, 23, cols 10–13 stay 6.
    - `$StampAllGates`: replaces `stamp-gates`: every cell between two `gate` cells in its line is stamped, inside the corridor or not. Fails Fit at train0: (4,4), (4,5), (4,8), (4,9) stay 6. It also fails at train2: (7,1), (8,1), (7,3), (8,3).
- `land-order`
    - `concept`: `land` paints over `stamp-gates`
    - `$MarkOverLand`: a stamped cell under the target takes `mark`. Fails Fit at train2, where (7,5), (8,5) are 7. It also fails at test0, where row 11 cols 10–13 are 7.
- `vacate`
    - `concept`: the start cells become `background`
    - `$KeepMover`: replaces `vacate`: the start cells keep the mover. Fails Fit at train0: rows 10–11, cols 6–7 are 6.
- `landing`
    - `concept`: the target's cells become `mover`
    - `$TranslateMover`: replaces `land`: the target cells become `background`, and the mover's shape moves along the axis until its leading edge is on the target's far edge. Parameters unchanged, and defined wherever the concept is. Fits every pair. Witness `longer-target` (train0 with 9 also at (0,6), (0,7)). It breaks `two-blocks`, the invariant that the two blocks are the same size. Plausibility `borderline`, verdict `concept`.
    - `$TranslateNear`: as `$TranslateMover`, but the mover's trailing edge lands on the target's near edge. Fits every pair. Witness `longer-target`, same claim, invariant, plausibility and verdict.
- `background`
    - `concept`: stored, 6
    - `background=DominantColor`: replaces the stored `background` with the input's commonest color. Undefined on an input whose top count is tied. Fits every pair. Witness `background=DominantColor` (train1 with 6 recolored 5), at the stored assignment. It breaks `two-blocks`, the invariant that every field is 6. Plausibility `variant`, verdict `background=DominantColor`.
    - `background=SharedColor`: gives 6, 0, 7 and 9 on every input. Fails Fit at train0.
- `mover`
    - `concept`: stored, 7
    - `mover=RarestColor`: on every input it gives both 7 and 9, which tie for the fewest cells. Fails Fit at train0.
- `target`
    - `concept`: stored, 9
    - `target=RarestColor`: gives 7 and 9. Fails Fit at train0.
- `mark`
    - `concept`: stored, 2
    - `mark=OutNewColor`: the run reads one input and no output, so it gives no single color. Fails Fit at train0.
    - `mark=AnyOutNewColor`: on one input with no output it gives no color, so the model is undefined there. Fails Fit at train0.
- `gate`
    - `concept`: stored, 0
    - `gate=SharedColor`: gives 6, 0, 7 and 9. Fails Fit at train0.
- `gate-sides` & `gate-reach`, `gate-sides` & `gate-axis`, `gate-sides` & `stamp-region`, `gate-sides` & `landing`, `gate-sides` & `background`, `gate-reach` & `stamp-region`, `gate-reach` & `landing`, `gate-reach` & `background`, `gate-axis` & `stamp-region`, `gate-axis` & `landing`, `gate-axis` & `background`, `stamp-region` & `landing`, `stamp-region` & `background`, `landing` & `background`: the two branches' changes applied together
- `land-order`, `vacate`, `mover`, `target`, `mark`, `gate`, and `$StampWholeLine`, `$StampAllGates`, `background=SharedColor`: each non-concept branch here fails Fit. So no case takes it, and it pairs with no model.

## Open parameters
- none

## Not formed
- A rule that picks the mover by position: the mover is at the bottom in train0, left in train1, right in train2 and top in test0, and it moves up, right, left and down. Only its color separates it from the target.
- Derivations by VanishedColor, ChangedColor, UnchangedColor, ChangedPairs and VanishedNewPairs: each compares an input with its output. A `@derive` run has no output, so on one input each gives every input color or none. That is the failure `mark=OutNewColor` shows, at train0.
- A corridor across unequal spans (blocks offset across the axis): it is undefined under the concept and under every branch, and the pairs have no such input to separate any reading.

## Tickets filed
- none
