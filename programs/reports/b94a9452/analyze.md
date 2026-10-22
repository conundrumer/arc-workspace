# b94a9452

## Concept
- Fits every pair: the object's box is the output, with its two colors exchanged. Each claim has a relational form, and no witness has the verdict `other`.

## Choice points
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: derives `background` as each input's commonest color, in place of the stored value in `one-object`; undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: a field of 5 holding a 2 square with a 4 core. It breaks `one-object`, stands at the stored assignment, plausibility `variant`, verdict `background=DominantColor`; it breaks the invariant that every input's field is 0, the commonest color.
    - `background=SharedColor`, `background=VanishedColor`: give every color of the input, so no cell is outside the background and the model is undefined. Fails Fit at train0.
    - `background=RarestColor`: gives the core color, so the box is the whole grid. Fails Fit at train0.
    - `background=OutNewColor`, `background=AnyOutNewColor`, `background=ChangedColor`, `background=UnchangedColor`: give no value on an input alone, so the model is undefined. Fails Fit at train0.
- `recolor`
    - `concept`: `swap-colors`, the object's two colors exchange
    - `$StoredMapping`: replaces `swap-colors` with a stored color-to-color table `color_map`. Fails Fit at train2: 4 maps to 2 in train0 and to 6 in train2. Test0's 8 is also a key that no train pair holds.
    - `$LayerReverse`: replaces `swap-colors`: the object's nested color regions, outermost first, take their colors in reverse order. Undefined where the cells around a region hold more than one color. Fits every pair. Witness `three-layers`: nested regions 2, 4, 2. It breaks `nested-squares`, stands at the stored assignment, plausibility `borderline`, verdict `concept`; it breaks the invariant that every object holds two nested regions.
    - `$LayerShiftOut`: replaces `swap-colors`: each nested color region takes the color of the region inside it, and the innermost takes the outermost's color. Undefined as `$LayerReverse` is. Fits every pair. Witness `three-layers`, as above.
    - `$LayerShiftIn`: replaces `swap-colors`: each nested color region takes the color of the region around it, and the outermost takes the innermost's color. Undefined as `$LayerReverse` is. Fits every pair. Witness `three-layers`, as above.
- `box-background`
    - `concept`: a background cell inside the object's box leaves the model undefined
    - `$KeepBackground`: adds that a background cell inside the box keeps the background color. Fits every pair. Witness `cut-corners`: a 2 square with a 4 core, its four corner cells background. It breaks `nested-squares`, stands at the stored assignment, plausibility `borderline`, verdict `$KeepBackground`; it breaks the invariant that every object fills its box.
- `background` & `recolor`, `background` & `box-background`, `recolor` & `box-background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The output keeps the input frame: the pairs separate it, since each output is the object's box.
- The object is one connected component, picked from several: every input holds one object, and the pairs give no way to pick one.
- The outer color is the color on the box's edge and the inner color the other one: wherever either reading is defined, both exchange the same two colors, so its model is the concept's.
- A one-color object stays unchanged: no reading of the pairs gives a swap partner for one color, and the layer branches already give the box unchanged there.

## Tickets filed
- none
