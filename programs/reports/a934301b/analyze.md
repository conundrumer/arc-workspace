# a934301b

## Concept
- Fits every pair: on each train and test input, erasing each 4-adjacent object of non-0 cells that holds more than one 8 gives the paired output.
- `touching-rectangles`, verdict `other`: two rectangles that share an edge, each holding one 8.
    - It breaks the scene claim `rectangles`: no two rectangles touch.
    - It stands at the stored assignment.
    - Plausibility `borderline`. It breaks this invariant of the inputs: every rectangle has a 0 cell between it and every other rectangle.
    - Every case reads the two rectangles as one component holding two marks, and erases both. The generator's rule erases a rectangle that holds more than one mark, so both rectangles stay and the output is the input.
- The generator applies the rule per rectangle: a rectangle that holds more than one `mark` cell becomes `background`. The concept's `count-marks` rule counts per connected component instead, which approximates that rule only where no two rectangles touch.

## Choice points
- `object adjacency`: which cells join one object
    - `concept`: 4-adjacency over non-`background` cells
    - `$EightAdjacent`: replaces `count-marks`, so that diagonal neighbors join one object (8-adjacency). It is defined on every input. It fits every pair.
        - Witness `corner-contact`: two rectangles that meet at a corner, each holding one 8. It breaks the scene claim `rectangles` (no two rectangles touch). Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: no two rectangles meet, even at a corner.
- `mark kind`: which cells of an object count as marks
    - `concept`: cells of the stored color `mark`
        - `mark source`: where the value of `mark` comes from
            - `concept`: stored
            - `mark=RarestColor`: derives `mark` as the rarest color of each input. It replaces the stored value of `mark` that `count-marks` reads. It is defined on every input. Where colors tie for rarest, each of them is a mark color. It fits every pair.
                - Witness `no-marks`: two clean rectangles and no 8 anywhere. Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: every input holds both an object with two or more marks and one with at most one.
    - `$NonBody`: replaces `count-marks`, so that a mark is any object cell not of the stored color `body`, which becomes a parameter. It is defined on every input. It fits every pair.
        - Witness `third-color`: a rectangle holding one 8 and two cells of 2. It breaks the scene claim `rectangles` (each rectangle is made of `body` and `mark` cells). Plausibility `borderline`, verdict `$NonBody`. It breaks this invariant of the inputs: every input holds only the colors 0, 1 and 8.
    - `$Minority`: replaces `count-marks`, so that a mark is any object cell not of the object's commonest color. Where two colors tie for commonest, the object has no marks. It fails Fit at train2: the 2x2 object at rows 0–1, cols 11–12 holds two 8s and two 1s, so it has no marks and stays, while the output erases it.
- `mark unit`: what the mark count counts
    - `concept`: mark cells
    - `$MarkGroups`: replaces `count-marks`, so that the count is the number of 4-adjacent groups of mark cells in the object. It is defined on every input. It fits every pair.
        - Witness `mark-domino`: a rectangle holding two edge-adjacent 8s. Plausibility `ordinary`, verdict `concept`.
    - `$MarkGroups8`: the same count over 8-adjacent groups. It fails Fit at train0: the object at rows 1–2, cols 1–3 has its two 8s at (1,2) and (2,3), which form one group, so it stays, while the output erases it.
- `selection`: which mark counts erase an object
    - `concept`: a count above the stored `max_marks`
    - `$CountTable`: replaces `erase-crowded` with a stored lookup table from a mark count to keep (`keep_count`: 0, 1) or erase (`drop_count`: 2, 3, 4). It is undefined on an input with an object whose count is in neither set. The test counts are all train counts. It fits every pair.
        - Witness `five-marks`: a rectangle holding five 8s. It stands at the assignment that adds 5 to `keep_count`. At the stored table, `$CountTable` is undefined on that input. Plausibility `ordinary`, verdict `concept`.
    - `$Fewest`: replaces `erase-crowded`, so that the objects with the fewest marks in the grid stay and every other object is erased. It fails Fit at train1: the objects with one mark at rows 0–2, cols 5–7 and at rows 2–4, cols 0–3 stay in the output, while the fewest count there is 0.
- `background source`: where the value of `background` comes from
    - `concept`: stored
    - `bg=DominantColor`: derives `background` as the commonest color of each input. It replaces the stored value that `count-marks` and `erase-crowded` read. It is defined on every input. It fits every pair.
        - Witness `dense-field`: rectangles of 1 cover more of the grid than 0 does. Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: 0 is the commonest color of every input.
- `object adjacency` & `mark kind`, `object adjacency` & `mark source`, `object adjacency` & `mark unit`, `object adjacency` & `selection`, `object adjacency` & `background source`, `mark kind` & `mark unit`, `mark kind` & `selection`, `mark kind` & `background source`, `mark source` & `mark unit`, `mark source` & `selection`, `mark source` & `background source`, `mark unit` & `selection`, `mark unit` & `background source`, `selection` & `background source`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Erasing per rectangle, where touching rectangles form one component: a component made of edge-touching rectangles of one `body` color does not fix how it divides into rectangles, so the rule has no relational form over such a component. `touching-rectangles` records the generator's output.
- Copying the kept objects onto a blank grid: no non-`background` cell lies outside an object, so this model is equivalent to the concept.
- Erasing by mark density (marks per object cell): a ratio counts nothing the task has, so the claim has no relational form. It also fails Fit at test0: the object at rows 8–11, cols 1–6 holds 2 marks in 24 cells and is erased, while the train1 object at rows 2–4, cols 0–3 holds 1 in 12 and stays.
- `body` derived under `$NonBody`: on an input alone, no proposer gives 1. SharedColor gives 0, 1 and 8, and DominantColor gives 0.
- `background` or `mark` derived by SharedColor: it gives 0, 1 and 8 on every input, and no single color.
- `mark` or `background` derived by VanishedColor, ChangedColor, UnchangedColor, ChangedPairs or VanishedNewPairs: on an input alone `ex_out` is empty, and none of them gives 8 or 0. ChangedColor and UnchangedColor give nothing, and VanishedColor gives every input color.
- `max_marks` derived: no proposer derives a count threshold.

## Issues filed
- none
