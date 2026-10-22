# df978a02

## Concept
- Fits every pair (the `concept` row that `probe_branches.py` prints). No witness has the verdict `other`. Every rule has a relational form: the winner is picked by a count of cells, and the grown line's length is a count of shapes.
- The concept is undefined where no center cell parses, where two shapes tie for the most cells, where the grown line would leave the grid, and where an even number of tips is taken, because the line cannot then be centered.
- `four-pointers` was tightened while checking. In train0, the left `2` shape is not mirror-symmetric, so the claim states only that each shape's front line holds one tip cell on the center row or column.

## Choice points
- `winner`: which shape grows
    - `concept`: the shape with the most cells
    - `$WidestBack`: replaces the winner of `others-lose-tip` and `largest-grows-back` with the shape whose back line, the line of the shape farthest from the center, holds the most cells. It is undefined where two back lines tie. It fits every pair. Witness `widest-back`: the top shape has 13 cells and a 1-cell back, and the right shape has 9 cells and a 5-cell back. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$LargestBox`: replaces the winner with the shape of the largest bounding-box area. It fails Fit at train0: the left `2` box (42) beats the top `4` box (18).
    - `$LongestAxis`: replaces the winner with the shape that has the most cells on the center row or column. It fails Fit at train1: the top `4` (4 cells) beats the right `7` (3 cells).
- `bitten`: which shapes lose their tip
    - `concept`: every shape but the winner
    - `$AllLoseTip`: replaces `others-lose-tip` so that the winner loses its tip as well. It fails Fit at train0: the top `4` keeps (7,7).
- `bite`: what a bitten shape loses
    - `concept`: its tip cell
    - `$BiteFrontLine`: replaces `others-lose-tip` so that each bitten shape loses its whole front line, the line nearest the center. It is defined wherever the concept is. It fits every pair. Witness `flat-front`: the left shape's front column holds (7,5) and (8,5). It breaks `four-pointers` (the front line holds a single cell). Plausibility `borderline`, verdict `concept`. It breaks the invariant that every shape's front line holds one cell.
- `grow-count`: how many cells the winner gains
    - `concept`: one per tip taken
    - `grow_width=stored`: replaces `largest-grows-back` with a stored line length, parameter `grow_width`: 3. It is defined where the concept is, and also where an even number of tips is taken. It fits every pair. Witness `grow_width=stored`, at the stored assignment: only a top shape and a bottom shape, so one tip is taken, and the concept grows one cell where this branch grows three. It breaks `four-pointers`. Plausibility `borderline`, verdict `concept`. It breaks the invariant that every input has four shapes, one on each side.
- `grow-anchor`: where the grown line goes
    - `concept`: one step beyond the winner's far edge
    - `$GrowPastAxisEnd`: replaces `largest-grows-back` so the line goes one step beyond the winner's farthest cell on the center row or column. It fits every pair. Witness `notched-back`: the winner's back row has a gap at the axis column (3,7). The concept lays row 2, cols 6–8, and this branch fills row 3, cols 6–8. It breaks no scene claim (in train0 the `2` back is off the axis as well). Plausibility `ordinary`, verdict `concept`.
- `background`
    - `concept`: stored, 8
    - `background=DominantColor`: derives `background` as the commonest color of the input. It is undefined nowhere the concept is defined at 8. It fits every pair. Witness `background=DominantColor`: the test input with the field recolored to 0. It breaks `four-pointers` (the field is not `background` 8). At the stored assignment the concept finds no center and is undefined. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that every input's field is 8.
- `winner` & `bitten`, `winner` & `bite`, `winner` & `grow-count`, `winner` & `grow-anchor`, `winner` & `background`, `bitten` & `bite`, `bitten` & `grow-count`, `bitten` & `grow-anchor`, `bitten` & `background`, `bite` & `grow-count`, `bite` & `grow-anchor`, `bite` & `background`, `grow-count` & `grow-anchor`, `grow-count` & `background`, `grow-anchor` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Winner by bounding-box breadth, by widest line, by depth along the axis, by perimeter, or by far-edge distance: each fails a train pair (`probe_winner.py`). Breadth and widest line fail train0, where the left `2` is 7 tall against the top `4`'s 3.
- Bitten shapes retreat by one cell: fails train1, where the left `6` loses (8,5) and its other cells stay in place.
- The winner grows along its axis, not across it: fails train0, where row 1 cols 6–8 is added.

## Tickets filed
- none
