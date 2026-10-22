# b74ca5d1

## Concept
- The concept case fits every train and test pair at `box-size` 5 (`probe_models.py`).
- No witness has verdict `other`, and the concept file's rules have relational form and need no approximation.
- Every choice point stands at the concept. `box-size` is read by the concept's key pairing, and also by `$ShapeBySpread`, `$KeyWithoutMarker`, `$StampAlignCenter` and `$MarkerCleared`.

## Choice points
- `shape-grouping`
    - `concept`: a shape is every cell of one non-marker color (`shapes`)
    - `$ShapeByComponent`: replaces `shapes`: a shape is one 8-connected component of a non-marker color; no parameter; undefined where a key fits with several components or a component gets no key. Fails Fit at train0: shape 0 splits into components, and key 5 at (12,17) fits with two of them.
    - `$ShapeBySpread`: replaces `shapes`: a shape is the cells of one non-marker color that are linked by steps of Chebyshev distance less than `box-size`; reads `box-size`; undefined where a shape has no key or several keys. Fits every pair. Witness `repeated-shape-color`: two far-apart shapes share color 3, keyed 4 and 6. The concept reads one keyless shape and is undefined, and the branch swaps and stamps each shape. Breaks `shapes`; stored assignment; `variant`, verdict `$ShapeBySpread`; invariant broken: no two shapes of an input share a color.
- `key-identity`
    - `concept`: a key is a cell of a corner marker's color (`key-cell`)
    - `$KeyWithoutMarker`: replaces `key-cell`: a key is a non-background cell off the corners with no other cell of its color at Chebyshev distance less than `box-size`, whatever its color. A shape whose key color is on no corner swaps colors and stamps nowhere. Reads `box-size`; undefined where a shape has no key or several keys. Fits every pair. Witness `key-without-marker`: shape 2 holds a key of color 7, and no corner holds 7. The concept reads the 7 cell as a keyless shape and is undefined, and the branch swaps 2 and 7. Breaks `key-cell` and `shapes`; stored assignment; `borderline`, verdict `$KeyWithoutMarker`; invariant broken: every key's color is a corner marker's color.
- `key-pairing`
    - `concept`: a key belongs to the shape whose cells fit with it in a `box-size` × `box-size` box (`key-cell`)
    - `$KeyByNearest`: replaces the pairing in `key-cell`: a key belongs to the shape with the cell nearest to it by Chebyshev distance; reads no parameter; undefined where two shapes tie for nearest, or a shape gets no key or several keys. Fits every pair. Witness `key-near-other-shape`: key 4 is in the box of shape 3 and two cells from shape 2, and key 6 is in the box of shape 2 and two cells from shape 3. The concept pairs each key with the shape whose box holds it, and the branch crosses the keys. Breaks no scene claim; stored assignment; `borderline`, verdict `concept`; invariant broken: the shape boxes of an input are at least 3 cells apart, and in this witness two boxes touch.
- `box-size`
    - `concept`: stored, 5
    - `$BoxSizeFromShapes`: derives `box-size` in place of the stored value, as the largest extent on either axis of the cells of one non-marker color, on each input alone; undefined on an input with no non-marker color off the corners. Fits every pair. Witness `larger-shapes`: both shapes span 6×6 with their keys. At 5, the concept fits no key with its shape and is undefined. The branch derives 6, and swaps and stamps both 6×6 boxes. `$KeyByNearest` gives the same output. Breaks `shape-box`; stored assignment; `variant`, verdict `$BoxSizeFromShapes`; invariant broken: every shape spans 5×5 with its key.
- `stamp-content`
    - `concept`: the stamp holds the shape cells and the key cell (`stamp-corner`)
    - `$StampWithoutKey`: replaces `stamp-corner`'s content: the stamp holds the shape cells alone; no parameter; undefined where the concept is. Fails Fit at train0: output (1,28) is 5, at the place of shape 0's key, and the branch leaves it 2.
- `stamp-combine`
    - `concept`: a stamp cell is painted where any keyed box covers it (`stamp-corner`)
    - `$StampXor`: replaces `stamp-corner`'s overlay: a stamp cell is painted where an odd number of keyed boxes cover it; no parameter; undefined where the concept is. Fails Fit at train0: output (0,2) is 9, and shapes 3 and 6 both cover it.
