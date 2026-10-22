# 4c7dc4dd

## Concept
- The concept case fits every pair, train and test, on the box layout the probe (`probe.py`) names.
- Each pair uses a different member of the repertoire. `connect` shows in train 0, `invert` in train 1 and test 0, and `mirror-fill` in test 1 only. A repertoire read from the train pairs alone fails Fit on test 1.
- The generator's rule is "apply to the query picture whatever transformation the demo shows". The concept's fixed repertoire approximates that rule, and the approximation is undefined wherever the demo shows a transformation outside the repertoire.
    - `dropped-demo`: in train 1, the demo target is replaced by its source with each column dropped to the bottom. That breaks `repertoire`, and every case is undefined. Plausibility `variant`, verdict `other`; the judged output is the query picture dropped the same way:

        ```
        0 0 0 0
        0 0 2 0
        0 2 2 0
        2 2 2 0
        ```

## Choice points
- `link`: how the output is obtained from the demo
    - `concept`: the repertoire member that maps one demo picture onto the other, applied to the query picture
        - `recolor fallback`
            - `concept`: none
            - `$RecolorAnalogy`: adds a recolor link. When the query picture recolors a demo picture, the output also holds the other demo picture under that recoloring. This branch fits every pair.
                - Witness `unrelated-demo-recolored-query`: in test 0, the demo target is replaced by a ring of 8 that no member makes of the plus. That breaks `repertoire`. Plausibility `variant`, verdict `$RecolorAnalogy`; the invariant it breaks is that the demo pictures are related by a repertoire member.
        - `d4 member`
            - `concept`: the repertoire holds `connect`, `invert` and `mirror-fill`
            - `$D4Repertoire`: adds the eight D4 transforms to `repertoire`. This branch fits every pair.
                - Witness `mirrored-demo`: in train 1, the demo target is replaced by its source mirrored left to right. That breaks `repertoire`. Plausibility `variant`, verdict `$D4Repertoire`; the invariant it breaks is that the demo pictures are related by a repertoire member.
                - A demo related by a quarter turn holds in both directions, once as the turn and once as its inverse. Under the concept `roles`, this branch then gives two outputs.
        - `line color`: the color of a `connect` line
            - `concept`: the one non-`anchor` mark color of the picture
            - `$LineFrameColor`: replaces `connect`'s color with the frame color of the picture's panel. It reads no `anchor` unless it is combined with `$AnchorEndsOnly`. This branch fits every pair.
                - Witness `frame-color-line`: in train 0, the query panel's frame is recolored 7. Plausibility `ordinary`, verdict `concept`.
        - `line ends`: which aligned mark pairs `connect` joins
            - `concept`: every pair of marks on one row or column
            - `$AnchorEndsOnly`: replaces `connect`'s pairs with those that have an `anchor` mark at one end. This branch fits every pair.
                - Witness `unanchored-pair`: in train 0, a 2 is added at the query picture's (4,4). Plausibility `ordinary`, verdict `concept`.
        - `anchor`
            - `concept`: stored, 6
            - `anchor=RarestColor`: the rarest color of the input alone. Where colors tie for rarest, `connect` is undefined. This branch fits every pair.
                - Witness `anchor-recolored`: in train 0, every 6 is recolored 7. Plausibility `variant`, verdict `anchor=RarestColor`. That output is also the output of `$AnchorShared` and `$LineFrameColor`, and the concept case is undefined. The invariant it breaks is that the anchor is 6 in the one input that shows it.
                - Witness `stray-rare-color`: in train 0, one stray 7 sits in the clutter. Plausibility `ordinary`, verdict `concept`. This branch is undefined there.
            - `$AnchorShared`: the one non-background color found in both demo pictures and the query picture. Where there is not exactly one such color, `connect` is undefined. This branch fits every pair.
                - Witness `anchor-recolored`: plausibility `variant`, verdict `anchor=RarestColor`, which gives this branch's output.
                - Witness `shared-mark-color`: in train 0, the query marks are recolored 1. Plausibility `ordinary`, verdict `concept`. This branch is undefined there.
        - `quarter completion`: how `mirror-fill` copies the quarter
            - `concept`: mirrored on both axes
            - `$MirrorD4`: replaces it with every D4 image, so the quarter is also mirrored across its diagonals. This branch fits every pair.
                - Witness `skew-quarter`: in test 1, the query quarter has an 8 off its diagonal. Plausibility `variant`, verdict `concept`; the invariant it breaks is that each quarter picture is symmetric about its corner's diagonal.
            - `$RotateC4`: replaces it with the four rotations. It is undefined where a rotated cell lands on a different mark. This branch fits every pair.
                - Witness `skew-quarter`: plausibility `variant`, verdict `concept`, as above.
        - `fill`: what `mirror-fill` floods
            - `concept`: the source's cells of the box outline color flood that color over the background cells they reach
            - `$FillEnclosed`: replaces the flood. The background region holding the box's center cells is filled with the box outline color. This branch fits every pair.
                - Witness `unseeded-quarter`: in test 1, the query quarter's 6 is removed. Plausibility `variant`, verdict `$FillEnclosed`; the invariant it breaks is that every quarter picture holds a cell of the box outline color.
        - `invert color`: the color an `invert` cell takes
            - `concept`: the color that the cell's parity carries among the source's marks
            - `$InvertMono`: replaces it with the source's commonest mark color. This branch fails Fit on test 0.
    - `$RecolorCopy`: replaces `repertoire`, `pick` and `apply` with the recolor link alone. It is undefined where the query picture recolors no demo picture, and it fails Fit on train 0.
