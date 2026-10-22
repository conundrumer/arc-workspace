# e048c9ed

## Concept
- The concept fits every train pair and the test pair (`probe.py`).
- The stored `length_color` table holds 2 → 1, 3 → 4, 4 → 9, 5 → 6. These are the last digits of 1, 4, 9 and 16, the squares of one less than each length. The generator probably applies "the mark's color is (length − 1)² mod 10". That rule reads a color as a number and has no relational form, so the stored table is an approximation of it.
    - Witness `unseen-length` (a bar of length 6) is where the two differ. The table has no key 6 and the concept is undefined there. That witness's verdict goes to `$DerivedLengthColor`, which fails Relational form.
- No witness has the verdict `other`.

## Choice points
- `mark-color`
    - `concept`: the mark takes the color that the stored `length_color` table gives for the bar's cell count.
    - `$DerivedLengthColor`: replaces `mark-per-bar`. The mark's color is (n − 1)² mod 10, with n the bar's cell count, and no table is stored. It is defined on every bar. It fits every pair, and it fails Relational form because the rule reads a color as a digit.
        - Witness `unseen-length`, at the stored assignment. It breaks `bar-lengths-known`. Plausibility `variant`. Verdict `$DerivedLengthColor`. It breaks the input invariant that every bar has 2 to 5 cells.
    - `$GapKey`: replaces `mark-per-bar`. A stored table is keyed by the count of background cells between the bar's end and the marker's column. It fails Fit at train2: gap 3 gives 6 there and 4 in train1.
    - `$BarColorKey`: replaces `mark-per-bar`. A stored table is keyed by the bar's color. It fails Fit at train1: color 1 gives 9 there and 1 in train0.
    - `$RankKey`: replaces `mark-per-bar`. A stored table is keyed by the dense rank of the bar's length among the input's bar lengths. It fails Fit at train2: rank 1 (length 5) gives 6 there, and rank 1 (length 3) gives 4 in train1.
- `marker`
    - `concept`: the marker is the one single-cell object, and the mark goes in its column.
    - `$MarkerOnEdge`: replaces `one-marker`. The marker is the one object with a cell on the `marker_edge` row, and the program reads `marker_edge` (T). It is undefined where no object or more than one object meets that row, or where that object spans more than one column. It fits every pair.
        - Witness `two-cell-marker`, at the stored assignment: the marker is two gray cells stacked in col 4 on the top row. It breaks `one-marker`. Plausibility `borderline`. Verdict `$MarkerOnEdge`. It breaks the input invariant that the marker is one cell.
    - `$MarkerByColor`: replaces `one-marker`. The marker is the cells of the stored `marker_color` (5). It is undefined where those cells span more than one column. It fails Fit at test0: the gray bar at test0 input (6,1), (6,2) joins the marker and gets no mark.
- `background`
    - `concept`: `background` is stored (0).
    - `background=DominantColor`: the background is the commonest color of the input. It is undefined where two colors tie for commonest. It fits every pair.
        - Witness `background=DominantColor`, at the stored assignment: the same scene on a field of 3. It breaks `background`. Plausibility `variant`, because it is a color permutation of the task. Verdict `background=DominantColor`. It breaks the input invariant that the field is 0.
    - `background=SharedColor`: the background is a color present in the input. On one input this gives every color present, so the parameter takes several values. It fails Fit at train0.
- `bar-axis`
    - `concept`: `bar_axis` is stored (H). Only bars along it are marked.
    - `$EitherAxis`: replaces `bars` and `mark-per-bar`. The program has no `bar_axis`. A bar along either axis is marked where its line meets the marker's line across it. It is undefined on an object of two or more cells that is not straight. It fits every pair.
        - Witness `turned-scene`, at the stored assignment: the scene turned a quarter, with bars along columns and the marker on the left column. It breaks `bars` and `one-marker`. Plausibility `variant`, because it is a D4 image of the task. Verdict `$EitherAxis`. It breaks the input invariants that the bars are horizontal and that the marker is on the top row.
- `mark-color` & `marker`, `mark-color` & `background`, `mark-color` & `bar-axis`, `marker` & `background`, `marker` & `bar-axis`, `background` & `bar-axis`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Measuring a bar by its bounding extent in place of its cell count: the two agree on every straight bar. An object that is not a straight bar is outside the scene, and no source gives a rule for one.
- A rule for a bar that reaches the marker's column: `bars-short-of-marker` excludes it, and no pair or source shows such a scene.
- A marker that is the single cell of a stored or derived color (`RarestColor` gives 5 on every input): no pair separates it from the concept. With color alone, it is `$MarkerByColor`.

## Tickets filed
- none
