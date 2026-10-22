# b74ca5d1

## Departures
- The models of `$KeyWithoutMarker`, `$StampAlignCenter` and `$MarkerCleared` are not cases. Each takes `$ColorClass` and `$KeyInBox`, and the Analyze report lists them as branch models. The solver's `$ShapeBySpread` twin of each stands for the branch. These models fail Subsumption. A reading with `$ColorClass` and `$KeyInBox` is defined only where each color's cells fit in one box with their key. There those cells are pairwise near, so they spread into one shape, and the `$ShapeBySpread` twin gives the same output. The twin is also defined where a color splits into far-apart shapes (`repeated-shape-color`). Of the 16 readings that take `$ColorClass` and `$KeyInBox`, 11 leave this way. The concept case is exempt.
- The 8 readings that take `$ShapeBySpread`, `$MarkerColor` and `$BoxSizeFromShapes` are not cases. They fail Equivalence against their `$ColorClass` twins. The derived box-size is the widest extent of a non-marker color's cells, and under `$MarkerColor` the shape cells are exactly those cells. So every color fits in one box, the spread never splits a color, and the two groupings agree on every input. The `$ShapeBySpread` reading takes more non-concept branches, so it leaves. The 4 `$ColorClass` & `$KeyInBox` & `$BoxSizeFromShapes` readings stay, and one of them is the `$BoxSizeFromShapes` model.
- `[$ColorClass, $MarkerColor, $KeyByNearest, $BoxSizeFromShapes, $StampFlush, $MarkerKept]` fails Subsumption against the `$KeyByNearest` model, as the Analyze report's `$KeyByNearest` & `$BoxSizeFromShapes` line states. Only the derivation reads box-size there, and the derivation only leaves the case undefined more often.
- The solver has 44 cases, out of 64 combinations of the six choice points. `impl_choice` and the `subsumed` and `equivalent` relations encode the exclusions above, and the `witness --every-case` audit shows each dropped case failing a case condition.

## Judgments
- Background is the commonest input color (`Mode`), read on each input: the concept file has no stored background, and the Analyze report's Not formed list shows that a stored one fails Fit.
- The Not formed items (stored background, stored key-color-to-corner map, 4-connected shapes) fail Fit at the train pairs, as the Analyze report shows. So no branch was added for them.
- Paint order is stamp, then `$MarkerCleared` clearing, then the color swap, then the input color. Two stamp colors on one cell give two `out` facts, so the case is undefined there. This follows the Analyze probe (`probe_models.py`).
- "Fits in a box-size × box-size box" is the same test everywhere: the bounding box (`Bbox`) of the cells has an extent of at most box-size on each axis. For two cells, this is Chebyshev distance less than box-size. So `$ShapeBySpread` linking and `$KeyWithoutMarker` isolation use that pair test. `$KeyByNearest` compares the larger extent of the pair box, which is the Chebyshev distance plus one.
- `$StampAlignCenter` tries each translation that takes the keyed box's corner cell onto a cell of the corner box, and keeps the one under which the moved box is `centered` in the corner box. Where none is centered (parity differs), `unplaced` makes the case undefined.
- `derive` found no built-in derivation, and `store` printed no `@store` line to add. So `$BoxSizeFromShapes` is a constructor with its own clauses. The derived `size` equals the stored 5 on every input.
- Determine: the sweep gives `box_size` 5 as the one value, and the plan lists no actions, so the solver has no `Determine` comp.
- New witness `crossed-keys`, built to show `$ColorClass & $KeyByNearest & $StampAlignCenter` defined and differing from `$ShapeBySpread & $KeyInBox & $StampAlignCenter`. Key 4 fits a 5×5 box with both shapes and lies nearer shape 2; key 6 lies nearer shape 3. My judgment: `borderline $KeyByNearest`, relaxed `key-cell`. The concept is undefined, and the generator most likely drew each key two cells from its own shape.
- New witness `adjacent-keys`, built to show the `$MarkerColor` readings defined and differing from `$KeyWithoutMarker`. Two shapes keyed to one corner sit side by side, with their keys of color 4 two cells apart, so no lone cell exists. My judgment: `borderline concept`. No scene claim breaks, but the shape boxes are one column apart, and in the train inputs they are at least 3 apart.
- Deletions that change no pair (the `broken`, `unplaced` and `cleared` rules, the `!stamp` and `!cleared` guards, `near` in the spread edge, `size(B, _)` in `out`, and the case-exclusion negations): each guards undefinedness, paint order, or a case condition that the train pairs do not exercise, so each stays. `box_corner(Pc, Bx, D)` in the centered `place` only narrows the translations it tries, and it stays.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
