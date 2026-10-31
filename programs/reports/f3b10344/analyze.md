# f3b10344

## Concept
- Fits every train pair (probe `work/task/f3b10344/probe.py`). At test0 it gives one bridge more than the expected output: `8` at `test0 output (15,25)–(19,25)`, between the 3 rectangles at rows 10–14, cols 24–27 and rows 20–22, cols 24–26. Every other same-colored facing pair in the train pairs and in test0 is bridged. The search for a rule that drops that one bridge found none (gap length, bridge width, bridges per rectangle, lattice bands, a cycle among the four 3 rectangles), so the expected output is taken as an error in the task, logged in `progress-analyze.md`. Fit at test0 is judged against the concept's own output there.
- No witness has verdict `other`. Every rule has a relational form as written: spans, bands and colors are compared cell by cell, and no number is computed beyond the stored `inset`. So the concept file's rule is the rule as the generator applies it, with no approximation.
- The program reads `bridge_color` = 8, `inset` = 1 and `background` = 0. The pairs fix each one: no other value fits.

## Choice points
- `blocking-colors`: which cells in the band between a pair block it
    - `concept`: any non-`background` cell in the band blocks (`facing-pair`)
    - `$ThroughOtherColors`: replaces `facing-pair`: only a cell of the pair's own color in the band blocks, so a pair is two same-colored rectangles with no rectangle of their color between them. The bridge paints the band's `background` cells. Parameters: those of the concept. Defined wherever the concept is. Fits every pair. Witness `sandwiched-other-color` (two 4 rectangles in a column with a 6 rectangle between them): it breaks no scene claim and stands at the stored assignment; plausibility `ordinary`; verdict `concept`.
        - `obstacle-cells`: what the bridge does to another color's cells in its band
            - `concept`: keeps them (`keep-rest`)
            - `$PaintOver`: replaces `keep-rest`: the bridge overwrites every cell of its band, other-colored ones included. Parameters: those of the concept. Defined wherever the concept is. Fits every pair. Witness `sandwiched-other-color`: it breaks no scene claim and stands at the stored assignment; plausibility `ordinary`; verdict `concept`.
