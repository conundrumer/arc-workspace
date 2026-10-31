# ef26cbf6

## Concept
- Fits every pair (probe `work/task/ef26cbf6/probe.py`). Each rule has a relational form and nothing approximates it: tiles come from the full `divider_color` lines, pairs are the two tiles on one line across the two-deep axis, the key is the tile holding a color other than `background` and `pattern_color`, and each `pattern_color` cell of the other tile takes that color. No witness has verdict `other`.
- The concept model is undefined where no axis is two deep, where a pair has two key tiles or none, and where a key tile holds two key colors. On a 2×2 tile layout both axes are two deep, and it gives the output of each axis whose pairs are well formed (at most two grids).
- Every branch below fits every pair. Each witness has a branch defined and the concept undefined, and none breaks no scene claim. The task's pairs separate none of them.

## Choice points
- `pairing`: which key tile a pattern tile takes its color from
    - `concept`: the tile on the same line across the two-deep axis
    - `$AdjacentKey`: replaces `tile-pairs` and `paint-pattern`; a pattern tile (a tile with no key color) takes the color of the one key tile sharing a divider with it, over any tile layout; parameters `pattern_color`, `divider_color`, `background`; undefined where a pattern tile has no adjacent key tile or more than one. Fits every pair. Witness `shared-key-row`: breaks `divider-lines`, stored assignment, `borderline`, verdict `$AdjacentKey`; breaks the invariant that every input lays its tiles out two deep, each pattern tile across from its own key tile. Where both models are defined they agree, so no witness has both defined.
- `key-identification`: which tile of a pair is the key, and its color
    - `concept`: the tile holding a color other than `background` and `pattern_color`, and that color
    - `$DotKey`: replaces `key-tile`; the key tile is the tile holding exactly one non-`background` cell, of any color; parameters as the concept; undefined where both tiles of a pair, or neither, hold a lone cell. Fits every pair. Witness `key-dot-in-pattern-color`: breaks `key-tile`, stored assignment, `borderline`, verdict `$DotKey`; breaks the invariant that no key dot has the pattern color.
        - `painted-cells`: which cells of the pattern tile are repainted
            - `concept`: the `pattern_color` cells
            - `$PaintAllInk`: replaces `paint-pattern`; every non-`background` cell of the pattern tile takes the key color; reads no `pattern_color`; undefined where `$DotKey` is. Fits every pair. Witness `pattern-in-other-color`: breaks `pattern-tile`, stored assignment, `variant`, verdict `$PaintAllInk` (the output `$CommonestInk` gives too); breaks the invariant that every pattern is drawn in 1.
    - `$CenterKey`: replaces `key-tile`; the key tile is the tile whose center cell is neither `background` nor `pattern_color`, and its color is that cell's; parameters as the concept; undefined where both tiles of a pair, or neither, have such a center. Fits every pair. Witness `extra-cell-in-key-tile`: breaks `key-tile`, stored assignment, `borderline`, verdict `$CenterKey`; breaks the invariant that a key tile holds one non-background cell.
- `pattern-color`: the source of `pattern_color`
    - `concept`: stored, 1
    - `$CommonestInk`: derives `pattern_color` as the commonest color of the input other than `background` and `divider_color`; replaces the stored value in `pattern-tile`; undefined where that count ties. Fits every pair. Witness `pattern-in-other-color`: breaks `pattern-tile`, stored assignment, `variant`, verdict `$CommonestInk`; breaks the invariant that every pattern is drawn in 1.
    - `pattern_color=SharedColor`, `pattern_color=DominantColor`, `pattern_color=RarestColor`, and each proposer that reads outputs: fails Fit at train0. On train0's input alone none gives 1 as its only value (SharedColor gives every color of the input, DominantColor gives 0, RarestColor gives 2, 3 and 6, and the output readers have no `ex_out` to read).
- `divider-color`: the source of `divider_color`
    - `concept`: stored, 4
    - `$LineDivider`: derives `divider_color` as the one non-`background` color that fills whole rows or columns; replaces the stored value in `divider-lines`; undefined where no such color exists or several do. Fits every pair. Witness `divider-in-other-color`: breaks `divider-lines`, stored assignment, `variant`, verdict `$LineDivider`; breaks the invariant that the dividers are 4.
    - `divider_color=<Proposer>`, each proposer: fails Fit at train0. On train0's input alone none gives 4 as its only value (DominantColor gives 0, which outnumbers 4 by 35 cells to 23).
- `background`: the source of `background`
    - `concept`: stored, 0
    - `background=DominantColor`: derives `background` as the commonest color of the input; replaces the stored value in `key-tile` and `pattern-tile`; undefined where that count ties. Fits every pair (0 is the commonest color in every input). Witness `background=DominantColor`: breaks `key-tile`, stored assignment, `variant`, verdict `background=DominantColor`; breaks the invariant that the background is 0.
    - `background=SharedColor`, `background=RarestColor`, and each proposer that reads outputs: fails Fit at train0. On train0's input alone none gives 0 as its only value.
- `pairing` & `key-identification`, `pairing` & `pattern-color`, `pairing` & `divider-color`, `pairing` & `background`, `pairing` & `painted-cells`, `key-identification` & `pattern-color`, `key-identification` & `divider-color`, `key-identification` & `background`, `pattern-color` & `divider-color`, `pattern-color` & `background`, `divider-color` & `background`, `painted-cells` & `divider-color`, `painted-cells` & `background`: the two branches' changes applied together
- `painted-cells` & `pattern-color`: `$PaintAllInk` & `$CommonestInk` gives `$PaintAllInk`'s model alone. `$PaintAllInk` reads no `pattern_color`, so the pattern-color property does not exist with it. The point stays at the concept, where every other branch reads `pattern_color`.

## Open parameters
- none

## Not formed
- Pairing by reading order (the k-th key colors the k-th pattern): no source suggests it. In every pair each key faces its pattern across one divider, and where keys sit on one side it gives the concept's pairs.
- Painting every non-background cell under the concept's key identification: equivalent to the concept. Wherever the concept is defined, the pattern tile holds only `background` and `pattern_color`, and where it is undefined so is this model.
- A tile-size or tile-count parameter: the tiles come from the divider lines, so no size is read. The 3×3 size is an invariant of the inputs that no rule uses.

## Tickets filed
- none
