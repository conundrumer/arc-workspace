# b775ac94

## Concept
- The concept case fits every train pair and the test pair (`check_concept.py`, `probe.py`). Every rule has a relational form, and no witness has the verdict `other`.
- Every object in the pairs has two or three markers, so the key block is always fixed by its markers. Every key cell is a corner of its shape's bounding box, and no copy lands on another object.

## Choice points
- `side-copy-transform`
    - `concept`: a marker beside the key cell takes the reflection across the key block's center line between the key cell and that marker
    - `$SideTurn`: replaces `mirror-copy` for a marker beside the key cell with the quarter turn about the key block's center that takes the key cell to the marker. It has no parameters, and it is undefined only where the concept is undefined. It fails Fit at train0 (and at every other pair).
- `diagonal-copy-transform`
    - `concept`: the diagonal marker takes the half turn about the key block's center
    - `$DiagTranspose`: replaces `mirror-copy` for the diagonal marker with the reflection across the key block's diagonal that does not hold the key cell. It has no parameters, and it is undefined only where the concept is undefined. It fails Fit at train0 (and at every other pair).
- `copy-transform-source`
    - `concept`: the transform of each copy is derived from the key cell's and the marker's places in the key block (`mirror-copy`)
    - `quadrant_op=stored`: replaces the derivation in `mirror-copy` with a stored lookup table `quadrant_op(key_corner: DiagDir, marker_corner: DiagDir, op: D4)`, which holds the eight rows the train pairs show (`quadrant_op_stored.json`). It is undefined on an input with a key-corner and marker-corner pair the table lacks (for example, a key cell at the key block's top-right corner). It fits every pair, because each test row is in the table. Witness `quadrant_op=stored`: it stands at the table whose four side rows are quarter turns (`D4_CW`, `D4_CC`), and the branch's model is defined there. It breaks no scene claim. Plausibility `variant`, verdict `quadrant_op=stored`. It breaks no invariant of the inputs: the witness's input is ordinary, and the assignment is that of a variant task whose side copies turn.
- `shape-cells`
    - `concept`: the shape is the cells of the shape's color in its 8-connected object
    - `$Adjacency4`: replaces `shapes` with "the shape is the 4-connected component of the key cell's color that holds the key cell". It is a program on another adjacency type. It fails Fit at train0, where cell (15,5) of the color-1 shape joins the shape only at a corner. It fails train2 for the same reason: the color-8 block at rows 1–2 reaches the key cell (3,9) only at a corner.
    - `$ColorClass`: replaces `shapes` with "the shape is every cell of the key cell's color in the grid". It fails Fit at train0: marker (9,17) of color 1 joins the color-1 shape, and marker (11,6) of color 3 joins the color-3 shape. It is undefined at test0, where two copies conflict at (6,9).
- `copy-on-object`
    - `concept`: `keep`, so an input cell that is not background keeps its color under a copy
    - `$CopyOver`: replaces `keep` with "a copy cell replaces the input cell it lands on". It has no parameters, and it is undefined only where two copies of different colors meet, as the concept is. It fits every pair. Witness `copy-over-object`: it breaks `room` and stands at the stored assignment. Plausibility `borderline`, verdict `any`. The invariant of the inputs it breaks: in every input, each copy covers only background cells and its own marker.
- `background`
    - `concept`: stored `0`
    - `background=DominantColor`: derives `background` as the commonest color of the input. It is undefined on an input where two colors tie for the commonest. It fits every pair. Witness `background=DominantColor`: it breaks `shapes`, because with background 0 the field of 5 joins every cell into one object. It stands at the stored assignment. Plausibility `variant`, verdict `background=DominantColor`. The invariant of the inputs it breaks: every input has background 0.
- `side-copy-transform` & `diagonal-copy-transform`, `side-copy-transform` & `shape-cells`, `side-copy-transform` & `copy-on-object`, `side-copy-transform` & `background`, `diagonal-copy-transform` & `shape-cells`, `diagonal-copy-transform` & `copy-on-object`, `diagonal-copy-transform` & `background`, `copy-transform-source` & `shape-cells`, `copy-transform-source` & `copy-on-object`, `copy-transform-source` & `background`, `shape-cells` & `copy-on-object`, `shape-cells` & `background`, `copy-on-object` & `background`: the two branches' changes applied together
- `copy-transform-source` & `side-copy-transform`: the model of `quadrant_op=stored` alone. The table gives every copy's transform, so the property of `side-copy-transform` exists only with the concept branch of `copy-transform-source`, which the concept claims take.
- `copy-transform-source` & `diagonal-copy-transform`: the model of `quadrant_op=stored` alone, for the same reason

## Open parameters
- none

## Not formed
- A copy in a quadrant with no marker (completing the four-fold figure): the train0 object at rows 21–24 and both train2 objects leave their unmarked quadrant empty, and no reading gives a color for that copy.
- A copy color other than its marker's: the shape's color fails every pair. A stored map from a marker's direction to a color fails train0, where the marker above the key cell is 3 in one object and 2 in another.
- A mirror line through the key cell, which would put the key cell's image on the key cell itself: in every pair the marker cell is the place of the key cell's image, and no reader of the concept takes this line.
- A copy that runs past the grid edge: under the `room` claim no reading other than dropping the cells off the grid gives an output.
- Two copies of different colors that meet at one cell: every case is undefined there, and the pairs show no order between objects.
- `background` by the other proposers: `SharedColor` gives every color of an input, and `RarestColor` gives a marker color. `UnchangedColor` and `ChangedColor` read `ex_out`, which is empty in a run, so they give no value. Each one fails Fit at train0.
- Markers found as the object's minority-color cells, or as the key block's other cells: the two parses agree on every input where `key-block` and `marker-colors` hold. Where a marker has its shape's color, it merges into the shape under both parses.

## Tickets filed
- none
