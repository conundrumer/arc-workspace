# e76a88a6

## Departures
- `$MatchFootprint` has no constructor, and its name is removed from every group of the witness file. This follows the rule that a branch gets a constructor only when `analyze.md` gives it a witness. `analyze.md` gives it none, because it fails Subsumption. The run against `witnesses.json` reports only this name.
- `$ClipAtCorner` runs every corner through `diag_dir_elem`, and `$TurnToBlock` runs every D4 element through `d4_elem`. Neither has an `anchor` or `turn` relation in Params. This rests on [Orientation](docs/handbook/principles.md#orientation) "Every value": analyze.md says each case runs every value of the set and is undefined where the values disagree, so no value is singled out. For `$TurnToBlock`, only the four transposing elements can carry the pattern's box onto a block of another extent, so `d4_elem` gives the same model as the four stored values. This form also clears the audit's open-value findings on the eight stored facts.
- `smaller-block` is no longer `$ClipAtCorner`'s witness. The audit showed that on it `$ClipAtCorner` and the concept are both undefined. The new witness `corner-clip` takes its place: a 1x1 gray block, with a pattern whose four corners are all 2. On it `$ClipAtCorner` is defined and gives 2, the concept and `$ScaleToBlock`, `$TileRegion` and `$TurnToBlock` are undefined, and `$SkipMismatched` keeps the block gray.
- `transposed-block` is no longer `$TurnToBlock`'s witness. On it `$TurnToBlock` is undefined, so no run showed that case defined and differing from `$ScaleToBlock`. The new witness `turned-symmetric` takes its place: a 4x3 gray block, with a 3x4 pattern that is symmetric about both midlines. On it the transposing elements agree, so `$TurnToBlock` fills the block with the turned pattern, and the concept, `$ScaleToBlock` and `$TileRegion` are undefined. `transposed-block` stays in the witness file, where it separates `$SkipMismatched`.
- The concept, and every other case, is undefined where a second pattern stands (`extra_pattern`). Before this change, on `blocks-in-another-color` the concept found three patterns and no blocks, and gave the input unchanged. `witnesses.json` gives the concept as undefined there, which is what the `one-pattern` claim states.

## Judgments
- `corner-clip`: plausibility `foreign` and verdict `$SkipMismatched`. The generator never makes a block of another extent, and analyze.md judged `smaller-block`, which is the same kind of input, as `$SkipMismatched`.
- `turned-symmetric`: plausibility `foreign` and verdict `$TurnToBlock`. This is the verdict analyze.md gives `transposed-block`, which is the same kind of input.
- The `case section` hints on `objects4`, `objects8` and `object` are kept with `@ignore`. The hints come from a static reading. Each case reads only the objects of its own adjacency, through the `Adjacency` field of `Obj`.
- Develop step 3 adds no branch. Of the Not formed items, "pattern erased" fails Fit, because every train output keeps the pattern. The other two items state no model.
- `background=DominantColor` is the `@derive DominantColor` line, with plausibility `borderline` and verdict `concept`, as analyze.md gives them. `store` reported no findings.
- Determine relations: `background` keeps the color that is the commonest of every input (`Mode` with a defect relation). `placeholder` is the color of the cells that a train output changes. The plan then reported no actions.
- `deletions`: the removals that change nothing on the pairs are branch behavior that the pairs never instantiate (`$SkipMismatched`, `$ClipAtCorner`, `$TurnToBlock`, `extra_pattern`, the Determine universal). Those stay. The `impl_choice` atoms in the per-shape `out` clauses were redundant, because every combination of the fields is a case and the other atoms ground the head. Those atoms were removed.
- Only 9 of the 48 cases are witnessed. The other cases combine non-concept branches, and no input shows them giving an output that their parts do not give.

## Unsettled
- `deletions` ran before the last solver edit. That edit removed the `impl_choice` atoms that the run reported. The pairs run, lint and the witness check after the edit pass. A `deletions` run on the final file would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
