# f9a67cb5

## Concept
- Fits every pair (train0–2, test0), checked by `work/task/f9a67cb5/check.py`. Each rule is a propagation over cells (fall straight on, spread along the line in front of a wall up to the first cell that faces a gap, drain through it), so each one has a relational form and nothing in it is an approximation. No witness has the verdict `other`. The flow direction comes from the source's edge, and the program goes through all four cardinal directions. Three of the branches below fit every pair. Two change what is stored (where the source color and the water color come from), one changes how walls are found, and one changes how water drains through a gap wider than one cell. Every input has only one-cell gaps.

## Choice points
- `source-color`
    - `concept`: `source_color` is stored (2), and the source is the one cell of that color
    - `source_color=RarestColor`: derives `source_color` as the rarest color of each input. Replaces `one-source`'s stored `source_color`. No parameter. On an input with tied rarest colors it gives one output per color, and it is undefined on no input. Fits every pair. Witness `source_color=RarestColor` breaks `one-source` (no cell of 2), stands at the stored assignment, plausibility `variant`, verdict `source_color=RarestColor`; it breaks the input invariant that the spout is 2.
    - `source_color=DominantColor`: derives `source_color` as the commonest color, which is 0 on every input. Replaces `one-source`'s stored `source_color`. Fails Fit at train0.
    - `source_color=SharedColor`: derives `source_color` from the colors present in the input, which are 0, 2 and 8 on every input. Replaces `one-source`'s stored `source_color`. Fails Fit at train0.
- `water-color`
    - `concept`: the water takes `source_color` (`paint-water`)
    - `water_color=stored`: a stored `water_color` (2) paints the water. Replaces `paint-water`. Parameter `water_color`. Undefined on no input. Fits every pair. Witness `water_color=stored` stands at `water_color` = 3, breaks no scene claim, plausibility `ordinary`, verdict `concept`.
- `wall-color`
    - `concept`: walls are the cells of the stored `wall_color` (8)
    - `$WallAnyColor`: a wall is any cell that is neither `background` nor the source. Replaces `parallel-walls`' `wall_color` and `fall-straight`/`spread-along-wall`'s wall test. Reads `background` (0) in place of `wall_color`. Undefined on no input. Fits every pair. Witness `wall-other-color` breaks `parallel-walls` and `background` (its walls are 5), stands at the stored assignment, plausibility `variant`, verdict `$WallAnyColor`; it breaks the input invariant that every wall cell is 8.
    - `wall_color=DominantColor`, `wall_color=RarestColor`, `wall_color=SharedColor`: each derives `wall_color` on each input, as 0, as 2, or as 0, 2 and 8. Each replaces `parallel-walls`' stored `wall_color`. Each fails Fit at train0.
- `gap-drain`
    - `concept`: water drains through a gap only at the cell it reaches, so the stream is one cell wide
    - `$DrainWholeGap`: water at a cell that faces a gap also spreads over every cell that faces the same gap, and drains through each of them. Replaces `drain-through-gap`. No parameter. Undefined on no input. Fits every pair. Witness `wide-gap` breaks `parallel-walls` (a gap two cells wide), stands at the stored assignment, plausibility `borderline`, verdict `concept`; it breaks the input invariant that every gap is one cell wide.
- `spread-stop`
    - `concept`: each way, the spread stops at the first cell that faces a gap
    - `$SpreadPastGaps`: the spread runs on past gaps to the grid edge and drains through every gap on the way. Replaces `spread-along-wall`. No parameter. Undefined on no input. Fails Fit at train0 (row 3 would fill cols 0–16).
- `straight-arrival`
    - `concept`: water that falls straight onto a gap passes through it without spreading
    - `$SpreadAtEveryWall`: water that falls straight onto a cell facing a gap also spreads along the wall's line. Replaces `drain-through-gap`. No parameter. Undefined on no input. Fails Fit at train2 (col 3 would be wet in rows 3–9).
- `flow-direction`
    - `concept`: derived from the edge the source sits on, as the direction away from that edge
    - `flow_dir=stored`: one stored flow direction (down). Replaces `fall-straight`. Parameter `flow_dir`. Undefined on no input. Fails Fit at train1.
- `source-color` & `water-color`, `source-color` & `wall-color`, `source-color` & `gap-drain`, `source-color` & `spread-stop`, `source-color` & `straight-arrival`, `source-color` & `flow-direction`, `water-color` & `wall-color`, `water-color` & `gap-drain`, `water-color` & `spread-stop`, `water-color` & `straight-arrival`, `water-color` & `flow-direction`, `wall-color` & `gap-drain`, `wall-color` & `spread-stop`, `wall-color` & `straight-arrival`, `wall-color` & `flow-direction`, `gap-drain` & `spread-stop`, `gap-drain` & `straight-arrival`, `gap-drain` & `flow-direction`, `spread-stop` & `straight-arrival`, `spread-stop` & `flow-direction`, `straight-arrival` & `flow-direction`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Water fills the whole basin between two walls instead of only the line in front of the wall: the pairs separate it (train0 row 5 is wet only at col 2 and col 12).
- The spread stops one cell short of the gap: water could not then reach the gap, and no pair has water stopping short of one.
- Several sources: the concept's rules pour from each source cell alike, and no reading of the pairs differs there.
- Water color from a proposer: OutNewColor and AnyOutNewColor give nothing, since 2 is in every input, and ChangedPairs gives a mapping (0 to 2), not a color.
- A source off the edge (in the interior or at a corner): no edge gives a direction, the scene rules it out, and nothing in the pairs or the solver headers (for example 36a08778) suggests a reading.

## Tickets filed
- none
