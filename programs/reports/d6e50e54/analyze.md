# d6e50e54

## Concept
- Fits every pair. Each pair is separated tightly at the reach: in every input one mark lies at a distance below the block's side and lands on the block, and every other mark lies at the side's length or beyond and stops just outside it.
- No witness has the verdict `other`. The rule `mark-pull` has a relational form and is the rule as the generator applies it.
- In every input exactly one mark lies within reach, no two marks share a line on one side of the block, the block is square, and every mark lies in the block's rows or columns. Only the last two are scene claims.

## Choice points
- `landing-selection`: which marks land on the block
    - `concept`: each mark whose distance is below the reach lands on the block
        - `reach`: what gives the reach a mark's distance is compared with
            - `concept`: the block's extent along the mark's line
            - `$ReachAcross`: replaces `mark-pull`'s reach with the block's extent along the side the mark faces; defined where the concept is. Fits every pair. Witness `rectangle-block`: breaks `one-square-block`, at the stored assignment, `variant`, verdict `concept`; it breaks the invariant that the block is square.
            - `$ReachMin`: replaces the reach with the shorter of the block's two extents; defined where the concept is. Fits every pair. Witness `rectangle-block`, as for `$ReachAcross`.
            - `$ReachMax`: replaces the reach with the longer of the block's two extents; defined where the concept is. Fits every pair. Witness `rectangle-block`, as for `$ReachAcross`.
            - `$ReachStored`: replaces the reach with a stored number of cells; defined where the concept is. Fails Fit: train1 needs the value 3 (a mark at 2 lands, a mark at 3 stops) and train2 needs 4 (a mark at 3 lands, a mark at 4 stops), so every value fails train1 or train2.
    - `$NearestLands`: replaces `mark-pull`'s test with "the mark is the nearest to the block of all marks, ties included"; defined where the concept is. Fits every pair. Witness `two-within-reach`: breaks no scene claim, `variant`, verdict `concept`; it breaks the invariant that exactly one mark lies within reach.
- `recolor-condition`: when the block takes `fill_color`
    - `concept`: always
    - `$RecolorWhenHit`: replaces `block-recolor` with "the block takes `fill_color` only when a mark lands on it, and keeps `block_color` otherwise"; defined where the concept is. Fits every pair. Witness `none-within-reach`: breaks no scene claim, `variant`, verdict `concept`; it breaks the invariant that exactly one mark lies within reach.
- `collision`: two marks that land on one cell
    - `concept`: they land together and show as one mark
    - `$Stack`: adds to `mark-pull` that marks on one line and one side rest in order of distance, each farther one on the next cell outward from the one before it when its own landing cell is taken; defined where the concept is. Fits every pair. Witness `same-line-pair`: breaks no scene claim, `variant`, verdict `$Stack`; it breaks the invariant that no two marks share a line on one side of the block.
    - `$CollideUndefined`: adds "undefined where two marks land on one cell"; undefined there. Fits every pair. Fails Subsumption: the concept's model gives its output wherever it is defined. Witness `same-line-pair`, on which it is undefined.
- `off-line-marks`: a mark in neither the block's rows nor its columns
    - `concept`: the model is undefined
    - `$OffLineStay`: replaces `marks-in-line` and adds "a mark in neither the block's rows nor its columns stays where it is"; defined on every input the concept is, and on those marks. Fits every pair. Witness `off-line-mark`: breaks `marks-in-line`, `borderline`, verdict `$OffLineStay`; it breaks the invariant that every mark lies in the block's rows or columns.
    - `$OffLineErase`: replaces `marks-in-line` and adds "such a mark clears to `bg`"; defined as `$OffLineStay` is. Fits every pair. Witness `off-line-mark`, as for `$OffLineStay`.
- `rest`: the cells no rule names
    - `concept`: `rest-kept`, each keeps its input color
    - `$RestCleared`: replaces `rest-kept` with "every other cell becomes `bg`"; defined where the concept is. Fits every pair. Witness `stray-cell`: breaks no scene claim, `borderline`, verdict `concept`; it breaks the invariant that every input holds only `bg`, `block_color` and `mark_color`.
