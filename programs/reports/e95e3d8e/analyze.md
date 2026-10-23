# e95e3d8e

## Concept
- The concept fits every pair. Its per-axis periods are 5, 3, 7 and 8 on train0, train1, train2 and test0, and on each pair the filled grid is the expected output.
- As the generator applies it, the rule is this: each hole cell takes the color that the generator's tile has at that cell's place. The concept's period, the least shift on each axis that no pair of surviving cells contradicts, approximates the tile's period. That approximation is wrong where the holes hide every cell that shows the true period.
    - `hidden-tile-color`: a 3-by-3 hole covers every cell of color 4 in a 5-by-5 wallpaper with period 2. Every case fills the hole with 3. Plausibility `borderline`, verdict `other`. It breaks the invariant of the inputs that each tile color shows outside the holes. It breaks no scene claim, because under the period 1 that the concept finds, every class shows.
- On 3000 random 22-by-22 inputs built like the pairs (one diagonal-symmetric square tile with period 3 to 8, and 2 to 5 rectangular holes up to 6 by 6), the concept gave the uncovered tiling every time. On those inputs `$IsometryOrbits` and `$ModalClass` never parted from the concept.

## Choice points
- `counterpart-kind`
    - `concept`: the hole cell takes its color from the cells that the periods relate to it. Each point below exists only with this branch.
        - `period-source`
            - `concept`: each axis's period is derived on each input, as the least shift that no pair of surviving cells contradicts.
            - `$StoredPeriod`: replaces `periodic-tiling`'s per-input period with stored parameters `period_v` and `period_h`. It fails Fit at train1, because train0 needs 5 and train1 needs 3.
            - `periods=Period`: derives each axis's period from the whole input, with the holes counted as content. On every input the holes contradict each shorter shift, so it gives 22 (21 on train2), and each hole cell's class holds no surviving cell. It fails Fit at train0.
        - `period-shape`
            - `concept`: each axis has its own period.
            - `$SquarePeriod` (29ec7d0e): replaces `periodic-tiling` with one period that both axes share, which is the least shift that no surviving pair contradicts on either axis. It is undefined where a hole cell's class under that period holds no surviving cell, or holds two colors. It fits every pair.
                - Witness `unequal-periods`, at the stored assignment, breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks these invariants of the inputs: every tile is square, and every grid is 22 by 22. `$SquarePeriod` is defined on it and copies 1 into (0,2), where the concept restores 2.
        - `fill-source`
            - `concept`: the cells of the hole cell's period class.
            - `$IsometryOrbits` (0dfd9992): adds the claim that the period classes merge under each D4 transform, with a translation modulo the periods, that some pair of surviving classes witnesses and none contradicts. On every input of this task, the one such transform is the main-diagonal reflection. It is undefined where a hole cell's orbit holds no surviving cell, or holds two colors. It fits every pair.
                - Witness `single-copy-cell`, at the stored assignment, breaks `every-residue-visible`. Plausibility `variant`, verdict `$IsometryOrbits`. It breaks this invariant of the inputs: every grid is 22 by 22, so each tile cell shows at least twice on each axis. The concept is undefined on it. `$IsometryOrbits` fills (3,2) from its diagonal mirror class, which gives the tile's color.
            - `$LineFill`: replaces `fill-from-period` so that the hole cell's class is limited to the cells on its own line, along a stored axis `line_axis`. It fails Fit at test0 for both axis values. For example, along rows, (4,6) and (4,14) make up their whole class and both are holes.
        - `class-agreement`
            - `concept`: the class's surviving cells share one color, and the concept is undefined otherwise.
            - `$ModalClass` (135a2760): the hole cell takes the commonest color among its class's surviving cells, and the model is undefined on a tie. It fits every pair.
                - Witness `hidden-period-evidence`, at the stored assignment, breaks `periodic-tiling`: under the least uncontradicted shifts (2 and 2), one class holds both 1 and 4. Plausibility `borderline`, verdict `other`. It breaks these invariants of the inputs: the holes cover a small part of a 22-by-22 grid, and they leave the evidence of each period visible. The concept is undefined on it, `$ModalClass` fills 4, and the tile's period is 4 rows.
    - `$DiagonalMirror`: replaces `fill-from-period` so that the hole cell takes the color of its mirror cell across the main diagonal, with no period. It fails Fit at train0: (1,1) and (2,2) are holes, and each is its own mirror.
- `hole-color-source`
    - `concept`: `hole_color` is stored as 0.
    - `$DerivedHoleColor`: replaces the stored `hole_color` with the color whose cells, read as holes, leave the least sum of the two periods. It is undefined where two colors tie and give different outputs. On every pair it gives 0. It fits every pair.
        - Witness `holes-of-another-color`, at the stored assignment, breaks `periodic-tiling` and `hole-patches`. Plausibility `borderline`, verdict `$DerivedHoleColor`. It breaks this invariant of the inputs: every hole is color 0. The concept returns the input unchanged, and `$DerivedHoleColor` restores the wallpaper.
    - `hole_color=RarestColor`: it fails Fit at train0, where the rarest color is 1.
    - `hole_color=SharedColor`: on one input it gives every color of that input. Every cell is then a hole, so the model is undefined. It fails Fit at train0.
    - `hole_color=DominantColor`: it gives 3 on train0, so the 0 cells stay. It fails Fit at train0.
- `hole-extent`
    - `concept`: the hole cells are filled.
    - `$HoleBoxFill`: each hole's bounding box is filled from the period classes. It fits every pair. It fails Equivalence, because it is equivalent to the concept, so it has no witness:
        1. A box cell outside a hole is in its own class, so wherever its class has one color, it already shows that color.
        2. The cells of one class form a rectangular lattice, and steps of one period join them. Under periods that no surviving pair contradicts, a path with no hole forces one color along it.
        3. So a class that holds two colors also holds a hole cell, and the concept is undefined there too.
- `period-source` & `period-shape`, `period-source` & `fill-source`, `period-source` & `class-agreement`, `period-shape` & `fill-source`, `period-shape` & `class-agreement`, `fill-source` & `class-agreement`, `counterpart-kind` & `hole-color-source`, `counterpart-kind` & `hole-extent`, `hole-color-source` & `hole-extent`, `period-source` & `hole-color-source`, `period-source` & `hole-extent`, `period-shape` & `hole-color-source`, `period-shape` & `hole-extent`, `fill-source` & `hole-color-source`, `fill-source` & `hole-extent`, `class-agreement` & `hole-color-source`, `class-agreement` & `hole-extent`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The tile is symmetric about its main diagonal, as a scene claim of the concept. A person fills a hole from the repeat. The symmetry enters only as an isometry that `$IsometryOrbits` reads from the surviving cells.
- The grid is 22 by 22. No rule reads the grid size.
- Derivations of `hole_color` by ChangedColor, VanishedColor, ChangedPairs, VanishedNewPairs, OutNewColor and AnyOutNewColor. These proposers read train outputs, and a `@derive` run on one input has no outputs.

## Tickets filed
- none
