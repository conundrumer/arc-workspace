# b7256dcd

## Concept
- The concept case fits every pair: each 4-connected shape of color 6 takes the color of the one marker cell 4-adjacent to it, and every marker, including the markers in train1 (1,0) and test0 (0,6) that touch no shape, goes to background 7.
- The concept is undefined where a shape touches no marker cell or more than one marker cell; the branches at `unmarked-shape` and `several-marker-cells` define it there.
- No witness has verdict `other`.

## Choice points
- `shape-connectivity`
    - `concept`: shapes are the 4-connected components of `shape_color`
    - `$Shapes8`: replaces `shapes`; shapes are the 8-connected components of `shape_color`; undefined where shapes that touch at a corner have more than one marker between them. Fits every pair. Witness `diagonal-touch`: plausibility `variant`, verdict `concept`; breaks the invariant that no two shapes of an input touch, even at a corner.
- `contact-adjacency`
    - `concept`: a marker touches a shape when 4-adjacent to one of its cells
    - `$Contact8`: replaces `one-marker-per-shape` and `recolor-shape` with 8-adjacent contact. Fails Fit at train0: marker 4 at (1,3) touches the shape at (0,1), (0,2) at a corner, so that shape has two markers.
- `unmarked-shape`
    - `concept`: undefined on a shape with no 4-adjacent marker (scene claim `one-marker-per-shape`)
    - `$UnmarkedKeeps`: adds a rule; a shape with no adjacent marker keeps `shape_color`; this is the reading of a marker that floods its color through the shape it touches. Fits every pair. Witness `unmarked-shape`: breaks `one-marker-per-shape`; plausibility `borderline`, verdict `$UnmarkedKeeps`; breaks the invariant that every shape touches a marker.
    - `$NearestMarker`: adds a rule; a shape with no adjacent marker takes the color of the marker nearest it by 4-step distance; undefined where no marker exists, or where the nearest markers have different colors. Fits every pair. Witness `unmarked-shape`: breaks `one-marker-per-shape`; plausibility `borderline`, verdict `$UnmarkedKeeps`; breaks the invariant that every shape touches a marker.
    - `$NearestMarker8`: as `$NearestMarker`, by 8-step distance. Fits every pair. Witness `nearest-metric`: breaks `one-marker-per-shape`; plausibility `borderline`, verdict `$UnmarkedKeeps`; breaks the invariant that every shape touches a marker.
- `several-marker-cells`
    - `concept`: undefined on a shape that touches more than one marker cell (scene claims `markers`, `one-marker-per-shape`)
    - `$MarkerUnanimous`: replaces `one-marker-per-shape`; a shape takes the one color of the marker cells it touches; undefined where those colors differ. Fits every pair. Witness `two-cell-marker`: breaks `markers` and `one-marker-per-shape`; plausibility `borderline`, verdict `$MarkerUnanimous`; breaks the invariant that every marker is a single cell, and that each shape touches one marker cell.
- `marker-erasure`
    - `concept`: every marker goes to background (`erase-markers`)
    - `$EraseTouchingOnly`: replaces `erase-markers`; only a marker that touches a shape goes to background. Fails Fit at train1: the marker 3 at (1,0) touches no shape and goes to 7.
    - `$KeepMarkers`: replaces `erase-markers`; markers keep their color. Fails Fit at train0: the markers at (0,3) and (1,3) go to 7.
- `background`
    - `concept`: stored, 7
    - `background=DominantColor`: replaces the stored value of `background` with the commonest color of the input; undefined where that commonest color is tied. Fits every pair. Witness `background=DominantColor`: plausibility `borderline`, verdict `concept`; breaks the invariant that background covers more than half of every input.
    - `background=SharedColor`, `background=RarestColor`, and the derivations that read `ex_out`: fail Fit at train0. On that input alone, `SharedColor` gives 7, 6, 3 and 4, and `RarestColor` gives 3 and 4. The derivations that read `ex_out` give no value, because `ex_out` is empty.
- `shape_color`
    - `concept`: stored, 6
    - `$ShapeColorCommonest`: replaces the stored value of `shape_color` with the commonest non-background color of the input; undefined where that color is tied. Fits every pair. Witness `single-cell-shape`: plausibility `borderline`, verdict `concept`; breaks the invariants that each shape has at least two cells and that the marker colors of an input are distinct.
    - `$ShapeColorMulticell`: replaces the stored value of `shape_color` with the one non-background color that has more than one cell; undefined where no such color or several such colors exist. Fits every pair, and fails Subsumption: where it is defined, its color is also the commonest non-background color, so `$ShapeColorCommonest` gives the same output. The two are not equivalent: where marker color 3 has two cells and 6 has four, it is undefined and `$ShapeColorCommonest` gives the concept output. Witness `single-cell-shape`: plausibility `borderline`, verdict `concept`.
    - `shape_color=SharedColor`, `shape_color=DominantColor`, `shape_color=RarestColor`, and the derivations that read `ex_out`: fail Fit at train0. On that input alone, they give 7, 6, 3 and 4; 7; 3 and 4; and no value.
- `shape-connectivity` & `contact-adjacency`, `shape-connectivity` & `unmarked-shape`, `shape-connectivity` & `several-marker-cells`, `shape-connectivity` & `marker-erasure`, `shape-connectivity` & `background`, `shape-connectivity` & `shape_color`, `contact-adjacency` & `unmarked-shape`, `contact-adjacency` & `several-marker-cells`, `contact-adjacency` & `marker-erasure`, `contact-adjacency` & `background`, `contact-adjacency` & `shape_color`, `unmarked-shape` & `several-marker-cells`, `unmarked-shape` & `marker-erasure`, `unmarked-shape` & `background`, `unmarked-shape` & `shape_color`, `several-marker-cells` & `marker-erasure`, `several-marker-cells` & `background`, `several-marker-cells` & `shape_color`, `marker-erasure` & `background`, `marker-erasure` & `shape_color`, `background` & `shape_color`: the two branches' changes applied together

## Open parameters
none

## Not formed
- `marker-touches-at-most-one-shape`: no rule reads it. A marker that touches two shapes gives its color to both under every reading, so no branch changes it.

## Tickets filed
none
