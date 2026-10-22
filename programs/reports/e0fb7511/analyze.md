# e0fb7511

## Concept
- The concept fits every pair: each 4-component of `0` with two or more cells takes `8` in every cell, and each lone `0` stays (`probe.py pairs`).
- The concept file's rule is the rule as the generator applies it, and no witness has the verdict `other`.

## Choice points
- `adjacency`
    - `concept`: 4-adjacency joins mark cells into components.
    - `$Adj8`: replaces `recolor-groups` with the same rule over 8-components, reads `mark`, `fill`, `min_size`, defined on every input; fails Fit at train0, where the diagonal pair `train0 input (0,2), (1,1)` forms one 8-component of size 2 and stays `0` in the output.
- `qualifying-test`
    - `concept`: a mark cell recolors when its component has at least `min_size` cells.
    - `$NeighborCount`: replaces `recolor-groups` with "each mark cell with at least `min_neighbors` 4-neighbors of `mark` takes `fill`", with `min_neighbors` 1 in place of `min_size`, defined on every input; fits every pair.
        - witness `domino-and-tromino`, at `min_neighbors` 2: a domino, an L-tromino and a lone cell of `0`. The concept recolors the domino and the tromino whole. `$NeighborCount` recolors only the corner cell of the tromino. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$SizeTable`: replaces `recolor-groups` with a lookup table from component size to the color that component's cells take (stored sizes 1 to `0`, and 2, 3, 5, 6, 8 to `8`), undefined on an input that has a component of a size that is not a key; fails Fit at test0, which has components of sizes 4 and 7, keys that no train pair contains.
- `mark` determination
    - `concept`: `mark` is stored.
    - `mark=RarestColor`: replaces the stored `mark` with the color of fewest cells in the input, which gives both colors where their counts tie; fits every pair, where `0` is the rarest color.
        - witness `mark=RarestColor`: a 5×5 grid where `0` has 19 cells and `1` has 6. The concept recolors the one 19-cell group of `0`. `mark=RarestColor` reads `1` as the mark and recolors the two dominoes of `1`. It breaks the scene claim `field-with-marks`, since there the marks outnumber the field. It breaks the invariant of the inputs that mark cells are less than a third of the grid (0.16 to 0.31 over the pairs). Plausibility `borderline`, verdict `concept`.
    - `mark=DominantColor`: derives `1`; fails Fit at train0, where it recolors the field.
    - `mark=SharedColor`, `mark=VanishedColor`: derive both `0` and `1`; fail Fit at train0, where the `1` components recolor.
- `fill` determination
    - `concept`: `fill` is stored.
    - `fill=OutNewColor`, `fill=AnyOutNewColor`: derive `fill` from the outputs. On a run over one input with `ex_out` empty they give no value, so they are undefined on every input; they fail Fit at train0.
- `adjacency` & `qualifying-test`, `adjacency` & `mark` determination, `adjacency` & `fill` determination, `qualifying-test` & `mark` determination, `qualifying-test` & `fill` determination, `mark` determination & `fill` determination: the two branches' changes applied together

## Open parameters
- none

## Not formed
- An upper bound on the size of a recolored component: no reader of the concept takes one, and the largest component in the pairs (8 cells) recolors.
- A derived `min_size`: no proposer derives a component size, and the pairs fix it at 2, since lone cells stay and every domino recolors.
- "A mark cell with a mark neighbor recolors", with no parameter: it is `$NeighborCount` at `min_neighbors` 1.
- A rule that reads `background`: no output cell depends on the field color, so the program does not read it.

## Tickets filed
- none