- `blocking-region`: the part of the band between a pair that must be clear
    - `concept`: the whole band over the shared span (`facing-pair`)
    - `$ClearBridgeOnly`: replaces `facing-pair`: only the cells the bridge would fill must be `background`. Parameters: those of the concept. Defined wherever the concept is. Fits every pair. Witness `edge-of-band-obstacle` (a 1×3 6 rectangle in the gap, on the first row of the shared span and outside the bridge's rows): it breaks no scene claim and stands at the stored assignment; plausibility `borderline`; verdict `concept`. It breaks this invariant of the inputs: a rectangle that enters the band between two same-colored facing rectangles crosses that band whole, as the middle 2 in train1 does.
- `bridge-span`: the span a bridge covers, and which pairs get one
    - `concept`: the shared span less `inset` at each end, for every facing pair (`bridge-band`)
    - `$NarrowerFace`: replaces `bridge-band`: the narrower face's span less `inset` at each end. Parameters: those of the concept. Defined wherever the concept is. Fits every pair, where every bridged pair's spans nest. Witness `partial-overlap` (facing 4 rectangles on rows 1–5 and rows 3–6): it breaks no scene claim and stands at the stored assignment; plausibility `ordinary`; verdict `concept`.
    - `$NestedOnly`: adds to `same-color-bridge`: a pair whose spans do not nest, neither holding the other, gets no bridge. Parameters: those of the concept. Defined wherever the concept is. Fits every pair. Witness `partial-overlap`: it breaks no scene claim and stands at the stored assignment; plausibility `ordinary`; verdict `concept`.
    - `$WiderFace`: replaces `bridge-band`: the wider face's span less `inset` at each end. Parameters: those of the concept. Defined wherever the concept is. Fails Fit at train1: between the 2 rectangles at rows 15–18, cols 4–9 and rows 21–24, cols 5–8, the output bridges cols 6–7 at rows 19–20, and `$WiderFace` paints cols 5–8 there.
    - `$EqualFacesOnly`: adds to `same-color-bridge`: only a pair whose two faces have one span gets a bridge. Parameters: those of the concept. Defined wherever the concept is. Fails Fit at train1: it leaves out the bridge at rows 19–20, cols 6–7 between the 2 rectangles at cols 4–9 and cols 5–8.
- `pair-colors`: which facing pairs are joined
    - `concept`: pairs of one color (`same-color-bridge`)
    - `$AnyColorPair`: replaces `same-color-bridge`: every facing pair is joined, whatever its colors. Parameters: those of the concept. Defined wherever the concept is. Fails Fit at train0: the 1 rectangle at rows 4–10, cols 3–9 and the 3 rectangle at rows 14–19, cols 7–11 face each other across a clear band, and it bridges them at col 8, rows 11–13, which the output leaves `0`.
- `background`: where the background color comes from
    - `concept`: stored, 0
    - `background=DominantColor`: replaces the stored `background`: on each input, the background is the commonest color of that input. Parameters: `bridge_color`, `inset`. Undefined on an input where two colors tie for commonest. Fits every pair. Witness `background=DominantColor` (two 4 rectangles cover all of a 7×7 grid but the 0 column between them): it breaks no scene claim and stands at the stored assignment; plausibility `borderline`; verdict `concept`. It breaks this invariant of the inputs: `background` is by far the commonest color of every input.
- `object-adjacency`: how an object's cells join
    - `concept`: 4-adjacency within one color (`solid-rectangles`)
    - `$Components8`: replaces `solid-rectangles`: an object is an 8-connected same-colored component, and facing and spans are read from its bounding box. Parameters: those of the concept. Defined wherever the concept is. Fits every pair. Witness `corner-touching` (a 4 rectangle touches a second at a corner and faces a third): it breaks `rectangles-apart` and stands at the stored assignment; plausibility `borderline`; verdict `concept`. It breaks this invariant of the inputs: no two rectangles touch, even at a corner.
- `blocking-colors` & `blocking-region`, `blocking-colors` & `bridge-span`, `blocking-colors` & `pair-colors`, `blocking-colors` & `background`, `blocking-colors` & `object-adjacency`, `blocking-region` & `bridge-span`, `blocking-region` & `pair-colors`, `blocking-region` & `background`, `blocking-region` & `object-adjacency`, `bridge-span` & `pair-colors`, `bridge-span` & `background`, `bridge-span` & `object-adjacency`, `pair-colors` & `background`, `pair-colors` & `object-adjacency`, `background` & `object-adjacency`, `obstacle-cells` & `blocking-region`, `obstacle-cells` & `bridge-span`, `obstacle-cells` & `pair-colors`, `obstacle-cells` & `background`, `obstacle-cells` & `object-adjacency`: the two branches' changes applied together. Under `$AnyColorPair` & `$ThroughOtherColors`, a cell blocks when it has the color of either rectangle of the pair.

## Open parameters
none

## Not formed
- `bridge_color` derived: 8 is in no input, so no proposer gives it from one input. `OutNewColor` reads the outputs, so it determines the stored value and is no branch.
- `inset` derived: nothing in an input gives it.
- Bridge over the overlap of the two rectangles' interiors (each less its rim): this is the concept at `inset` 1 with that value fixed in the program. A variant task can change it, so it is task data the program would fix.
- Objects as components of all non-`background` cells, of any color: where two colors touch, an object holds two colors and `same-color-bridge` has no color to compare. Nothing in the pairs gives such a rule.
- A minimum gap for a bridge: the test0 bridge at (3,4) spans a gap of one cell, and nothing in the train pairs suggests a bound.
- A rule that drops the test0 bridge at (15,25)–(19,25): dropping one edge of the cycle the four 3 rectangles form needs an order over the edges, and nothing gives one. No other rule found separates that pair from the bridged ones.

## Tickets filed
- none
