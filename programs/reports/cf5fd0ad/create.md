# cf5fd0ad

## Departures
- `quadrant_transform` is keyed by the quadrant's Position in the 2 × 2 arrangement, through `GRID_2x2`. The concept file names it by corner (top-left `D4_HT`, …). `$CounterSpin`'s `anchor` is likewise the `GRID_MASK_2x2` cell at the bottom right, not `DIAG_BR`: [Indirection](docs/handbook/encoding.md#indirection) holds that naming a position in a 2 × 2 arrangement by its corner gives the same key a second name (a68b268e). The program places each quadrant by `concat_2d` on that Position, and 7953d61e and 7fe24cdd are the precedent for the form.
- In the witness file, `off-spin-table`'s `assign` of `quadrant_transform` is rewritten from `DIAG_*` keys to 2 × 2 Positions (TL `[0,1,0,1]`, TR `[0,1,1,0]`, BL `[1,0,0,1]`, BR `[1,0,1,0]`), with the same transforms. So `witness --file programs/reports/cf5fd0ad/witnesses.json` stops at that witness with a key-type error, and that is its only difference. Rests on the departure above.
- In the witness file, the group `["concept", "$CounterSpin"]` of `three-copies` is written `["$Quadrants"]` by `record --all`. That name stands for the same two cases.

## Judgments
- Constructors: `Quadrants {source: Source}` (my name for the concept branch of `arrangement-grain`) | `TileTable`, and under it `Stored` (my name for the concept branch of `quadrant-transform-source`) | `CounterSpin`. `$CoSpin`, `$MirrorFlip` and `$WholeRepeat` fail Fit at train0 by analyze.md and have no witness, so they get no constructor. No line of analyze.md gives the `quadrant-transform-source` & `quadrant-repeat` pair any non-concept branch that fits.
- `$CounterSpin` is encoded as a C4 rotation R that carries the anchor quadrant to a quadrant and turns the input by R's inverse. This gives analyze.md's arrangement, clockwise steps with counterclockwise turns, and needs no sense parameter.
- Not formed, Develop step 3: "`copies` derived from the side" is a family of functions that the pairs do not separate, not one model, and `side − 1` needs arithmetic. The TileD4 `@derive`, reflections, and color claims state no model that is defined. So nothing was formed.
- `derive` reports no built-in derivation that fits. `store` reports that no relation both reads `in` and feeds `out`. So no `@derive` or `@store` branch exists.
- Witness plausibility and verdicts are copied from analyze.md: `off-spin-table` ordinary concept, `@reassigned quadrant_transform`; `three-copies` ordinary concept, `@reassigned copies`. I built no witness.
- Determination: `copies` counts the input-sized strips of a train output nearer one edge than its opposite. `anchor` is the quadrant that every train output shows the input in untransformed, as in 7fe24cdd, with the quadrant found by dividing the tile frame by `params.copies`. `quadrant_transform` is "undecided" in the plan, so it is determined by the values at which the model fits every train pair, and no relation is written for it.
- `tile_transform`: the plan asked for a determination relation (TileD4 exact). The one I wrote tested each D4 element against the outputs, and the lint's `determine prediction` hint flagged it as a guessed value kept by a test that reads inputs and outputs together. I removed it, so `tile_transform` is determined by the fit set that TileD4 gives. Noted in progress-create.md.
- Deletions: I removed `half.domain`, because a zero count is absence, and the redundant `axis_of`, because `dist_pair` on an axis-only strip already rules out the other axis. I kept `missed`/`!missed` in the anchor determination: the pairs never exercise it, but an input with a symmetry would show the input untransformed in more than one quadrant.
- Hints: in the first run, the lib-name collision `turn` and the case-section hints both came from the relation name. Renaming it `quadrant_turn` cleared both. No hint is left.
- Keywords: `tile-arrangement d4 lookup`. The stored quadrant table and the 4 × 4 tile table are lookups.

## Unsettled
- Whether the generator varies `copies` with the input side: every input has side 3. A task with another input size would settle it.

## Concept faults
- none

## Fixes elsewhere
- `scripts/run_dl.py determination-plan` (the line "write a determination relation for each value here that a proposer derives from a fact other than any the concept derives it from"): it lists `tile_transform (TileD4 exact)` even though the only relation that derives it is the fit test the lint rejects. The plan should not ask for a relation where the proposer's derivation is a train-fit test.

## Tickets filed
- none