- `bg`
    - `concept`: stored, 7
    - `bg=DominantColor`: derives `bg` as the commonest color of the input; on a tie it takes each tied color, and it is defined where the concept's model is defined at each color it gives. Fits every pair. Witness `bg=DominantColor`: breaks no scene claim, `variant`, verdict `concept`; it breaks the invariant that `bg` is the commonest color of every input.
- `mark_color`
    - `concept`: stored, 9
    - `mark_color=RarestColor`: derives `mark_color` as the rarest color of the input; undefined where that color is `block_color`. Fits every pair. Witness `mark_color=RarestColor`: breaks no scene claim, `variant`, verdict `concept`; it breaks the invariant that the marks are fewer than the block's cells.
    - `$MarkColorByShape`: derives `mark_color` as the color of the one-cell objects other than `bg`; undefined where those objects have more than one color. Fits every pair. Witness `mark-other-color`: breaks `single-cell-marks`, at the stored assignment, `variant`, verdict `$MarkColorByShape`; it breaks the invariant that the marks are of color 9.
- `block_color`
    - `concept`: stored, 1
    - `$BlockColorByShape`: derives `block_color` as the color of the one object of more than one cell other than `bg`; undefined where there is not exactly one such object. Fits every pair. Witness `block-other-color`: breaks `one-square-block`, at the stored assignment, `variant`, verdict `$BlockColorByShape`; it breaks the invariant that the block is of color 1.
- `landing-selection` & `recolor-condition`, `landing-selection` & `collision`, `landing-selection` & `off-line-marks`, `landing-selection` & `rest`, `landing-selection` & `bg`, `landing-selection` & `mark_color`, `landing-selection` & `block_color`, `reach` & `recolor-condition`, `reach` & `collision`, `reach` & `off-line-marks`, `reach` & `rest`, `reach` & `bg`, `reach` & `mark_color`, `reach` & `block_color`, `recolor-condition` & `collision`, `recolor-condition` & `off-line-marks`, `recolor-condition` & `rest`, `recolor-condition` & `bg`, `recolor-condition` & `mark_color`, `recolor-condition` & `block_color`, `collision` & `off-line-marks`, `collision` & `rest`, `collision` & `bg`, `collision` & `mark_color`, `collision` & `block_color`, `off-line-marks` & `rest`, `off-line-marks` & `bg`, `off-line-marks` & `mark_color`, `off-line-marks` & `block_color`, `rest` & `bg`, `rest` & `mark_color`, `rest` & `block_color`, `bg` & `mark_color`, `bg` & `block_color`, `mark_color` & `block_color`: the two branches' changes applied together
- `reach` stands under the concept branch of `landing-selection`: a case that takes `$NearestLands` and a non-concept branch of `reach` has `$NearestLands`'s model alone, as `$NearestLands` compares no distance with a reach.

## Open parameters
none

## Not formed
- A reach of the block's side plus a stored offset: the offset counts nothing the task has, so the claim has no relational form; offset 0 is the concept, and an offset of 1 fails train0 and an offset of -1 fails train2.
- A mark that touches the block staying outside it: no pair shows a touching mark, and nothing in the pairs or the concept singles out distance 1 from the other distances within reach.
- A mark off the block's rows and columns pulled diagonally to a corner: the pairs show only pulls along a row or a column, and give such a mark no side it faces and no landing cell.
- A derivation of `fill_color`: 2 is in no input, and every proposer that gives it reads the train outputs.
- A derivation of `block_color` by a proposer: on one input `SharedColor` gives all three colors, `DominantColor` gives 7 and `RarestColor` gives 9, `VanishedColor` and `ChangedColor` read the train outputs, and `CountRankAsc` and `CountRankDesc` give a rank for each color in place of one color.
- A derivation of `bg` or `mark_color` by `CountRankAsc` or `CountRankDesc`: they give a rank for each color in place of one color.

## Tickets filed
none
