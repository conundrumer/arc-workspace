# f3b10344

## Departures
- `bg` has the line `@derive DominantColor: variant derived`. With test0's alt, a derivation of `bg` fits, and `run_dl.py derive` wrote the witness `bg=DominantColor`: train0 with 0 and 2 swapped, where the stored `bg` keeps 0 as background and the derived one takes 2. A color permutation of the task is a variant task, so plausibility `variant`, and its background is the derived one.
- Witness `edge-of-band-own-color` is added. It is `edge-of-band-obstacle` with the 6 in the band made 4. The `witness` run reported that no witness separated `$ClearBridgeOnly` from `$WholeBand` under `$ThroughOtherColors`. The cases' clauses differ, and this input separates them: a cell of the pair's own color sits in the band but outside the bridge's rows. Plausibility `borderline` and verdict `concept`, as for `edge-of-band-obstacle`, since it breaks the same input invariant (a rectangle that enters a band crosses it whole).

- The `$InteriorNested` branch of `Span` is added for test0's `rule` alt: a pair gets a bridge only when its faces have one span, or one face's span holds the other's and reaches past it at both ends. It gives the task file's test0 output, which leaves unbridged the 3 rectangles at cols 24–27 and cols 24–26, whose faces are flush at col 24; the concept gives the alt. Witness `flush-nested` separates it from the concept.

## Judgments
- Concept branch names: `$Opaque` (blocking-colors), `$KeepCells` (obstacle-cells), `$WholeBand` (blocking-region), `$SharedSpan` (bridge-span), `$Comp4` (object-adjacency). `$PaintOver` is nested under `$ThroughOtherColors` as the field `obstacle`, as `analyze.md` nests it.
- No constructor for `$WiderFace`, `$EqualFacesOnly` or `$AnyColorPair`. They fail Fit at train1 and train0, and `analyze.md` gives them no witness.
- Spans, bands and bridges are read from each object's bounding box (`Bbox`) for both adjacencies. For `$Comp4` objects the box is the rectangle itself. `$Components8` reads spans from the box by its own claim.
- The band (`lane`) is the cells strictly between the two box faces along the axis, on the across lines both faces hold. The bridge is the zone less every cell from which a `params.inset` jump toward either side leaves the zone. This states "less `inset` cells at each end" with no arithmetic.
- `$NarrowerFace` with two faces of equal width that overlap only in part takes the lines of both faces. The witness `partial-overlap` does not test this tie.
- Paint: under `$Opaque`, every bridge cell of an unblocked pair is `params.bg`, whichever region is checked, so `$Opaque` paints every crossing cell. `$KeepCells` paints only the `params.bg` ones.
- Hints: `negated-use` on `blocked` was right, so `blocked` is gone. `head-repeat` on `narrow_face` and `overhang` was right, so they are now `narrow_line`, `near_overhang` and `far_overhang`. `common-subexpr` among `facing`, `gap` and `band` was right, so `margin` and `shared` were added. The reserved name `band` was renamed `lane`.
- `determine prediction` hint on `inset` is kept with `@ignore`. `inset` is read as the least run of a face past a bridge's side, measured on the outputs. The inputs enter only through `bridge`, the output color that no input holds, and no output alone shows that color.
- The Determine relations are: `bg` (the commonest input color, the same on every input), `bridge` (the output color absent from its input), and `inset`. The plan reports all three determined.
- Keywords: `objects match span`. `match` applies because rectangles pair off by color and the output acts on each pair.

## Unsettled
- `run_dl.py deletions` did not run: "baseline fails: stored source does not pass train+test". A run after test0 is corrected would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
