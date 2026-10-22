# e40b9e2f

## Concept
- Fits every pair: the core is the 3x3 at rows 4-6, cols 3-5 in train0, the 2x2 at rows 4-5, cols 2-3 in train1, the 3x3 at rows 3-5, cols 3-5 in train2 and test0, and no image conflicts or leaves the grid.
- The rule as the generator applies it: the generator draws a whole pattern with four-fold rotational symmetry about a center, erases arm cells and never core cells, and pairs the input with the whole pattern. The concept's core, the largest solid square that `group` maps onto itself, approximates that center.
- On every erasure of the train patterns (keep the core, cut each arm orbit down to a nonempty subset; 224, 224 and 14 inputs), every fitting branch gives the generator's output.
- Witness `tied-cores`, verdict `other`: train1's input with 6 at (3,2) and (3,3). The 2x2 blocks of 6 at rows 3-4 and rows 4-5, cols 2-3 tie for the core, so the concept and every branch are undefined. The generator gives the whole pattern about (4.5, 2.5): `3 6 6 3 / 6 6 6 6 / 6 6 6 6 / 3 6 6 3` at rows 3-6, cols 1-4.
    - breaks `square-core`
    - plausibility `variant`; the invariant it breaks: no arm cell joins core-colored cells into a second square as large as the core

## Choice points
- `center`: how the turning center is found
    - `concept`: the center of the core, a square that the figure holds
        - `core-square`: which square is the core
            - `concept`: the largest solid square that each element of `group` maps onto itself
            - `$AnySolidCore`: replaces `square-core`; the core is the largest solid square, symmetric or not. It is undefined where the concept is, and also where the largest solid square ties or is not symmetric, because a non-symmetric square's own cells conflict under the turn. Fits every pair. Where it is defined, its square is the concept's core, so the concept subsumes it and it fails Subsumption.
                - witness `unsymmetric-square` (undefined there): a 2x2 of 6 with an L of 3 that makes a solid 3x3; plausibility `ordinary`, verdict `concept`
            - `$MirrorCore`: replaces `square-core`; the core is the largest solid square that every element of D4 maps onto itself, while the images stay under `group`. It is undefined where that square ties, and where the concept is undefined at its center. Fits every pair.
                - witness `chiral-core`: 16x16, a 4x4 pinwheel core and a solid 3x3 arm block of 1; `$MirrorCore` turns about the arm block
                - plausibility `borderline`, verdict `concept`; the invariants it breaks: 10x10 grids, a core of side 2 or 3 that mirrors map onto itself, arms of single cells
            - `$OpenCore`: replaces `square-core`; the core is the largest square that holds a figure cell and that `group` maps onto itself, `bg` cells included. It is undefined where that square ties, which happens on any input with two isolated figure cells. Fits every pair.
                - witness `sparse-square`: the 3x3 of field around the lone 2 at (6,3) is larger than the 2x2 of 1, so `$OpenCore` turns about (6,3)
                - plausibility `variant`, verdict `concept`; the invariant it breaks: every arm cell touches the rest of the figure at a side or a corner
        - `image-group`: which group gives the images
            - `concept`: the stored `group`
            - `$CoreStabilizer`: replaces `quarter-turn-completion`; the images are those under every element of D4 that maps the core onto itself. Fails Fit at train1: the 2x2 core of 6 is mirror-symmetric, and its mirror images paint 6 at (3,3), (4,1), (5,4) and (6,2).
    - `$MostAgreement`: replaces `square-core`; the center is the point, a cell or a corner where four cells meet, about which the most figure cells have a `group` image of the same color. It is undefined at a tie. Fits every pair.
        - witness `arm-agreement`: a one-color figure whose arm agrees more about (5,6) than the 2x2 core at rows 4-5, cols 5-6
        - plausibility `variant`, verdict `concept`; the invariant it breaks: the figure holds two colors
    - `$SmallestCompletion`: replaces `square-core`; the center is the one where the completion paints the fewest cells, over the centers where the images are consistent and in the grid. Fails Fit at train1: (4.5, 2.5) and (5, 2.5) tie.
    - `$FigureBoxCenter`: replaces `square-core`; the center is the center of the figure's bounding box. Fails Fit at train0: the box is rows 3-7, cols 3-6, centered at (5, 4.5).
    - `$OneColorCore`: replaces `square-core`; the core is the largest solid square of one color. Fails Fit at train0: the core there holds both 4 and 7, so the one-color squares are single cells that tie.
- `conflict`: an image that falls on a cell of another color
    - `concept`: undefined
    - `$InputWins`: replaces `consistent-images` in part; an image paints only a `bg` cell, and each input cell keeps its color. It is undefined where two images give one `bg` cell two colors, or fall off the grid. Fits every pair.
        - witness `conflicting-cell`: train2's input with 9 at (2,2) and (6,2) and 8 at (6,6); `$InputWins` returns the input
        - breaks `consistent-images`
        - plausibility `foreign`, verdict `$InputWins`; the invariant it breaks: the images of each input cell carry its color or fall on `bg`
- `off-grid`: an image that falls outside the grid
    - `concept`: undefined
    - `$ClipImages`: replaces `consistent-images` in part; an image outside the grid is dropped. It is undefined where images conflict. Fits every pair.
        - witness `image-off-grid`: an 8 core at rows 0-2, cols 3-5 and a 9 at (3,4), whose half turn falls on row -1
        - breaks `consistent-images`
        - plausibility `borderline`, verdict `$ClipImages`; the invariant it breaks: the whole pattern lies inside the grid
- `bg`
    - `concept`: stored, 0
    - `bg=DominantColor`: the commonest color of the input. It is undefined where two colors tie for the commonest. Fits every pair.
        - witness `bg=DominantColor`: a 4x4 grid where 5 outnumbers 0; the concept completes the ring of 5 around the 2x2 of 2, and the branch takes 5 as the field
        - plausibility `borderline`, verdict `concept`; the invariant it breaks: the field covers most of the grid
    - `bg=SharedColor`: each color in the input. Fails Fit at train0: on that input alone it gives 0, 4 and 7, so the figure is empty and there is no core.
- `center` & `conflict`, `center` & `off-grid`, `center` & `bg`, `conflict` & `off-grid`, `conflict` & `bg`, `off-grid` & `bg`, `core-square` & `image-group`, `core-square` & `conflict`, `core-square` & `off-grid`, `core-square` & `bg`, `image-group` & `conflict`, `image-group` & `off-grid`, `image-group` & `bg`: the two branches' changes applied together
    - `$AnySolidCore` & `$InputWins`: the asymmetric square's own conflicts are skipped, so this case is defined on `unsymmetric-square` and differs there from `$InputWins` alone

## Open parameters
- none

## Not formed
- the center at the centroid of the figure's cells: a mean of positions has no relational form
- other values of `group` (D4, the half turn, a mirror pair): values of a parameter that the pairs separate. Train1 rules out D4, and train0 rules out the half turn and every mirror group.
- a fixed order among the three turns where their images conflict: the task gives no order among them, and the conflict is the `conflict` point
- 4-adjacency against 8-adjacency for the figure: no claim reads connectivity

## Tickets filed
- none
