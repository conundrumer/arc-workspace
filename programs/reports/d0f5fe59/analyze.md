# d0f5fe59

## Concept
- Fits every pair: the shapes number 4, 3, 2 and 5, and each output is that count's square with the main diagonal in 8 on 0.
- No witness has the verdict `other`. Each rule has a relational form: the shapes are the components of the non-background cells (`Components8`), the shape color is their one color (`Unanimous`), and the output marks the cells at equal distance from the top and left edges.
- The concept is undefined where the shapes have more than one color, and where the input has no shape.
- Under 4-adjacency and 8-adjacency, every pair has the same shapes.

## Choice points
- `shape adjacency`
    - `concept`: the cells of a shape join through sides or corners
    - `$SideAdjacency`: replaces `shapes-on-background`, so the cells of a shape join through sides only; no parameter; undefined where the concept is. Fits every pair.
        - Witness `corner-link`: train2 input with a cell added at (6,9), which meets the right shape only at a corner. The concept gives the 2×2 diagonal and the branch gives the 3×3 diagonal. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. The invariant it breaks: every shape in the evidence joins through its sides, and the shapes stand apart by at least one background cell, corners included.
- `mark color`
    - `concept`: the one color of the shapes, derived from the input
    - `mark_color=stored`: replaces `diagonal-marks` with marks in a stored `mark_color` (8); undefined only where the input has no shape. Fits every pair.
        - Witness `mark_color=stored`: train2 input with the shapes in 3. The concept gives the diagonal in 3 and the branch gives it in 8. It breaks no scene claim. Plausibility `variant`, verdict `concept`. The invariant it breaks: every shape is 8.
    - `$CommonestShapeColor`: replaces `one-shape-color` and `diagonal-marks` with marks in the color that most shape cells have; no parameter; undefined where that color ties, and where the input has no shape. Fits every pair.
        - Witness `mixed-shape-colors`: train1 input with the shape at rows 8–9 in 3. The concept is undefined, and the branch and `mark_color=stored` give the 3×3 diagonal in 8. It breaks `one-shape-color`. Plausibility `borderline`, verdict `$CommonestShapeColor`. The invariant it breaks: every shape is 8.
- `shape cells`
    - `concept`: every non-background cell is a shape cell
    - `$ShapesOfOneColor`: replaces `shapes-on-background` and `one-shape-color`: the shapes are the groups of cells of a stored `shape_color` (8), the marks take `shape_color`, and cells of other colors are ignored. Undefined where the input has no cell of `shape_color`. Fits every pair.
        - Witness `mixed-shape-colors` (above): the branch gives the 2×2 diagonal in 8. It breaks `one-shape-color`. Plausibility `borderline`, verdict `$CommonestShapeColor`. The invariant it breaks: every shape is 8.
- `background`
    - `concept`: stored `background` (0)
    - `background=DominantColor`: derives `background` on each input as its commonest color; undefined where that color ties. Fits every pair.
        - Witness `background=DominantColor`: train2 input with the field in 5. The concept is undefined: the field and the shapes make one shape of two colors. The branch gives the 2×2 diagonal in 8 on 5. It breaks `shapes-on-background`. Plausibility `variant`, verdict `background=DominantColor`. The invariant it breaks: every field is 0.
- `what is counted`
    - `concept`: every shape
    - `$DistinctForms`: replaces `square-of-count`, so N is the number of shape forms up to translation; no parameter; undefined where the concept is. Fits every pair.
        - Witness `repeated-form`: train2 input with a second copy of the right shape at rows 5–7, cols 0–1. The concept gives the 3×3 diagonal and the branch gives the 2×2 diagonal. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$CongruenceClasses`: replaces `square-of-count`, so N is the number of shape forms up to D4. Fails test0: test0 has two P-pentominoes, (1,8)–(3,9) and (9,8)–(10,10), so the count is 4 where the output has 5.
- `output drawing`
    - `concept`: the diagonal is drawn from the count
    - `$CountTable`: replaces `square-of-count` and `diagonal-marks` with a stored table from count to output grid. Fails test0: the test count 5 is a key that no train pair has (the train counts are 4, 3 and 2).
- `shape adjacency` & `mark color`, `shape adjacency` & `shape cells`, `shape adjacency` & `background`, `shape adjacency` & `what is counted`, `shape adjacency` & `output drawing`, `mark color` & `background`, `mark color` & `what is counted`, `mark color` & `output drawing`, `shape cells` & `background`, `shape cells` & `what is counted`, `shape cells` & `output drawing`, `background` & `what is counted`, `background` & `output drawing`, `what is counted` & `output drawing`: the two branches' changes applied together
- `mark color` & `shape cells`: the model of `$ShapesOfOneColor` alone. The marks take `shape_color`, the one color of every shape. In every task of the generator, a stored `mark_color` equals `shape_color`, and so does the commonest shape color. So the `mark color` property exists only under the concept branch of `shape cells`.

## Open parameters
- none

## Not formed
- N as a cell count: train0 has 24 shape cells and N = 4, and train1 has 17 shape cells and N = 3, so no fixed ratio gives N.
- N as a color count: every input has one shape color, and N is 2 to 5.
- An output of a fixed size, as a bar of the count: the output sizes are 4, 3, 2 and 5, which is N on each pair.
- The anti-diagonal: `diagonal` is a stored parameter, and the pairs fix it to the main diagonal. It is not a choice point.

## Tickets filed
- none
