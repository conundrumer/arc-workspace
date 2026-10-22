# ac605cbb

## Concept
- Fits every pair (`probe.py` reproduces each train and test output). It has a relational form: each seed (a cell whose color is a key of `stamp`) draws its stored path, a cell that two stamps' line cells share is a crossing, and the lib's `Ray` casts `cross_dir` from each crossing to the frame edge.
- The program reads no background: a seed is a cell of a keyed color, and a cell of any other color is kept. `background` stays a scene parameter.
- On an input that breaks `stamps-meet-at-lines` with an end cell on another stamp's line cell, `stamp-path` paints that cell two colors and the concept case is undefined; the `end-meets-line` point holds the models defined there.
- A stamp that leaves the grid is drawn clipped to the frame.
- No witness has verdict `other`.

## Choice points
- `ray-over-ink`: what the ray does at a cell that a seed or a stamp occupies
    - `concept`: the ray paints the cell `cross_color` and goes on to the edge
    - `$RayUnderInk`: replaces `cross-ray`; the ray goes on to the edge and paints only cells that no seed or stamp occupies; defined on every input. Fits every pair. Witness `ray-meets-line`: the ray from the 2–3 crossing meets the 6 line at (7,1); stands at the stored assignment; breaks no scene claim; plausibility `ordinary`; verdict `concept`.
    - `$RayStopsAtInk`: replaces `cross-ray`; the ray ends before the first cell that a seed or a stamp occupies; defined on every input. Fits every pair. Witness `ray-meets-line`, as above: plausibility `ordinary`; verdict `concept`.
- `ray-direction`: the diagonal direction of the ray from a crossing
    - `concept`: the stored `cross_dir`, down-left
    - `$RayAlongHorizontalLine`: replaces `cross-ray`; the ray's horizontal sense is the step direction of the stamp that runs horizontally through the crossing, and its vertical sense is a stored `ray_vertical` (down); undefined where no stamp, or both stamps, run horizontally through a crossing. Fits every pair: every crossing in the pairs is on a 2 line, which runs left. Witness `one-line-crosses-three`: the 1 line, which runs right, crosses the 3 line at (5,3); stands at the stored assignment; breaks no scene claim; plausibility `ordinary`; verdict `concept`.
    - `$RayAlongBothLines`: replaces `cross-ray`; the ray's sense on each axis is the step direction of the stamp that runs along that axis through the crossing; no parameter; undefined where two crossing stamps run along one axis. Fails Fit at train3: the 6 line runs up, so the ray goes up-left, and the output paints down-left.
    - `$RayBothWays`: replaces `cross-ray`; the ray runs both ways along the anti-diagonal; defined on every input. Fails Fit at train2: it paints (3,5), which the output keeps 0.
    - `$RayTowardNearestCorner`: replaces `cross-ray`; the ray heads toward the grid corner nearest the crossing, and toward each nearest corner on a tie; defined on every input. Fails Fit at train2: the corner nearest (4,4) is top-left.
- `end-meets-line`: what a cell gets where one stamp's end cell meets another stamp's line cell
    - `concept`: both colors, so the concept case is undefined there (scene claim `stamps-meet-at-lines`)
    - `$EndOverLine`: adds that the end cell's color shows there and the cell is no crossing; defined there. Fits every pair. Witness `end-on-line`: the 2 stamp's end lands on the 3 line at (4,2); breaks `stamps-meet-at-lines`; stands at the stored assignment; plausibility `borderline`; verdict `$EndOverLine`; breaks the invariant that two stamps share only line cells.
    - `$LineOverEnd`: adds that `line_color` shows there and the cell is no crossing; defined there. Fits every pair. Witness `end-on-line`, as above: plausibility `borderline`; verdict `$EndOverLine`.
    - `$CrossAtEndCell`: replaces `cross-cell`; a cell that two stamps reach, line or end, is a crossing: it takes `cross_color` and casts the ray. Fits every pair. Witness `end-on-line`, as above: plausibility `borderline`; verdict `$EndOverLine`.
- `stamp-meets-seed`: what a seed's cell gets where another stamp's cell lands on it
    - `concept`: the stamp's color
    - `$SeedOverStamp`: replaces `keep-input`; a seed keeps its color over any stamp; defined on every input. Fits every pair. Witness `line-on-seed`: the 2 line passes over the 3 seed at (4,4); breaks `stamps-meet-at-lines`; stands at the stored assignment; plausibility `borderline`; verdict `$SeedOverStamp`; breaks the invariant that no stamp cell lands on a seed.
- `stamp-off-grid`: what is drawn of a stamp that reaches past the grid edge
    - `concept`: the part inside the grid
    - `$DropStampOffGrid`: replaces `stamp-path`; a stamp whose end cell lies outside the grid is not drawn; defined on every input. Fits every pair. Witness `stamp-off-grid`: the 6 stamp from (3,3) reaches past the top edge; breaks `stamps-fit`; stands at the stored assignment; plausibility `borderline`; verdict `concept`; breaks the invariant that every stamp lies inside the grid.
- `ray-over-ink` & `ray-direction`, `ray-over-ink` & `end-meets-line`, `ray-over-ink` & `stamp-meets-seed`, `ray-over-ink` & `stamp-off-grid`, `ray-direction` & `end-meets-line`, `ray-direction` & `stamp-meets-seed`, `ray-direction` & `stamp-off-grid`, `end-meets-line` & `stamp-meets-seed`, `end-meets-line` & `stamp-off-grid`, `stamp-meets-seed` & `stamp-off-grid`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `stamp` derived from the seed color: no relation of color to path holds across the keys (2 takes four steps left, 1 a bent path of three steps), so no derivation gives the stored table.
- `line_color` and `cross_color` derived: no proposer that reads one input alone gives 5 or 4; `OutNewColor` and `AnyOutNewColor` read `ex_out`, which is empty in a run on one input.
- `background` stored or derived: no rule reads it.
- Two stamps that overlap along one line: every such overlap of the 1 and 2 stamps, or of the 3 and 6 stamps, puts one stamp's end cell or line cell on the other's seed or line, so `end-meets-line` and `stamp-meets-seed` give its models.
- A seed color with no key in `stamp`: every model keeps such a cell, so it separates no two models.

## Tickets filed
- none
