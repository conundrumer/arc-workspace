# e4075551

## Concept
- Fits every pair (train0, train1, train2, test0). No witness has the verdict `other`. Every claim of the concept file has a relational form, and the rules are the rules as the generator applies them, with no approximation.

## Choice points
- `center identification`
    - `concept`: the center is the one dot of `center_color`.
    - `$CenterByPlace`: replaces `center-dot`; the center is the one dot that is extreme toward no side, and it keeps its own input color; it reads no `center_color`; undefined where some side has no unique extreme dot or where no single dot is extreme on no side. Fits every pair. Witness `center-not-2`: the test input with the inner dot recolored 8; it breaks `center-dot`; it stands at the stored assignment; plausibility `borderline`, verdict `$CenterByPlace`; it breaks the invariant of the inputs that the inner dot is 2 in every input.
    - `center_color=RarestColor`, `center_color=SharedColor`, `center_color=CountRankAsc`: on one input with `ex_out` empty, each gives several colors (all five dots tie at one cell each, and every color of the input is present), so the output holds more than one grid. Fails Fit at train0.
    - `center_color=DominantColor`: gives 0 on each input, and 0 is not the center's color. Fails Fit at train0.
- `background`
    - `concept`: `background` is stored as 0.
    - `background=DominantColor`: replaces the stored `background` with the commonest color of the input; undefined where the commonest color ties. Fits every pair. Witness `background=DominantColor`: train0's input with the field recolored 7; it breaks `five-dots` at the stored `background`; it stands at the stored assignment; plausibility `borderline`, verdict `background=DominantColor`; it breaks the invariant of the inputs that the field is 0 in every input.
- `cross_color`
    - `concept`: `cross_color` is stored as 5.
    - `cross_color=OutNewColor`, `cross_color=AnyOutNewColor`: with `ex_out` empty, each gives no value, so every case that takes it is undefined. Fails Fit at train0.
- `corner ownership`
    - `concept`: the two edges on `corner_axis` (top and bottom) take the corner cells.
    - `$CornerNearerDot`: replaces `frame`; each corner takes the color of the side dot nearer to it along its edge, with the edge on `corner_axis` on a tie. Fails Fit at train1: at (2,10) the right dot 7 is 3 cells away and the top dot 4 is 4 cells away, and the output holds 4.
- `center identification` & `background`, `center identification` & `cross_color`, `center identification` & `corner ownership`, `background` & `cross_color`, `background` & `corner ownership`, `cross_color` & `corner ownership`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `corner_axis` horizontal (left and right edges take the corners): the pairs separate it; every corner in every output holds the top or bottom dot's color.
- Cross drawn over the frame: the pairs separate it; train0 output (1,5) is 8, not 5.
- Cross spanning the whole grid in place of the box interior: the pairs separate it; train0 output (7,0) is 0.
- Box as the bounding box of all five dots: it differs from the concept only where the center dot is extreme on a side, and there it needs a color for a side whose extreme dot is the center, which no pair shows; no reading of the pairs gives that rule.
- `background` derivations other than `DominantColor`: `SharedColor` and `RarestColor` on one input give several colors or a dot color, and fail Fit at train0 in the same way as the `center_color` derivations.

## Tickets filed
- none
