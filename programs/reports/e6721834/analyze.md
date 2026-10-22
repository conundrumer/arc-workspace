# e6721834

## Concept
- Fits every pair. In each pair the dots have exactly one cover by distinct rectangles, and the moved rectangles stay inside the dot half and do not overlap (`probe.py`). The concept finds the dot half as the half that the other half's marks cover exactly. Where an input has two covers, the concept gives the output of each one. No witness has the verdict `other`, and each rule has a relational form.

## Choice points
- `dot-grouping`
    - `concept`: the dots split into groups, and each group is matched to one rectangle
        - `group-source`
            - `concept`: the groups are an exact cover of the dots by the translated marks of the rectangles, with their colors
            - `$DotClusters`: replaces `exact-cover`. Two dots join when their Chebyshev distance is at most `merge_dist`, and each cluster must equal the translated marks of one rectangle. Parameter `merge_dist`. Undefined where a cluster matches no rectangle. Fits every pair at `merge_dist` 2 and 3. Witness `ambiguous-pair` breaks `exact-cover`: it has two covers, the rectangle with marks 2 and 3, or the two one-mark rectangles. It stands at the stored assignment, `borderline`, verdict `$DotClusters`. The invariant it breaks: the dots of each input have one cover.
                - `cluster-metric`
                    - `concept`: Chebyshev distance, the ball of 8-adjacency
                    - `$ClusterTaxicab`: replaces the distance with taxicab distance at most `merge_taxi`. Parameter `merge_taxi`. Fits every pair at `merge_taxi` 3, 4 and 5. Witness `diagonal-pair` breaks `exact-cover` (two covers), at `merge_taxi` = 3, `borderline`, verdict `$DotClusters`. The invariant it breaks: the dots of each input have one cover.
        - `rectangle-reuse`
            - `concept`: each rectangle serves at most one group
            - `$ReuseRectangle`: replaces "a different rectangle" in `exact-cover` with any rectangle, used any number of times. No parameter. Undefined where the drawing of a cover puts two colors on a cell. Fails Fit at test0. That input has four covers, and three of them place the one-mark rectangle of input rows 19–22, cols 1–2 on single dots 1, where its copies overlap with different colors.
        - `fit-filter`
            - `concept`: `placed-fit` is a scene claim, and no cover is discarded
            - `$FitFiltersCovers`: adds a rule. A cover is discarded when its moved rectangles overlap or leave the dot half. No parameter. Undefined where no cover is left. Fits every pair. Witness `edge-cover` breaks `exact-cover`: it has two covers, and one of them moves a rectangle off the top edge. It stands at the stored assignment, `borderline`, verdict `$FitFiltersCovers`. The invariant it breaks: the dots of each input have one cover.
    - `$EachOccurrence`: replaces `exact-cover`, `move-rectangle` and `drop-unmatched`. Each rectangle is drawn at every translation that puts its marks on dots of their colors. No parameter. Undefined where the drawn copies put two colors on a cell, or where a dot is under no copy's marks. Fails Fit at test0. The one-mark rectangle of input rows 19–22, cols 1–2 lands on each of the five dots 1, and its copies overlap with different colors.
- `mark-colors`
    - `concept`: a mark goes only on a dot of its own color
    - `$MatchShapeOnly`: replaces "with their colors" in `exact-cover`, so marks match dots by position alone. No parameter. Fits every pair. Witness `same-shape-two-colors` breaks no scene claim. It stands at the stored assignment, `ordinary`, verdict `concept`.
- `transform`
    - `concept`: a rectangle moves by translation alone
    - `$MatchUnderD4`: replaces `exact-cover` and `move-rectangle`. A rectangle is turned or reflected by a D4 element, then moved. No parameter. Fails Fit at train1, where it gives four outputs: each of the two rectangles also fits its dots after a D4 element that changes its picture, a half turn for each one.
- `unmatched-rectangle`
    - `concept`: a rectangle with no group is dropped
    - `$KeepUnmatched`: replaces `drop-unmatched`. A rectangle with no group is drawn at its own place in the dot half. No parameter. Fails Fit at train0. The four-mark rectangle of input rows 8–10, cols 10–14 is drawn at output rows 8–10, cols 10–14, which hold `0`.
