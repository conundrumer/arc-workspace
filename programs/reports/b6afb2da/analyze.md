# b6afb2da

## Concept
- The concept case fits every pair. It finds the 4-connected objects of `shape` cells, and gives each object cell its role by its place in the object's bounding box: a box corner takes `corner_color`, another cell on the box's border takes `edge_color`, and any other cell takes `interior_color`. Every other cell passes through.
- No witness has the verdict `other`.
- On the solid, separate rectangles the generator draws, the bounding box of an object is the object, so this reading is the rule as the generator applies it.

## Choice points
- `rectangle-cells`: which cells make up the rectangles
    - `concept`: the cells of color `shape`
    - `$AnyNonBackground`: every cell whose color is not `background`; reads `background` in place of `shape`; undefined on no input. Fits every pair. Witness `other-color-rectangle`: a 3×3 gray block and a 3×4 green block apart; the concept leaves the green block as it is, and the branch frames it too. It breaks `solid-rectangles` (all rectangles are `shape`), at the stored assignment. Plausibility `foreign`, verdict `any`; it breaks the invariant that every input holds only `background` and `shape`.
        - `object-color`: whether cells of different colors join one object
            - `concept`: every non-background cell joins its neighbors, whatever their colors
            - `$PerColorObjects`: a cell joins only neighbors of its own color; undefined on no input. Fits every pair. Witness `two-color-block`: a gray 3×3 block and a green 3×3 block share a side; `$AnyNonBackground` frames them as one 3×6 box, and the branch frames each. It breaks `solid-rectangles`, at the stored assignment. Plausibility `foreign`, verdict `$PerColorObjects`; it breaks the invariant that every input holds only `background` and `shape`.
        - `background` source
            - `concept`: stored
            - `background=<Proposer>`, for each proposer of a color (`SharedColor`, `DominantColor`, `RarestColor`, `VanishedColor`, `OutNewColor`, `AnyOutNewColor`, `ChangedColor`, `UnchangedColor`): fails Fit. On one input with `ex_out` empty, `DominantColor` gives 5 on train1 (54 cells of 5, 46 of 0), `RarestColor` gives 5 on train0, `SharedColor` gives both 0 and 5, and the others give nothing.
    - `shape` source
        - `concept`: stored
        - `shape=<Proposer>`, for each proposer of a color: fails Fit. On one input with `ex_out` empty, `RarestColor` gives 0 on train1, `DominantColor` gives 0 on train0, `SharedColor` gives both 0 and 5, and the others give nothing.
- `role-reading`: how a cell's role (corner, side, inside) is read
    - `concept`: by the cell's place in its object's bounding box
        - `object-adjacency`: which contacts join cells into one object
            - `concept`: 4-adjacency
            - `$Objects8`: 8-adjacency, so a corner contact joins two rectangles into one object; undefined on no input. Fits every pair. Witness `diagonal-contact`: two gray 3×3 blocks meet at one corner; the concept frames each, and the branch reads them by their joint 6×6 bounding box. It breaks `solid-rectangles` (no two touching), at the stored assignment. Plausibility `borderline`, verdict `concept`; it breaks the invariant that the rectangles of an input lie at least one line apart.
    - `$CellNeighbors`: by the cell's own 4-neighbors, with a cell past the grid edge counted as outside: a cell missing a `shape` neighbor on both axes takes `corner_color`, one missing a neighbor on one axis takes `edge_color`, and the others take `interior_color`; replaces `corner`, `edge` and `interior`; undefined on no input. Fits every pair. Witness `notched-block`: a gray 4×4 block lacks its bottom-right cell; the concept gives the two cells beside the notch `edge_color`, and the branch gives them `corner_color`. It breaks `solid-rectangles`, at the stored assignment. Plausibility `foreign`, verdict `$CellNeighbors`; it breaks the invariant that every object of an input is a solid rectangle.
        - `border-adjacency`: which missing neighbors put a non-corner cell on the border
            - `concept`: a missing 4-neighbor
            - `$Border8`: a missing 8-neighbor, so the cell diagonal to a notch takes `edge_color`; undefined on no input. Fits every pair. Witness `notched-block`: `$CellNeighbors` gives the cell at (3,3) `interior_color`, and the branch gives it `edge_color`. It breaks `solid-rectangles`, at the stored assignment. Plausibility `foreign`, verdict `$CellNeighbors`; it breaks the invariant that every object of an input is a solid rectangle.
        - `grid-edge`: how a cell past the grid edge counts
            - `concept`: outside the shape
            - `$EdgeInside`: inside the shape; undefined on no input. Fails Fit at train0: the rectangle at rows 5–9, cols 6–9 meets the grid edge, and the branch gives (9,9) `interior_color` where the output holds 1.
- `corner_color` source, `edge_color` source, `interior_color` source
    - `concept`: stored
    - `<param>=<Proposer>`, for each of the three parameters and each proposer of a color: fails Fit at train0. On one input with `ex_out` empty, every such proposer gives 0, 5, or nothing, and train0's output holds 1 at (2,1), 4 at (2,2) and 2 at (3,2).
- `rectangle-cells` & `role-reading`, `rectangle-cells` & `object-adjacency`, `rectangle-cells` & `border-adjacency`, `rectangle-cells` & `grid-edge`, `object-color` & `object-adjacency`, `object-color` & `border-adjacency`, `object-color` & `grid-edge`: the two branches' changes applied together
- `object-color` & `role-reading`: `$PerColorObjects` & `$CellNeighbors` read a cell's neighbors under `$CellNeighbors` and count a neighbor as present only when it is non-background and of the cell's own color.
- `object-adjacency` & `border-adjacency`, `object-adjacency` & `grid-edge`: no case takes both branches, since each point stands under a different branch of `role-reading`.

## Open parameters
- none

## Not formed
- A third role reading, where the border is the cells with a missing 8-neighbor and a corner is a border cell at which the border turns: the pairs give no sign of a corner rule other than a missing neighbor on both axes, and `$Border8` covers the 8-neighbor border.

## Tickets filed
- none
