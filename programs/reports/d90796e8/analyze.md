# d90796e8

## Concept
- Fits every pair, train and test, at the stored assignment (`merge-color` 3, `absorbed-color` 2, `result-color` 8, `background` 0).
- train2 input (1,6) is green with a red cell at (0,5) on its diagonal, and the output keeps both, so the pairs fix 4-adjacency.
- No witness has verdict `other`. The concept's rule is relational as written, so no rule approximates another.

## Choice points
- `background`: what color the erased red cell takes
    - `concept`: the stored `background` 0
    - `background=DominantColor`: replaces the stored `background` in `merge-pair` with the commonest color of the input, derived on the input alone; undefined on an input where two colors tie for the most cells. Fits every pair.
        - witness `background=DominantColor`: a green-red pair on a gray field, at the stored assignment. It breaks `scattered-single-cells`, since the field is not `background` and gray cells sit side by side. Plausibility `foreign`: at the stored `background` 0, every input lays its single cells on a black field, and the generator never lays a field of another color. Verdict `background=DominantColor`: a person erases the red cell into the field around it.
- `pair-condition`: which green cells with a red 4-neighbor merge
    - `concept`: every green cell that has a red 4-neighbor, with every such red neighbor erased (`merge-pair`)
    - `$IsolatedPair`: replaces `merge-pair`. A 4-connected object of non-`background` cells merges only when it is exactly one `merge-color` cell and one `absorbed-color` cell, and every other object is unchanged. Defined on every input. Fits every pair: no pair of the evidence touches a third non-background cell.
        - witness `pair-touching-other-color`: a green-red pair with a gray cell touching the red cell, at the stored assignment. It breaks no scene claim. Plausibility `ordinary`: train2 input (1,0)–(2,0) and test input (6,0)–(6,1) show a gray cell touching a green one, so the generator lets other colors touch. Verdict `concept`.
    - `$ExclusivePair`: replaces `merge-pair`. A green cell and a red cell merge only when each is the other's one 4-neighbor of the partner color, and a green or red cell with two partners is unchanged. Defined on every input. Fits every pair.
        - witness `red-between-two-greens`: a red cell with a green cell on each side, at the stored assignment. It breaks `pairs-disjoint`. Plausibility `borderline`: it breaks the invariant that every red cell touches at most one green cell side by side and every green cell touches at most one red cell. Verdict `concept`: each green cell that touches the red cell turns purple, and the red cell is erased.
- `adjacency`: what counts as a green cell touching a red cell
    - `concept`: a 4-neighbor
    - `$EightAdjacent`: replaces 4-adjacency in `merge-pair` with 8-adjacency. Fails Fit at train2: the green cell at (1,6) has the red cell (0,5) on its diagonal, and the branch turns (1,6) purple and erases (0,5), where the output keeps both.
- `kept-cell`: which cell of a merging pair takes `result-color`
    - `concept`: the `merge-color` cell
    - `$PositionalKeep`: replaces `merge-pair`. The top or left cell of a green-red pair takes `result-color`, and the other cell is erased. Fails Fit at train2: in the pair (2,2) red and (2,3) green, the branch puts purple at (2,2), where the output has it at (2,3).
- `background` & `pair-condition`, `background` & `adjacency`, `background` & `kept-cell`, `pair-condition` & `adjacency`, `pair-condition` & `kept-cell`, `adjacency` & `kept-cell`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `background` derived by `SharedColor`: it gives every color of the input, which is four colors on every input of the evidence. The output then holds more than one grid, so the branch fails Fit at train0.
- `merge-color` or `absorbed-color` derived by `RarestColor`: on train1 input the rarest color is 5 alone, which is neither 3 nor 2.
- `result-color` derived by `OutNewColor` or `AnyOutNewColor`, and `absorbed-color` derived by `ChangedColor`: on an input alone `ex_out` is empty, so these give no value and the branch is undefined on every pair.
- `absorbed-color` derived by `VanishedColor`: with `ex_out` empty it gives every color of the input, so the output holds more than one grid and the branch fails Fit at train0.
- A stored table from each green-red pair layout to its output: it holds the same four colors as the concept's parameters, and the program derives each layout's output from them, so it adds no model.

## Tickets filed
- none
