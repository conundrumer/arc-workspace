# b7955b3c

## Departures
- `$DirectOrder` stays as a case. The Analyze report says it fails Subsumption: that holds only on inputs whose over relation is acyclic. On a cyclic input, the concept case is undefined where two covering rectangles are each over the other through the closure, and `$DirectOrder` is defined there. The new witness `weave` shows it: four bars woven so that each lies over the next around a cycle, with the mark on the crossing of the 1 and 2 bars. The concept case is undefined at the mark cells, and `$DirectOrder` fills them with 1. This also holds for `probe.py`: its `stack` rejects only 2-cycles when no closure is applied.
- The `erase-marks` rule takes the generator's reading from the Analyze report's Concept section: each mark cell shows the rectangle drawn last there. The concept file's rule stands under it as `@approximated:`, stated with the approximations that the Analyze report gives (the box of the visible cells, and the order the visible cells give, closed transitively). Witnesses `order-hidden` and `hidden-end` stand under that line.
- The concept case is undefined only at a mark cell whose covering rectangles have no top. `probe.py` makes its concept undefined on the whole grid when the order has a cycle anywhere. The two readings differ only on inputs that break `layered-rectangles`, and no witness in either file has such a cycle except `weave`.

## Judgments
- Choice layout: a flat record `[m: Marks, o: LayerOrder, b: Background]`. The points `layer-order` and `background` stand under the concept branch of `restore-source`, and that point has no other formed branch: `$NeighborMode8`, `$NeighborMode4` and `$BetweenCover` fail Fit and have no witness. So the solver does not nest the two points under a one-constructor type.
- Concept branch names: `$EveryMarkCell`, `$Transitive` and `$BottomLayer`. No name in the witness file needed a rewrite.
- All 8 combinations fit every train and test pair. A check of the `out` rows of each case on each pair input showed this. Only the concept case and the three single-branch cases are witnessed. Every verdict on the branches is `concept`, so no combination is witnessed.
- Witness `weave`: plausibility `foreign`, verdict `$DirectOrder`, `@relaxed layered-rectangles`. No drawing order of rectangles makes a cyclic weave, so the generator never produces it. The visible corners of the hidden crossing show 1, so a reader fills the mark with 1, which is `$DirectOrder`'s output.
- `@claim` placement: `Marks` and `LayerOrder` turn on `erase-marks`. `Background` turns on `layered-rectangles`, the claim that puts the background as the bottom layer. `$DominantBackground` adds the claim `dominant-background`.
- `unit` restricts the closure's edges and `over` to the rectangles of the case. That restriction matters only under `$DominantBackground`, where the commonest color is not a rectangle. `deletions` reports that removing `unit(M, Bg, Hi)` and `unit(M, Bg, Lo)` in `over` changes nothing. The pairs never put the commonest color mid-path, so the atoms stay. `common.item` and `!common.mode` are reported for the same reason, and they stay.
- `mark_color`: no built-in derivation fits (`derive`), and `determination-plan` finds the value covered by ChangedColor exactly. So there is no `@derive` line and no determination relation.
- `mark_shape` determination follows 1818057f: the smallest 4-connected component of erased mark cells, cropped to its box. The sweep reports other sets that also fit. `mark_shape` is a scene parameter that the concept fixes as the plus, so it is not an open parameter, and no extra value is stored.
- Lint hint `negated-use` on `!covered(M, B, P)`: applied. The helper `covered` is removed, and the clause negates `covers(..., _)`.
- Keywords: `color-class` (one rectangle per color), `noise` (the marks are removed), `bbox` (a rectangle is the box of its visible cells), `occlude` and `repair` (hidden cells are restored), `rank` (the layer order picks the color that shows).
- No @workaround, and no performance issue: each run finishes in under 2 s.
- Why the restated `erase-marks` rule has no set of clauses: the generator's drawing order and the full extent of each rectangle are not in the input where marks hide them. `order-hidden` (two rectangles overlap only under a mark) and `hidden-end` (the end of a bar lies under a mark) show inputs where no clause can recover what the generator drew.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-445_task_b7955b3c_create.md
