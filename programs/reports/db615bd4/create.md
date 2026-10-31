# db615bd4

## Departures
- The concept file's scene parameters `dot-parity`, `piece-parity` and `margin` are written into the `@scene` lines (odd, even, 1). `margin` is also a Params relation, because `$RoomAxis` and `$GapFromFit` read it and literals are banned: the concept file lists it only as a scene parameter.
- `$OrderAlongSpread` reads a new parameter `spread_sense` (SENSE_CC): where the spread axis and the stack axis differ, the order along the spread axis has to be mapped onto the stack axis, and no fixed mapping is equivariant. CC maps top to left, which gives the output that `witnesses.json` gives on `order-across-spread`.
- `gap` is declared above the case markers, so every case reads it. By the program's rules, `$GapFromFit` cases read it through the shared layout set (`gap_cand`), and the case-section hint fired when `gap` stood under its own marker.
- Two names in the witness file were rewritten by `record --all` into the listed form. The concept branches take the constructor names `FrameLong`, `SpanOrder`, `CenterStack`, `CenterAlong` and `DotClassFrame`. On all 7 witnesses, every branch's model gives the output that `witnesses.json` gives (`witness --file` ok).
- `deletions` ran before the last solver edit. That edit removed an atom from `layout` that `gap_cand` already implies. The pairs run after that edit passes, and lint is ok.

## Judgments
- bg is the commonest color, and the dot color is the commonest color off the background (`Mode`). The dot class is the set of cells that the dots reach in steps of two cells (`Reach` with doubled cardinal steps). Under the scene, dots outnumber all other non-background cells, so this agrees with `dot-class` on every input the generator produces.
- Pieces are color classes: the non-background colors other than the dot color and the frame color. Each piece's block is its color's bounding box.
- The stack is built without arithmetic. The tokens are each piece's span lines, plus `gap` lines between consecutive pieces (`AxisFrame`). `Order` ranks the tokens, and `DirPack` turns rank and reverse rank into a line of the stack's own frame. `relative` and `centered` center each block in the interior. `$CenterEachBlock` uses the same placement, and the concept adds the definedness check `mixed_cross`.
- `$GapFromFit` keeps the gap candidate (0, or each sub-extent of the interior) at which the stack's first line sits `margin` from one end and its last line sits `margin` from the other end. `$RoomAxis` keeps the axis on which, at the stored gap, the far end is `margin` or more from the edge.
- Each layout is computed for both directions of its axis, and the two directions give the same output, so the program fixes no orientation.
- `$SpreadAxis & $OrderAlongSpread` is left out of `impl_choice`, because `analyze.md` gives it as the `$SpreadAxis` model.
- Hint `head-zero` on `gap_cand`: kept with `@ignore`, because a gap of no cells is a real candidate for `$GapFromFit`.
- `witness` without `--file` reports no unseparated pair and no unwitnessed case. The audit's checks of witnesses, dropped cases, store, open values and relabelings are ok.
- `deletions`: 50 deletions change nothing on the pairs. They are inputs that the pairs never exercise: definedness checks such as `unplaced`, `mixed_cross` and `!room`, the `$OrderAlongSpread` cross-axis branch, and guards on non-piece colors. These are kept, because each states part of a model that the witnesses separate. One `deletions` run timed out (`interior(P, B)` in `interior_box.cell`).
- Performance: the pairs run takes 3–13 s. `stack.before` is over 20000 rows on an input, because there is one layout per frame branch × order branch × direction × gap candidate.

## Unsettled
- `derive` reports four built-in derivations that fit: `gap=SepThickness`, `gap=TileDim`, `margin=SepThickness` and `margin=TileDim`. The solver has no `@derive` or `@ignore: derive` line for any of them, and the audit still reports them. The pace budget ran out before each one had a witness. To settle: build a witness for each derivation, or show that it fails a case condition. On inputs whose dots are not 2 apart, the dot-class parse is undefined, so the `gap=SepThickness` cases that take `$DotClassFrame` are likely subsumed. The `$FrameLargest` cases likely are not.
- `analyze.md` Not formed, "`gap` as the dot class's period less one", was not formed as a branch. It is close to `gap=SepThickness`, and the same witness work would settle both.
- `spread_sense`: the sweep reports that SENSE_CW also fits every pair. It is an open parameter of `$OrderAlongSpread` and is not stored as `@open` with an `OpenValue` column. To settle: store both senses as `@open`, then re-record `order-across-spread`.
- Determination: the solver has no `Determine` comp. The plan reports that `gap` and `margin` are covered by `DivisorRatio`, and `spread_sense` by enumeration. A determination of `gap` and `margin` from the background cells between blocks, and between the end blocks and the outline, in the train outputs is not written. That needs the scene parse to move into `Parse<Key>`.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
