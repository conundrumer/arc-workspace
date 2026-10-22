# d4f3cd78

## Concept
- The concept case fits every pair: the probe `probe.py` reproduces train0, train1 and test0 exactly.
- "Inside the outline" is read as the cells strictly inside the bounding box of the `wall_color` cells, and a gap is a non-corner cell of that box's border that is not `wall_color`. The stream runs from each gap, so the concept is defined on a box with several gaps.
- No witness has the verdict `other`. The rules have a relational form, so nothing is approximated.
- The concept is not the verdict on `interior-object`, `stream-obstacle` and `two-boxes`. Each of these breaks `one-walled-box`.

## Choice points
- `interior`: which cells the water fills, and where the gaps are
    - `concept`: the cells strictly inside the bounding box of all `wall_color` cells; gaps are the non-wall, non-corner cells on that box's border.
    - `$EachObject`: replaces `fill-interior`, `fill-gap` and `stream-out` so that they run once per 4-connected component of `wall_color` cells, each with its own bounding box. Parameters: `wall_color`, `fill_color`. Defined on every input. Fits every pair. Witness `two-boxes` (two boxes, each with one gap) breaks `one-walled-box` (one outline); it stands at the stored assignment; plausibility `variant`, verdict `$EachObject`. Breaks the input invariant that there is one outline (292dd178 is a variant task with several outlines).
    - `$SealedRegion`: replaces `fill-interior` and `fill-gap`. The interior is the set of non-wall cells that no walk reaches from the grid edge once one non-wall cell, the gap, is sealed. The stream leaves the gap away from its one interior neighbor. Parameters: `wall_color`, `fill_color`. Where no single sealed cell closes a region, it paints nothing. Fits every pair. Witness `two-gaps` (one box with gaps at (7,4) and (4,7)) breaks `one-gap`; it stands at the stored assignment; plausibility `variant`, verdict `concept`. Breaks the input invariant that the outline lacks exactly one cell (551d5bf1 is a variant task with several gaps per outline).
- `obstacle`: what the fill does to a non-background, non-wall cell it covers
    - `concept`: overwrites it, in the interior and along the stream.
    - `$PaintBackgroundOnly`: replaces `fill-interior` and `stream-out` so that they paint `background` cells only and leave other cells as they are. The stream runs on to the edge. Adds the parameter `background`. Defined on every input. Fits every pair. Witness `interior-object` (a `2` at (4,4) inside the train0 box) breaks `one-walled-box` (empty interior); it stands at the stored assignment; plausibility `borderline`, verdict `$PaintBackgroundOnly`. Breaks the input invariant that the interior is empty.
        - `stream-stop`: where the stream ends
            - `concept`: at the grid edge, passing over obstacles.
            - `$StreamStops`: replaces `stream-out` so that the stream ends before the first non-`background` cell on its line. Fits every pair. Witness `stream-obstacle` (a `2` at (2,5) in the train1 stream's path) breaks `one-walled-box` (one outline on a field of `background`); it stands at the stored assignment; plausibility `borderline`, verdict `$StreamStops`. Breaks the input invariant that nothing but the outline stands on the field.
        - `background`: how `background` gets its value
            - `concept`: stored, 0.
            - `background=DominantColor`: the commonest color of the input. Undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor` (the train0 input on a field of 1) breaks `one-walled-box` at `background` 0; it stands at the stored assignment; plausibility `variant`, verdict `concept`, and the branch's model gives that output. Breaks the input invariant that the field is 0.
            - `background=SharedColor`: gives both 0 and 5 on one input; at 5 it paints nothing, so it fails Fit at train0.
- `wall_color`: how `wall_color` gets its value
    - `concept`: stored, 5.
    - `wall_color=RarestColor`: the least common color of the input. Undefined where two colors tie for least common. Fits every pair. Witness `wall_color=RarestColor` (the train0 input with the box in 3) breaks `one-walled-box` at `wall_color` 5; it stands at the stored assignment; plausibility `variant`, verdict `wall_color=RarestColor`. Breaks the input invariant that the outline is 5.
    - `wall_color=DominantColor`: gives 0, and the model fills the 8×8 inner frame of the grid. Fails Fit at train0.
    - `wall_color=SharedColor`: gives 0 and 5, and the grid at 0 is wrong. Fails Fit at train0.
- `fill_color`: how `fill_color` gets its value
    - `concept`: stored, 8.
    - `fill_color=OutNewColor`, `fill_color=AnyOutNewColor`: these read `ex_out`, which is empty on a single input, so they give no value. Each fails Fit at train0.
- `interior` & `obstacle`, `interior` & `wall_color`, `obstacle` & `wall_color`, `interior` & `stream-stop`, `interior` & `background`, `wall_color` & `stream-stop`, `wall_color` & `background`, `stream-stop` & `background`, and each pair with `fill_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stream in one fixed direction, such as downward: the pairs separate it, because the stream runs down in train0, up in train1 and right in test0.
- A stream that steps out of the gap and then turns toward the wall's longer arm (4e469f39): the pairs separate it, because the train0 gap at col 5 has arms of 3 and 2 cells and the stream runs straight.
- Diagonal rays from the ends of the opening (aba27056): the pairs separate it, because no output has a diagonal fill.
- A band as wide as a multi-cell opening: the concept already streams from each gap cell, so this gives the concept's model.
- A gap at a corner: no reading of the pairs gives the stream a direction there. The concept skips corner cells as gaps, and no other model was formed.

## Tickets filed
- none
