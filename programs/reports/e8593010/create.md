# e8593010

## Departures
- `keep-field` reads "each cell not of `hole_color` keeps its color", not "each `field_color` cell keeps its color": `analyze.md` gives the concept as passing every other cell through, and the concept output on `stray-third-color` keeps the `4` cell.
- `$RankDesc` is nested under `$RankBySize` as the constructor field `RankBySize {dir: RankDir}`, with `$RankAsc` as the name for the concept branch of `rank direction`. `$PieceJoin` likewise nests under `$NonFieldInk` as `NonFieldInk {join: PieceJoin}`, with `$MixedPieces` as its concept branch name. This follows the nesting in `analyze.md`.
- The concept branches take the names `$SizeKey` (`color key`) and `$HoleInk` (`ink selection`).
- `field_color=DominantColor` exists only under `$NonFieldInk`, because the `$HoleInk` cases do not read `field_color`, and `@ignore: derive $HoleInk` removes them. In `witnesses.json` the bare name `field_color=DominantColor` takes `$HoleInk`, so `witness --file programs/reports/e8593010/witnesses.json` reports that the name denotes no case. In the witness file the groups name `$NonFieldInk & field_color=DominantColor`.
- `shape_color` and `fixed_shape_color` in `witnesses.json` are keyed by cell lists. That form is not in [Witness file](docs/handbook/solver-file.md#witness-file). The witness file instead gives id-keyed facts of `shape_color` (ids 0–3: single cell, domino, L, straight three-cell piece) and `fixed_shape_color` (ids 0–7 in the order of the `witnesses.json` list), with the same colors. `witness --file` reports the old form as a type error in the `id` column.
- New branch `$SameColorPieces`, under `$NonFieldInk`: it comes from the Not formed item "Same-color pieces under `$NonFieldInk`", which states one model (Develop step 3). Its witness is `touching-third-color`.
- New witness `checkerboard` for `$NonFieldInk & field_color=DominantColor`: no prior run showed the stored-`field_color` case defined and different from the derived one (the subsumption check).

## Judgments
- `touching-third-color` (test0 input with `4` at (0,1), beside the single hole at (0,0)): plausibility `borderline`, because a third color breaks `field-and-holes`. Verdict `concept`: the hole takes `3` and the `4` is kept. `$MixedPieces` gives both cells `2`, and `$SameColorPieces` gives both `3`.
- `checkerboard` (3×3, five single `0` cells, four single `5` cells): the stored field `5` gives the `0` cells `3`, and the derived field `0` gives the `5` cells `3`. Plausibility `borderline`: holes outnumber the field, and that is hardly a field with holes. Verdict `concept`. It is recorded as a further witness of the `@derive DominantColor` branch, with no `@witness` line.
- The `case section` hints on `ink`, `params.hole_color` and `params.field_color` are false positives. Each case joins `ink` on its own `Ink` value, which the head constructor fixes. They are kept with `@ignore: case section`.
- `field_color=RarestColor`, `SharedColor` and `VanishedColor` fail Fit for every case that reads `field_color`: on a pair's input alone they give `0`, or `0` and `5`. They are recorded as `@ignore: derive` lines. A `grid` run of `$NonFieldInk` at `field_color` `0` on train0 left every `5` cell undefined.
- The relabelings finding on `fixed_shape_member` (a half turn and the axis mirrors change no output): this is kept. `$FixedShapeKey` is the model that tells orientations apart. A `RIGID` block would make it `$ShapeKey`, and `vertical-domino-color` shows that orientation-keyed colors separate it.
- Branches dropped under Fit, as `analyze.md` gives them: `$Adjacency8` (train1), `$NeighborCount` (train0), `hole_color=ChangedColor` and `hole_color=VanishedColor` (no value on a single input).
- Not formed: the threshold rule for pieces of 4 or more cells. The item names a family of rules with an example, does not fix one threshold, and so states no one model. A `size_color` computed as 4 minus the size has no relational form, because colors have identity alone.
- Sweep: `size_color`, `rank_color` and `rank_color_desc` accept extra single rows at keys that no input uses. They are not open parameters, so the stored values stand.
- Keywords: `objects count lookup` for the concept, `rank` for `$RankBySize`, `congruent` for `$ShapeKey`.

## Unsettled
- The determination relations of `shape_color`, `fixed_shape_member` and `fixed_shape_color` compare together modulo one renaming of ids. The free-shape ids and the fixed-shape ids were drawn from the same values, so one id could carry rows of both. Now `free_entry` names a piece's free shape by the pair of the piece with itself, so its ids are not fixed-shape ids, and the stored fixed-shape ids are 4 to 11, apart from the free-shape ids 0 to 3. No run has checked this.
- The piece parse (Components, Tally, Bbox, `piece_shape`) is repeated in `Determine`, and it is not in a `Parse` comp. To settle it, move it into `Parse<Key>`, with a record of the key and the piece id as the piece key, and check that a type declared inside a generic comp can use `Key`.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/e8593010/witnesses.json`, the `assign` of `i-tromino-color` and `vertical-domino-color`: it needs a form that [Witness file](docs/handbook/solver-file.md#witness-file) gives, not cell-list keys.

## Tickets filed
- none