- `roles`: which demo picture is the source
    - `concept`: the one from which a repertoire member gives the other
    - `$PositionalRoles`: replaces `pick`'s direction. The demo box at the empty box's place within its panel is the target. This branch fails Fit on train 0.
- `box_background`
    - `concept`: stored, 0
    - `$BackgroundFromEmptyBox`: derived as the one color of the one box whose interior is a single color. Where there is not exactly one such box, every rule is undefined. This branch fits every pair.
        - Witness `recolored-background`: in train 1, 0 and 9 are swapped throughout. Plausibility `variant`, verdict `$BackgroundFromEmptyBox`; the invariant it breaks is that the box background is 0 in every input.
- `link` & `roles`, `link` & `box_background`, `roles` & `box_background`, and, under the concept branch of `link`, each two of `recolor fallback`, `d4 member`, `line color`, `line ends`, `anchor`, `quarter completion`, `fill`, `invert color` other than `line color` & `anchor`, and each of these with `roles` and with `box_background`: the two branches' changes applied together
- `line color` & `anchor`: `$LineFrameColor` with an anchor derivation gives `$LineFrameColor`'s model alone, because no rule reads the anchor when lines take the frame color and every aligned pair is joined
    - `$LineFrameColor` & `$AnchorEndsOnly` & an anchor derivation: the three changes applied together, because the line ends read the anchor

## Open parameters
- none

## Not formed
- Pairing a panel's boxes by row or column alignment in place of by frame: in test 0, box I is aligned by rows with box K and by columns with box J, so the pairing is undefined there.
- A repertoire with fewer members: dropping a member fails Fit on the pair that uses it (`connect` on train 0, `invert` on train 1 and test 0, `mirror-fill` on test 1).
- The sparser demo picture as the source: over the repertoire this gives the concept's model. `connect` and `mirror-fill` only add marks, and `invert` is an involution.
- Parity in `invert` counted in input coordinates in place of box coordinates: this gives one model, because the parity colors are read off the picture that is inverted.
- Joining only consecutive aligned marks in `connect`: this gives the concept's model, because the background cells between any two aligned marks are those between the consecutive marks along that line.
- The line color as the demo's line color carried over by a demo-to-query color correspondence: in train 0 no recoloring takes a demo picture to the query picture, so the correspondence is undefined there.
- Readings of the clutter: no rule reads the field outside the boxes.

## Tickets filed
- none
