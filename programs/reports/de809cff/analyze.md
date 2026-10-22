# de809cff

## Concept
- The concept fits every pair, and the test through its main output (`check_concept.py`, `probe_witnesses.py`).
- No witness has verdict `other`. The concept file's rules are the rules as the generator applies them.
- The concept is undefined on two kinds of input: an input with other than two colors besides `background` and `mark_color`, and an input where rings of the two colors share a cell (`rings-apart`).

## Choice points
- `background-arity`
    - `concept`: one `background` value on each input, from the stored value or from `background=DominantColor`
        - `mark_color`
            - `concept`: stored `8`
                - `background`
                    - `concept`: stored `0`
                    - `background=DominantColor`: `background` is the input's commonest color; undefined where two colors tie for commonest; fails Fit at train0, where the commonest color is `3` (152 cells against 113 of `0`)
                - `foreign-cells`
                    - `concept`: a cell of a foreign color in a rectangle's visible part fills with the rectangle's color
                    - `$UnderColorHoles`: replaces `clean` at foreign cells and adds to `pinholes`: a cell of the color of a rectangle drawn beneath at that cell is a pinhole, and other foreign cells fill; undefined where the concept is; fits every pair, test0 through its `alt` (witness `under-color-stray`)
                    - `$ForeignHoles`: every foreign cell in a visible part is a pinhole; undefined where the concept is; fails Fit at train1 (7,7), a stray `2` in rectangle `1` that the output fills with `1`
                    - `$KeepForeignStrays`: a foreign cell in a visible part keeps its color; undefined where the concept is; fails Fit at train1 (7,7)
                - `background-pinholes`
                    - `concept`: every `background` cell of a rectangle's visible part is a pinhole
                    - `$NeighborHoles`: replaces `pinholes`: a `background` cell of a visible part is a pinhole when at least three of its 4-neighbors have the rectangle's color; undefined where the concept is; fits every pair (witness `corner-pinhole`)
                    - `$EnclosedHoles`: a `background` cell is a pinhole when the rectangle's color closes it off from the field and the frame edge; undefined where the concept is; fails Fit at train0 (0,3) and (3,12), edge pinholes that the output marks `8`
                - `attached-strays`
                    - `concept`: a stray that touches a rectangle's edge from outside becomes `background`
                    - `$KeepAttachedStrays`: such a stray keeps its color; undefined where the concept is; fails Fit at train1 (2,11)
                    - `$ComponentBbox`: replaces `clean`'s rectangle by the bounding box of the color's connected component, attached strays included; undefined where the concept is; fails Fit at train1 col 11 rows 0–10, which the output keeps `0`
                - `layer-order`
                    - `concept`: an overlap shows the rectangle the input shows on top there
                    - `$StoredLayerOrder`: a stored order of the colors gives the top rectangle of each overlap; undefined where the concept is; fails Fit at train0, where `4` is on top at rows 7–9, cols 6–12 and `3` is on top at rows 14–17, cols 6–9
                - `ring-color`
                    - `concept`: the other color of the two
                    - `ring_color=stored`: a stored map from the pinhole's rectangle color to the ring color; undefined where a pinhole's rectangle color is no key of the map; fails Fit at test0 (5,3): the train map holds `1 → 2`, and the output rings the pinholes of `1` with `6`, and `6` is a key no train pair holds
                    - `$OverlapRingColor`: replaces `ring`'s color: the color of the rectangles of another color that the pinhole's rectangle overlaps; undefined where that rectangle overlaps none, or overlaps rectangles of two other colors, and where rings of two colors share a cell; fits every pair (witness `four-colors`)
                - `ring-shape`
                    - `concept`: the full box of reach `ring_reach`
                    - `$CardinalRing`: the four cardinal neighbors only; undefined where the concept is; fails Fit at train0 (5,2), a diagonal neighbor of pinhole (6,3) that the output paints `4`
                - `ring-extent`
                    - `concept`: the ring paints over the field as well
                    - `$RingInsideRect`: the ring paints only cells inside a rectangle; undefined where the concept is; fails Fit at train0 (3,13), a field cell that the output paints `4`
                - `mark-order`
                    - `concept`: `mark_color` over every ring
                    - `$RingOverMark`: rings over the marks; undefined where the concept is; fails Fit at train0 (1,7), where the ring of pinhole (1,8) would cover the mark the output keeps
                - `ring-clash`
                    - `concept`: undefined where rings of the two colors share a cell
                    - `$OwnRingWins`: a shared cell takes the ring of the pinhole in the rectangle whose visible part holds the cell; undefined where a shared cell lies outside every rectangle; fits every pair (witness `ring-clash`)
                    - `$ForeignRingWins`: a shared cell takes the ring of the pinhole in the other rectangle; undefined where a shared cell lies outside every rectangle; fits every pair (witness `ring-clash`)
            - `mark_color=OutNewColor`: `mark_color` is a color in every train output and no input; an input alone has no train output, so the branch is undefined on every input; fails Fit at train0
            - `mark_color=AnyOutNewColor`: as `mark_color=OutNewColor`, undefined on every input; fails Fit at train0
    - `background=SharedColor`: `background` is each color of the input alone, so no color paints a rectangle and the branch is undefined on every input; fails Fit at train0
- `background` & `foreign-cells`, `foreign-cells` & `background-pinholes`, and each other two points under `mark_color`'s `concept`: the two branches' changes applied together

### Witnesses
- `under-color-stray` for `$UnderColorHoles`: a `2` in the overlap where `1` lies over `2`. It breaks no scene claim, plausibility `ordinary`, verdict `any`: test0 has two such cells, (9,20) and (19,8), and accepts both readings.
- `corner-pinhole` for `$NeighborHoles`: a pinhole at a rectangle's corner, with two cells of its rectangle beside it. It breaks no scene claim, plausibility `ordinary`, verdict `concept`.
- `ring-clash` for `$OwnRingWins` and `$ForeignRingWins`: pinholes of the two colors two columns apart across the colors' boundary. It breaks `rings-apart`, plausibility `borderline`, verdict `any`. The invariant it breaks: every pinhole in the evidence lies at least three cells from each pinhole of the other color, so no ring cell is near pinholes of both colors.
- `four-colors` for `$OverlapRingColor`: two separate overlapping pairs of rectangles, in four colors. It breaks `two-colors`, plausibility `borderline`, verdict `$OverlapRingColor`. The invariant it breaks: every input holds exactly two colors besides `background`.
- Each witness stands at the stored assignment.

## Open parameters
- none

## Not formed
- A pair of adjacent pinholes ringed as one unit, by the box around the pair: that box is the union of the two pinholes' boxes on every input, so the model is equivalent to the concept.
- A ring that skips the cells of the other color's rectangles: on every input where the concept is defined, those cells already have the ring color, and the model is undefined where the concept is, so it is equivalent to the concept.
- A derivation of `ring_reach`: no proposer derives it.

## Tickets filed
- `10-886_task_de809cff_analyze.md`
