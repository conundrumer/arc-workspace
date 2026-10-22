# d2abd087

## Concept
- Fits every pair. Each claim has a relational form: a shape is a 4-component of `shape_color` cells, and its size is a cell count (`Components`, `Tally`). The rule is not an approximation.
- No witness has the verdict `other`.
- `target_size` is fixed by the pairs: shapes of 5 and 7 cells take 1 (train0, train2), so neither `size >= 6` nor `size <= 6` fits.
- The test holds an 8-cell shape (test0 rows 0–2, cols 0–3). No train shape has 8 cells, so the concept's rule for sizes other than 6 is what reaches it.

## Choice points
- `adjacency`: which cells join one shape
    - `concept`: 4-adjacency
    - `$Diag8`: replaces `shapes-on-background` with 8-components of `shape_color` cells (`Components8`). Defined on every input. Fits every pair: no two shapes in the evidence touch at a corner.
        - Witness `diagonal-contact`: two 3-cell strokes meet at the corner (1,3)/(2,4). The concept colors them 1 as two shapes, and `$Diag8` colors them 2 as one 6-cell shape. It breaks no scene claim of the concept case. Plausibility `variant`: it breaks the invariant that no two shapes touch at a corner, which holds over about twenty shapes packed into 10×10 grids. Verdict `concept`.
- `shape-cells`: which cells the shapes are made of
    - `concept`: the cells of the stored `shape_color`
    - `$AnyInk`: replaces `shapes-on-background` with same-color 4-components of every color other than `background`. It reads `background` in place of `shape_color`. Defined on every input. Fits every pair.
        - Witness `second-ink-color`: a 6-cell shape of color 3 among gray shapes. The concept keeps it 3, and `$AnyInk` colors it 2. It breaks `shapes-on-background`, because that shape is not `shape_color`. Plausibility `borderline`: it breaks the invariant that every non-background cell is 5. Verdict `$AnyInk`.
        - `background`: the source of the background color, under `$AnyInk`
            - `concept`: stored 0
            - `background=DominantColor`: `background` is derived as the commonest color of the input. Fits every pair, since 0 outnumbers 5 in every input.
                - Witness `background=DominantColor`: gray bars cover 63 of 100 cells. With background 0, the bars are shapes and take 1. With the derived background 5, the 0 runs are the shapes: they take 1, and the bars stay 5. It breaks no scene claim. Plausibility `borderline`: it breaks the invariant that 0 is the commonest color of each input. Verdict `concept`.
    - `shape_color=RarestColor`: `shape_color` is derived as the rarest color of the input. Fits every pair, since 5 is rarer than 0 in every input.
        - Witness `shape_color=RarestColor`: every shape is color 4, and no cell is 5. The concept finds no shape and gives the input unchanged. The derived branch colors the color-4 shapes by size, and `$AnyInk` gives the same output. At the stored `shape_color` 5, it breaks `shapes-on-background`. Plausibility `variant`, because it is a color-permuted scene. It breaks the invariant that the shapes are color 5. Verdict `shape_color=RarestColor`.
    - `shape_color=SharedColor`: derives both 0 and 5, so 0 regions are recolored too. Fails Fit at train0.
    - `shape_color=DominantColor`: derives 0. Fails Fit at train0.
- `selection`: which shapes take `match_color`
    - `concept`: cell count equals the stored `target_size`
    - `$SizeTable`: replaces `size-match-recolor` and `size-miss-recolor` with a stored table from cell count to color. It is undefined on a shape whose count the table lacks. Fails Fit at test0: the train counts are 2–7, and the test has an 8-cell shape.
    - `$FootprintTable`: replaces the same two rules with a stored table from a shape's footprint, up to D4, to a color. Fails Fit at test0: the shapes at rows 4–5, cols 1–4, at row 8, and at rows 0–2, cols 0–3, have footprints that no train shape has.
    - `$SizeAtLeast`: count ≥ `target_size`. Fails Fit at train2, where the 7-cell shapes take 1.
    - `$SizeAtMost`: count ≤ `target_size`. Fails Fit at train0, where the 5-cell shape takes 1.
    - `$Largest`: the shapes of the largest count take `match_color`. Fails Fit at train2, where the 7-cell shapes take 1.
    - `$CommonestSize`: the shapes of the commonest count take `match_color`. Fails Fit at train1, where counts 4 and 6 tie and the 4-cell shapes take 1.
- `match_color source`
    - `concept`: stored 2
    - `match_color=OutNewColor`, `match_color=AnyOutNewColor`, `match_color=ChangedPairs`: each reads train outputs. `ex_out` is empty in a run, so each gives no value. Fails Fit at train0.
    - `match_color=SharedColor`, `match_color=DominantColor`, `match_color=RarestColor`: each gives 0 or 5. Fails Fit at train0.
- `other_color source`
    - `concept`: stored 1
    - `other_color=OutNewColor`, `other_color=AnyOutNewColor`, `other_color=ChangedPairs`: each reads train outputs, and gives no value in a run. Fails Fit at train0.
    - `other_color=SharedColor`, `other_color=DominantColor`, `other_color=RarestColor`: each gives 0 or 5. Fails Fit at train0.
- `adjacency` & `shape-cells`, `adjacency` & `selection`, `adjacency` & `match_color source`, `adjacency` & `other_color source`, `shape-cells` & `selection`, `shape-cells` & `match_color source`, `shape-cells` & `other_color source`, `selection` & `match_color source`, `selection` & `other_color source`, `match_color source` & `other_color source`, `adjacency` & `background`, `selection` & `background`, `match_color source` & `background`, `other_color source` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `target_size` as a set of counts: the concept's clauses read `target_size` as a relation, so a set of counts is a value of the same parameter, with the program unchanged.
- `target_size` derived: no proposer gives a component's cell count, and no reading of the pairs gives 6 from something in the input.
- Shape color derived from the shape's bounding box, or from its form other than by a stored table: the 6-cell shapes include a 2×3 block, S-shapes and an L-shape. Their bounding boxes differ (2×3, 3×3, 4×3), and shapes of other sizes share those boxes.
- `background` derived under the concept: the concept program reads no `background`.

## Tickets filed
- none
