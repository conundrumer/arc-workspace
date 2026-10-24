# f8a8fe49

## Concept
- Fits every pair (train0–2, test0; `work/task/f8a8fe49/check_concept.py`, `work/task/f8a8fe49/probe.py`). Each claim has a relational form: the mirror keeps a mark's distance to its nearer base, and "nearer" compares the two distances. No witness has verdict `other`.
- The verdict at `$WholeShape` and at `$FourAdjacent` is `$WholeShape`: where a mark shape crosses the midline, the generator is judged to flip the shape whole. The concept's per-cell `marks-mirror-out` gives the same output on every input where each mark shape lies wholly on one side of the midline, and every input in the evidence is like that.

## Choice points
- `flip-unit`: what flips as one unit, and so which base it flips across
    - `concept`: each mark cell, across the base it is nearer to
    - `$WholeShape`: replaces `marks-mirror-out`: each 8-connected mark shape flips whole across the base nearer to its nearest cell. Parameters: none beyond the concept's. Undefined on an input where a shape's nearest cells are equally near both bases. Fits every pair. Witness `$WholeShape`: a 3-cell bar over rows 6–8 with a lone mark at (9,9) on train0's brackets. Breaks no scene claim. Stands at the stored assignment. `borderline`, verdict `$WholeShape`. Invariant broken: every mark shape lies on one side of an empty middle line.
        - `shape-adjacency`: which cells join one shape
            - `concept`: 8-adjacency
            - `$FourAdjacent`: replaces the 8-adjacency of `$WholeShape` with 4-adjacency. Undefined where `$WholeShape` is, for 4-connected shapes. Fits every pair. Witness `$FourAdjacent`: the diagonal chain (6,6), (7,7), (8,8) with a lone mark at (9,5) on train0's brackets. As 4-connected singletons it gives the concept's output, and as one 8-connected shape it flips whole upward. Breaks no scene claim. Stored assignment. `borderline`, verdict `$WholeShape`. Invariant broken: every mark shape lies on one side of an empty middle line.
- `placement`: where a flipped mark lands
    - `concept`: its mirror image across the base, at the same depth outside as inside
    - `$FlipToGap`: replaces `marks-mirror-out`: the marks nearer each base flip as a group, and the group's near edge sits `out_gap` empty lines outside the base. Parameter `out_gap`: 1. Defined wherever the concept is. Fits every pair. Witness `marks-off-arm-line`: marks (7,6), (7,7), (8,9) on train0's brackets. Breaks `marks-touch-arm-line`. Stored assignment. `variant`, verdict `concept`. Invariant broken: the marks nearer each bracket include a cell on the line next to its arm line.
    - `$TranslateOut`: replaces `marks-mirror-out`: the marks nearer each base move outward as a group without flipping, and their near edge sits one empty line outside the base. Parameter `out_gap`: 1. Fails Fit at train0, where the top group's rows come out in input order (`5 5 5` above `5 0 5`), and the output has them reversed.
- `mark_color`: where the mark color comes from
    - `concept`: stored, 5
    - `mark_color=RarestColor`: derives `mark_color` (named in `marks-between`) as the rarest color of the input. Undefined where that color is not single, or is the bracket color. Fits every pair: 5 is the rarest color on every input. Witness `mark_color=RarestColor`: 19 marks fill rows 6–9, cols 5–9 of train0's brackets except (8,9), against 18 bracket cells. Breaks no scene claim. Stored assignment. `borderline`, verdict `concept`. Invariant broken: the mark cells are fewer than the bracket cells.
- `background`: where the background color comes from
    - `concept`: stored, 0
    - `background=DominantColor`: derives `background` (named in `background`) as the input's commonest color. Undefined where that color is not single, or is the bracket color. Fits every pair. Witness `background=DominantColor`: a 6×7 grid cropped to two horizontal 7-cell brackets (rows 0–1 and 4–5) holding 7 marks in rows 2–3, so 18 bracket cells outnumber 17 background cells. Breaks `mirror-in-frame`. Stored assignment. `foreign`, verdict `concept`. Invariant broken: each mirror image lies in the grid, and background is the commonest color.
- `flip-unit` & `placement`, `flip-unit` & `mark_color`, `flip-unit` & `background`, `placement` & `mark_color`, `placement` & `background`, `mark_color` & `background`, `shape-adjacency` & `placement`, `shape-adjacency` & `mark_color`, `shape-adjacency` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Mirror about another line (the arm line, or the line just outside the base): train0 puts row 6 at row 2 and row 7 at row 1, which is the mirror about base row 4 alone. A mirror about arm row 5 puts row 6 onto the base, and one about row 3.5 puts it at row 1.
- Flip to the farther bracket: fails train0, where row 9 lands at row 13 below the bottom base.
- The two halves split at an empty middle line rather than by the nearer base: on every input where such a line exists, it assigns each mark the side the nearer base assigns. Where none exists, it is undefined. It adds no output that `flip-unit`'s branches do not give.
- `bracket_color` derived: no proposer gives 2 from one input alone. SharedColor gives 0, 2 and 5, and UnchangedColor reads outputs, which a `@derive` branch does not have.
- `mark_color=ChangedColor`, `bracket_color=UnchangedColor`: both compare an input with its output, and a `@derive` branch reads no output.
- `mark_color=SharedColor`: it gives 0, 2 and 5 on each input, three values for a one-value parameter.
- Bracket axis as a parameter: train0 has horizontal bases and train1–2 vertical ones, so the program enumerates both axes (Every value), and no parameter stores one.

## Tickets filed
- none
