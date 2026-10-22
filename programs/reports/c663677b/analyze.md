# c663677b

## Concept
- The concept fits every pair: on each input the shortest shift on each axis under which the unblanked cells agree is 8, every blanked cell's class under those periods holds an unblanked cell, and filling each blanked cell from its class gives each output.
- The generator draws a wallpaper and blanks patches of it with 0, and the output is the wallpaper it drew. The concept's rule gives that wallpaper on each input where `each-class-seen` holds, and each claim has a relational form.
- The concept case has no witness with verdict `other`.
- Every input also shows two regularities that the concept does not read. The tile is symmetric across its main diagonal through cell (0,0), and the hole cells, at most 84 of 729, are never more than 12% of an input. `$StoredMirror` reads the first. The witnesses of `$ObliqueLattice` and `$WitnessedMirror` break the second.

## Choice points
- `damage`: how a blanked cell is known
    - `concept`: a cell is blanked when it has the stored `hole_color`, 0
    - `hole_color=RarestColor`: the hole color is derived as the rarest color of the input alone, which replaces the stored value in `blanked-patches`. The model is undefined where two colors tie as rarest. It fails Fit at train1: the rarest color there is 2 (45 cells), so 2 is read as blank and 0 stays.
    - `hole_color=VanishedColor`: the hole color is derived with `ex_out` empty, which replaces the stored value in `blanked-patches`. On one input alone, that derivation gives every color of the input. Every cell is then blank, so the model is undefined on every input. It fails Fit at train0.
    - `hole_color=SharedColor`: the same replacement, and on one input alone this derivation also gives every color of the input. The model is undefined on every input. It fails Fit at train0.
    - `hole_color=ChangedColor`: the same replacement. With `ex_out` empty, this derivation gives no color, so the model is undefined on every input. It fails Fit at train0.
    - `hole_color=DominantColor`: the same replacement. This derivation gives the commonest color, 1 on train0, so 1 is read as blank and 0 stays. It fails Fit at train0.
    - `$HoleFromPeriod`: this branch replaces the stored value in `blanked-patches` with a derived one. The hole color is the one color whose cells, read as blank, give the tile of least area under the concept's period derivation. The model is undefined where two colors tie, or where no color leaves a period shorter than the grid. It fits every pair. Witness `other-hole-color`: the holes are 9 and no cell is 0. It breaks `blanked-patches` at the stored `hole_color` 0 and stands at the stored assignment. Plausibility `variant`. It breaks the invariant that the blanked cells are 0 in every input. Verdict `$HoleFromPeriod`.
    - `$ClassMode`: this branch replaces `blanked-patches` and `restore-pattern`, so no cell is known to be blank. The periods are the tile of least area, with fewer rows first on a tie, at which every class has one color on more than half its cells. Each cell takes that color. The model is undefined where no tile shorter than the grid gives every class such a majority. It fits every pair. Witness `sparse-dots`: it breaks no scene claim and stands at the stored assignment. Plausibility `variant`. It breaks the invariant that no color covers half of an input's cells (the largest share is 1 in train0, 345 of 729). Verdict `concept`.
- `repeat`: which cells a blanked cell takes its color from
    - `concept`: the cells of its class under the translation lattice
        - `period`: how the lattice is found
            - `concept`: on each axis, the shortest shift under which the unblanked cells agree
            - `period=stored`: the periods are stored, 8 on each axis, which replaces the derivation in `periodic-pattern`. The model is undefined where a blanked cell's class under the stored periods holds no unblanked cell or holds two colors. It fits every pair. Witness `period=stored`: it breaks no scene claim and stands at the stored assignment. Plausibility `variant`. It breaks the invariant that every input is 27×27 and repeats every 8 cells on each axis. Verdict `concept`.
                - `period`: how the stored periods are determined
                    - `concept`: stored
                    - `period=Period`: the periods are derived as the least shift under which the input, hole cells included, repeats on each axis. On train0 no such shift exists on either axis, so the model is undefined there. It fails Fit at train0.
            - `$ObliqueLattice`: this branch adds to `periodic-pattern`. The lattice also takes each shift shorter than the axis periods, in any direction, under which the unblanked cells agree and at least one pair of unblanked cells meets. The model is undefined where a blanked cell's class holds no unblanked cell. It fits every pair. Witness `oblique-stripes`: it breaks `each-class-seen`, since every cell of the class at (0,0) under the axis periods 5 is blank. It stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that the blanked cells cover at most 12% of an input (here 36 of 100). Verdict `$ObliqueLattice`.
        - `isometries`: which further cells join a class
            - `concept`: none, so translations alone relate cells
            - `$WitnessedMirror`: this branch adds to `restore-pattern`. Classes merge under each reflection or rotation of the tile on its torus, with a shift, that some two unblanked cells it pairs witness and that no two contradict. The model is undefined where a merged class holds no unblanked cell. It fits every pair. Witness `mirror-class-blank`: it breaks `each-class-seen` and stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that the blanked cells cover at most 12% of an input (here 16 of 36). Verdict `$WitnessedMirror`.
            - `$StoredMirror`: this branch adds a scene claim: the tile is symmetric across its main diagonal through cell (0,0). It also adds to `restore-pattern`: a stored isometry, `D4_DG` on the tile's torus, merges classes. The model is undefined where a merged class holds two colors or no unblanked cell, and where the two periods differ. It fits every pair. Witness `asymmetric-tile`: it breaks no scene claim of the concept case and stands at the stored assignment. Plausibility `variant`. It breaks the invariant that every input's tile is symmetric across its main diagonal through cell (0,0). Verdict `concept`.
    - `$MirrorOnly`: this branch replaces `periodic-pattern` and `restore-pattern`. The grid is symmetric across its main diagonal, and a blanked cell takes its mirror cell's color. The model is undefined on a grid that is not square, and where a blanked cell's mirror cell is blanked. It fails Fit at train0: cell (3,3) lies on the diagonal and is blanked.
- `damage` & `period`, `damage` & `isometries`, `period` & `isometries`: the two branches' changes applied together. `$ClassMode` takes the majority within the classes of the stored periods, of the oblique lattice, or of the merged classes. Under `period=stored`, `$HoleFromPeriod` takes the color whose cells, read as blank, leave the unblanked cells consistent under the stored periods.
- `damage` & `repeat`: the two branches' changes applied together. The hole color that a `damage` branch gives is filled from the mirror cell.
    - `$ClassMode` & `$MirrorOnly`: each cell takes the color it shares with its mirror cell, and the model is undefined where the two differ

## Open parameters
- none

## Not formed
- Separator lines of 1 cut the grid into panels, and the panels are repaired from one another or each on its own: the uniform lines are part of the tile, and they do not mark the repeating unit. Train0 has uniform rows at 4 and 7 in each 8-row period, and train2 has uniform rows at 1 and 7 and uniform columns at 1 and 7. These lines cut panels of unequal size that do not repeat one another, and a 7×7 panel has no repeat inside it.
- Every cell, blanked or not, takes its class color: under the concept's period derivation the unblanked cells of a class agree, so this gives the concept's output on every input. The model is equivalent to the concept.

## Tickets filed
- none
