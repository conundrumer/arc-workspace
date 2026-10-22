# c6141b15

## Concept
- Fits every pair (`check_concept.py`, `probe.py`). Each rule has a relational form, and no witness has the verdict `other`.
- The parse reads the line as the one object of the color that forms one 8-connected object, and the copies as the objects of the color that forms two or more. A copy's center is its bounding-box center.
- The concept is undefined where some two centers share no row, column, or diagonal, where only one copy is present, and where the field is not `bg`.

## Choice points
- `line-parse`
    - `concept`: the line is the one object of the color that forms exactly one object, and the copies are the objects of the color that forms two or more.
    - `$LineByStraightness`: replaces the parse in `one-line` and `shape-copies`. The line is the one object that is a straight run of two or more cells, and the copies are the objects of the other color, one or more. It is undefined where no object or more than one object is such a run, for example where the copies are 1×3 bars. It fits every pair. Its witness is `one-copy`: one plus beside a line, so it breaks `shape-copies`. That witness stands at the stored assignment, with plausibility `borderline` and verdict `$LineByStraightness`. It breaks the invariant that every input holds two or three copies.
    - `$LineIsLargest`: the line is the object with the most cells, and the copies are the objects of the other color. It fails Fit at test0: the three I-shaped copies have 11 cells each, so they tie as largest.
- `adjacency`
    - `concept`: objects are 8-connected.
    - `$Adjacency4`: objects are 4-connected. It fails Fit at train0: the diagonal line splits into single cells.
- `joined-centers`
    - `concept`: a line joins every two centers. It is undefined where some two centers share no row, column, or diagonal.
    - `$JoinAligned`: replaces `aligned-centers` and `lines-join-centers`. A line joins each two centers that share a row, column, or diagonal, and no other two. It fits every pair. Its witness is `unaligned-centers`: centers at (2,2), (2,8), and (6,2), so it breaks `aligned-centers`. That witness stands at the stored assignment, with plausibility `foreign` and verdict `$JoinAligned`. It breaks the invariant that every two centers in an input share a row, column, or diagonal.
    - `$JoinChain`: each center joins the next one in row-major order. It fails Fit at train0. Any order of three centers draws two sides of the triangle, and train0 draws all three.
- `layer-order`
    - `concept`: where a stamp and a joining line meet, the stamp is drawn over the line.
    - `$LinesOverStamps`: the joining lines are drawn over the stamps. It fits every pair. Its witness is `stamp-meets-line`: a stamp at a line end reaches (2,6), which is on the line between the centers. It breaks no scene claim. It stands at the stored assignment, with plausibility `borderline` and verdict `any`. It breaks the invariant that each end of the line lies more than a stamp's reach from every segment between two centers.
- `bg`
    - `concept`: stored, 7.
    - `bg=DominantColor`: on each input, the background is that input's commonest color. It fits every pair. Its witness is `bg=DominantColor`: the train1 input on a field of 3, so it breaks `background`. That witness stands at the stored assignment, with plausibility `variant` and verdict `bg=DominantColor`. It breaks the invariant that every input's field is 7.
    - `bg=SharedColor`: on one input, the derivation gives every color of that input. Every cell is then background, no line is found, and the model is undefined. It fails Fit at train0.
- `line-parse` & `adjacency`, `line-parse` & `joined-centers`, `line-parse` & `layer-order`, `line-parse` & `bg`, `adjacency` & `joined-centers`, `adjacency` & `layer-order`, `adjacency` & `bg`, `joined-centers` & `layer-order`, `joined-centers` & `bg`, `layer-order` & `bg`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A closed polygon through the centers in hull order: the order reads an angle about a centroid, which has no relational form. With two or three centers it draws the same lines as joining every two centers.
- A copy turned to follow the line's direction: no pair shows a turned copy. Every train shape is unchanged under D4, so train fixes no turn. Test0 keeps the I shape upright where the line is horizontal.
- Stored line and stamp colors: the two colors change from pair to pair, and test0 swaps the two colors of train0. Each output color comes from its input object.
- A copy anchored at its center of mass: a center of mass counts nothing the task has. On copies whose bounding box has odd extents, as the scene states, the bounding-box center is the one center cell.
- Stamps at every line cell, or one stamp for each copy: train0 has three copies and a line of six cells, and its output has exactly two stamps, one at each line end.

## Tickets filed
- none