- `stamp-alignment`
    - `concept`: each keyed box lies flush against its corner (`stamp-corner`)
    - `$StampAlignCenter`: replaces `stamp-corner`'s placement: each keyed box is centered in the `box-size` × `box-size` box at its corner; reads `box-size`; undefined where a box's extent and `box-size` differ in parity. Fits every pair. Witness `small-shape`: shape 3 spans 3×3 with its key and is keyed to the top-left corner. The concept stamps it at rows 0–2, cols 0–2, and the branch stamps it at rows 1–3, cols 1–3. Breaks `shape-box`; stored assignment; `borderline`, verdict `concept`; invariant broken: every shape spans 5×5 with its key.
    - `$StampAlignKey`: replaces `stamp-corner`'s placement: the keyed boxes are aligned on their key cells, and the overlay's bounding box lies flush against the corner; no parameter; undefined where the concept is. Fails Fit at train0: the keys of shapes 4 and 0 sit at (3,3) and (1,3) in their boxes, and the branch paints (0,27) and (0,28) differently from the output.
- `marker-fate`
    - `concept`: a corner cell the stamp misses keeps its marker (`rest-kept`)
    - `$MarkerCleared`: replaces `rest-kept` in the corner boxes: the `box-size` × `box-size` box at each marked corner turns background before the stamp is painted; reads `box-size`; undefined where the concept is. Fits every pair. Witness `uncovered-corner`: a plus keyed to the top-left corner misses the corner cell. The concept keeps 4 at (0,0), and the branch turns it to background. Breaks no scene claim; stored assignment; `ordinary`, verdict `concept`.
- `key-cell-color`
    - `concept`: the key cell takes the shape's color (`swap-colors`)
    - `$KeyKeepsColor`: replaces `swap-colors`: the key cell keeps its own color; no parameter; undefined where the concept is. Fails Fit at train0: output (6,14) is 4, and the branch leaves 5.
- `shape-grouping` & `key-identity`, `shape-grouping` & `key-pairing`, `shape-grouping` & `box-size`, `shape-grouping` & `stamp-content`, `shape-grouping` & `stamp-combine`, `shape-grouping` & `stamp-alignment`, `shape-grouping` & `marker-fate`, `shape-grouping` & `key-cell-color`, `key-identity` & `key-pairing`, `key-identity` & `box-size`, `key-identity` & `stamp-content`, `key-identity` & `stamp-combine`, `key-identity` & `stamp-alignment`, `key-identity` & `marker-fate`, `key-identity` & `key-cell-color`, `key-pairing` & `stamp-content`, `key-pairing` & `stamp-combine`, `key-pairing` & `stamp-alignment`, `key-pairing` & `marker-fate`, `key-pairing` & `key-cell-color`, `box-size` & `stamp-content`, `box-size` & `stamp-combine`, `box-size` & `stamp-alignment`, `box-size` & `marker-fate`, `box-size` & `key-cell-color`, `stamp-content` & `stamp-combine`, `stamp-content` & `stamp-alignment`, `stamp-content` & `marker-fate`, `stamp-content` & `key-cell-color`, `stamp-combine` & `stamp-alignment`, `stamp-combine` & `marker-fate`, `stamp-combine` & `key-cell-color`, `stamp-alignment` & `marker-fate`, `stamp-alignment` & `key-cell-color`, `marker-fate` & `key-cell-color`: the two branches' changes applied together
- `key-pairing` & `box-size`: the two branches' changes applied together, where a branch at another point reads `box-size` (`$ShapeBySpread`, `$KeyWithoutMarker`, `$StampAlignCenter`, `$MarkerCleared`)
    - `$KeyByNearest` & `$BoxSizeFromShapes`: the model of `$KeyByNearest`, because no other part of the model reads `box-size` when every other point takes its concept branch

## Open parameters
- none

## Not formed
- A stored background color: the background is 2, 4 and 8 in the three train pairs, so no stored value fits. The concept reads it on each input.
- A stored map from key color to corner: the marker colors and the marked corners differ in each pair, so no stored value fits. The concept matches each key to the marker of the same color on each input.
- Shapes as 4-connected components: such a component lies inside one 8-connected component, so 4-connectivity splits shape 0 of train0 at least as finely, and key 5 at (12,17) still fits with more than one part. It fails Fit at train0, as `$ShapeByComponent` does.

## Tickets filed
- none