- `adjacency`
    - `concept`: the rectangles are the 4-connected parts of the object half
    - `$Objects8`: replaces the 4-adjacency of `object-half` with 8-adjacency, so rectangles that touch at a corner move as one object. No parameter. Fits every pair. Witness `corner-touch` breaks `object-half` (two rectangles touch at a corner). It stands at the stored assignment, `borderline`, verdict `$Objects8`. The invariant it breaks: no two rectangles touch, even at a corner.
- `split`
    - `concept`: the grid is cut at its middle into two equal halves
    - `$SplitAtColorChange`: replaces the equal size in `two-halves`. The grid is cut at the line where the background color changes. No parameter. Fits every pair. Witness `unequal-parts` breaks `two-halves` (6 rows against 10). It stands at the stored assignment, `variant`, verdict `$SplitAtColorChange`. The invariant it breaks: the two parts are of equal size.
- `mark-cells`
    - `concept`: a rectangle's marks are its cells that are not of its most common color
    - `$MarksByDotColor`: replaces the marks of `object-half`. The marks are the cells of the rectangle whose color some dot has. No parameter. Fits every pair. Witness `extra-mark-color` breaks `object-half` (one rectangle has marks of two colors). It stands at the stored assignment, `variant`, verdict `concept`. The invariant it breaks: the marks of each rectangle are of one color.
- `dot-grouping` & `mark-colors`, `dot-grouping` & `transform`, `dot-grouping` & `unmatched-rectangle`, `dot-grouping` & `adjacency`, `dot-grouping` & `split`, `dot-grouping` & `mark-cells`, `mark-colors` & `transform`, `mark-colors` & `unmatched-rectangle`, `mark-colors` & `adjacency`, `mark-colors` & `split`, `mark-colors` & `mark-cells`, `transform` & `unmatched-rectangle`, `transform` & `adjacency`, `transform` & `split`, `transform` & `mark-cells`, `unmatched-rectangle` & `adjacency`, `unmatched-rectangle` & `split`, `unmatched-rectangle` & `mark-cells`, `adjacency` & `split`, `adjacency` & `mark-cells`, `split` & `mark-cells`, `group-source` & `mark-colors`, `group-source` & `transform`, `group-source` & `unmatched-rectangle`, `group-source` & `adjacency`, `group-source` & `split`, `group-source` & `mark-cells`, `rectangle-reuse` & `mark-colors`, `rectangle-reuse` & `transform`, `rectangle-reuse` & `unmatched-rectangle`, `rectangle-reuse` & `adjacency`, `rectangle-reuse` & `split`, `rectangle-reuse` & `mark-cells`, `fit-filter` & `mark-colors`, `fit-filter` & `transform`, `fit-filter` & `unmatched-rectangle`, `fit-filter` & `adjacency`, `fit-filter` & `split`, `fit-filter` & `mark-cells`, `cluster-metric` & `mark-colors`, `cluster-metric` & `transform`, `cluster-metric` & `unmatched-rectangle`, `cluster-metric` & `adjacency`, `cluster-metric` & `split`, `cluster-metric` & `mark-cells`, `group-source` & `rectangle-reuse`, `group-source` & `fit-filter`, `rectangle-reuse` & `fit-filter`, `cluster-metric` & `rectangle-reuse`, `cluster-metric` & `fit-filter`: the two branches' changes applied together
    - `$ReuseRectangle` & `$FitFiltersCovers` fits every pair. At test0 the filter discards the three covers whose copies overlap.

## Open parameters
- `merge_dist`: 2, 3, under `$DotClusters`
- `merge_taxi`: 3, 4, 5, under `$ClusterTaxicab`

## Not formed
- The dot half taken as the half with fewer foreground cells: this is equivalent to the concept. Each rectangle that a cover uses has a body cell beyond its marks, so the covered half always has fewer cells than the other half, and the reverse direction has no cover.
- Dots kept under the moved rectangles: each dot lies under a mark of its own color, so keeping or erasing the dots gives the same output.
- An order of drawing for moved rectangles that overlap: no pair has moved rectangles that overlap, and no pair shows an order among rectangles.
- The output frame or background taken from the object half: in every pair, the output has the size and the background of the dot half, and no reading takes the other half.
- Each rectangle drawn at its one occurrence among the dots, and undefined where it has several: at test0 the one-mark rectangle has five occurrences, so this reading is undefined there, the same as `$EachOccurrence`.

## Tickets filed
- 10-941_task_e6721834_analyze.md
