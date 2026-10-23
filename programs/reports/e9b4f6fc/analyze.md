# e9b4f6fc

## Concept
- Fits every train pair and the test pair (probe `work/task/e9b4f6fc/analyze/check_concept.py`).
- Each rule has a relational form, and no witness has the verdict `other`.
- The concept is subsumed by `$PictureLargest`: on each input where the concept is defined, `$PictureLargest` gives the same output.

## Choice points
- `color-map-source`
    - `concept`: the keys in the input give the color mapping (`recolor-by-key`)
        - `key-reading`
            - `concept`: stored `new-side` = `DIR_L`; the old color is the key cell opposite `new-side` (`domino-keys`, `key-names-picture-color`)
            - `$KeyOldInPicture`: replaces `new-side` and the axis part of `domino-keys`. The old color of a key is derived as the key cell whose color the picture holds, and the new color as the other cell, on either axis. A key with neither color in the picture is ignored. Undefined where the picture holds both colors of a key. Fits every pair. Witness `key-old-in-picture` (train0 input mirrored left to right): it breaks `key-names-picture-color`, plausibility `variant`, verdict `$KeyOldInPicture`. It breaks the invariant that the right cell of each key holds a picture color.
    - `$StoredColorMap`: replaces `recolor-by-key` with a stored color-to-color table read from the train pairs (the ChangedPairs and VanishedNewPairs proposers give this table). Fails Fit at train3: train0 stores 4 → 1, and train3 output (0,1) shows 4 → 2. The test also has the unseen key 7.
- `picture-adjacency`
    - `concept`: the objects are 4-connected (`one-picture`, `domino-keys`)
    - `$Picture8Adjacent`: replaces the adjacency in `one-picture` and `domino-keys` with 8-adjacency. Undefined where the concept's conditions fail under 8-adjacency. Fits every pair. Witness `diagonal-key` (train2 input, with key `3 2` moved to (5,9), (5,10), diagonal to picture corner (4,8)): it breaks `domino-keys`, plausibility `borderline`, verdict `concept`. It breaks the invariant that every cell that touches a key, other than the key's own cells, is background.
- `picture-selection`
    - `concept`: the picture is the one object of more than two cells (`one-picture`)
    - `$PictureLargest`: replaces `one-picture` with "the picture is the largest object; the keys are the two-cell objects". Objects of other sizes are ignored. Undefined where no object has more than two cells, or where two objects tie for largest. Fits every pair. Witness `two-pictures` (train0 input with a 2x2 object `8 3 / 8 8` at rows 10–11, cols 0–1): it breaks `one-picture`, plausibility `foreign`, verdict `$PictureLargest`. It breaks the invariant that each input has one object of more than two cells.
- `recolor-application`
    - `concept`: each cell is recolored once, by the key of its own color (`recolor-by-key`)
    - `$RecolorTransitive`: replaces `recolor-by-key` with "a cell follows the chain of keys from its color until no key applies, stopping at a repeated color". Same undefined inputs as the concept. Fits every pair. Witness `chained-keys` (train0 input with key `2 3` changed to `4 3`): it breaks `key-names-picture-color`, plausibility `borderline`, verdict `concept`. It breaks the invariant that no key's new color is a picture color.
- `background`
    - `concept`: stored `background` = `0`
    - `background=DominantColor`: derives the background as the commonest color of the input. Undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor` (train0 input with 0 and 8 exchanged): it breaks `background`, plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that every cell outside the objects is 0.
    - `background=SharedColor`: fails Fit at train0. On one input, SharedColor gives every color of that input, and a value other than 0 gives an output other than the train output.
- `color-map-source` & `key-reading`: the model of `$StoredColorMap` alone, so `key-reading` stands under the concept branch of `color-map-source`
- `key-reading` & `picture-adjacency`, `key-reading` & `picture-selection`, `key-reading` & `recolor-application`, `key-reading` & `background`, `color-map-source` & `picture-adjacency`, `color-map-source` & `picture-selection`, `color-map-source` & `recolor-application`, `color-map-source` & `background`, `picture-adjacency` & `picture-selection`, `picture-adjacency` & `recolor-application`, `picture-adjacency` & `background`, `picture-selection` & `recolor-application`, `picture-selection` & `background`, `recolor-application` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Keep the input's frame in place of `crop-picture`: each train output has the size of the picture's bounding box, which is smaller than its input, so this reading fails Fit at every pair and gives no model the pairs leave open.
- `background=RarestColor`: the rarest color of every input is a drawing or key color, never the background, so this derivation fails Fit at every pair.
- Two keys that give one old color two new colors: the concept is undefined there. A pick between the two new colors is a tiebreak that no pair shows, and no claim of the scene allows such keys.
- Keys whose old color the picture does not hold: the concept ignores them, and no other reading changes the output, because the cut-out holds only picture colors.

## Tickets filed
- none
