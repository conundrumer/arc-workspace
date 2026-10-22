# dbff022c

## Concept
- The concept fits every pair (`work/task/dbff022c/probe.py`). It has no witness with verdict `other`.
- The concept is undefined in these places, and each one is a witness of a branch below:
    - a legend with no line on the grid edge (`legend-off-edge`)
    - a hole whose cells meet two colors (`stray-cell-in-hole`)
    - an input whose field is not 0 (`bg=DominantColor`)
- The concept is also undefined on a square 2×2 legend in a grid corner. There, a line of each axis lies on a grid edge. No source gives a reading that picks one of the two axes, and `$KeyLineNearEdge` is undefined there too.

## Choice points
- `key-line`: which line of the legend holds the keys
    - `concept`: the legend line that lies on the grid edge holds the keys, and the paint is the color beside each key on the other line.
    - `$KeyLineNearEdge`: replaces `key-line`. Among the legend's lines, the key line is the one with the least distance to the grid edge beyond it, and the other line holds the paints. It is undefined where two lines tie. Parameters: `bg`. It fits every pair.
        - witness `legend-off-edge`: breaks scene claim `legend`. Stands at the stored assignment. Plausibility `variant`, verdict `$KeyLineNearEdge`. Invariant of the inputs broken: in every input the legend lies against a grid edge.
    - `$KeyLineInner`: replaces `key-line`. The line on the grid edge holds the paints, and the inner line holds the keys. Parameters: `bg`. It fails Fit at train0, where the 4 outline is no key and its holes stay 0.
    - `$KeyLineOutlineColors`: replaces `key-line`. The key line is the legend line that holds more of the outline colors. It is undefined on a tie. Parameters: `bg`. It fails Fit at train0, where row 0 holds 3 and 4 and row 1 holds 3 and 7.
    - `$SymmetricPairs`: replaces `key-line`. A pair has no direction, so an outline of either color of a pair takes the other color. It is undefined where one color has two partners. Parameters: `bg`. It fails Fit at train0, where 6 pairs with 4 and with 7.
    - `$KeySideStored`: replaces `key-line`. A stored side gives the grid edge whose legend line holds the keys. Parameters: `bg`, `key_side`. It fails Fit: train0 needs the top side and train1 needs the left side, so no stored value fits every train pair.
- `legend`: how the legend is found
    - `concept`: the one object of several colors.
    - `$LegendOnEdge`: replaces `legend`. The legend is the one object that touches the grid edge. It is undefined where several objects touch the edge. Parameters: `bg`. It fails Fit at train0, where the 4 outline also touches the top edge.
- `hole`: which cells an outline paints
    - `concept`: a hole is a region of `bg` cells that no 4-adjacent walk through `bg` cells reaches from the grid edge, and its wall color is the one color its cells meet. It is undefined where a hole meets two colors.
    - `$Leak8`: replaces `outlines`. The walk through `bg` cells is 8-adjacent. Parameters: `bg`. It fails Fit at train0, where hole cell (8,3) reaches (9,2) on a diagonal, so it stays 0, and the output has 3 there.
    - `$EdgeWalls`: replaces `outlines` and `hole-wall`. A hole is any 4-connected region of `bg` cells that meets one color only, and the grid edge does not open it. Parameters: `bg`. It fails Fit at train2, where the `bg` strip at col 14 meets only 2 and takes 7.
    - `$BboxFill`: replaces `outlines`. An outline paints every `bg` cell in its bounding box. Parameters: `bg`. It fails Fit at train0, where (8,1) lies in the 3 outline's box and stays 0.
    - `$PerColorWalls`: replaces `outlines` and `hole-wall`. For each key color, the `bg` cells that no 4-adjacent walk through cells of other colors reaches from the grid edge take that key's paint. It is undefined where a cell takes two paints. Parameters: `bg`. It fits every pair.
        - witness `stray-cell-in-hole`: breaks scene claim `hole-wall`. Stands at the stored assignment. Plausibility `borderline`, verdict `$PerColorWalls`. Invariant of the inputs broken: every hole holds only 0 cells and meets one outline color.
- `bg`
    - `concept`: stored, 0.
    - `bg=DominantColor`: derives `bg` as the commonest color of the input. It replaces the stored `bg`. It is undefined where two colors tie for commonest. It fits every pair.
        - witness `bg=DominantColor`: breaks scene claim `outlines`, which at bg 0 reads the objects as drawn on a field of 0. Stands at the stored assignment. Plausibility `variant`, verdict `bg=DominantColor`. Invariant of the inputs broken: the field is 0 in every input.
    - `bg=SharedColor`: derives `bg` as each color of the input. It replaces the stored `bg`. It fails Fit at train0: at bg 3, for example, the cells that are not 3 form one object of several colors, so the model is undefined there.
- `key-line` & `legend`, `key-line` & `hole`, `key-line` & `bg`, `legend` & `hole`, `legend` & `bg`, `hole` & `bg`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Holes of an outline whose color is no key take some fill: the 7 outline of train0, the 5 outline of train1 and the 4 outline of train2 keep their holes 0, so the pairs give no such reading.
- An axis rule for a square legend in a grid corner: no pair, solver header, lib component or proposer gives one.
- `bg` from the proposers RarestColor, OutNewColor, AnyOutNewColor, VanishedColor, ChangedColor and UnchangedColor: none of them gives 0 on the train evidence.

## Tickets filed
none
