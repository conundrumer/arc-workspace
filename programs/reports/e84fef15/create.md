# e84fef15

## Departures
- `$DividerFromLines` has no constructor, and the witness file no longer names it: it fails Subsumption. On an input where exactly one color fills full lines, `divider=SharedColor` cuts at the same lines and gives the same output. Where no color or more than one color does, `$DividerFromLines` is undefined. So no input shows it defined and differing from the `divider=SharedColor` case. `witness --file witnesses.json` prints "the name `$DividerFromLines` denotes no case" on five witnesses for this reason.
- `divider=SharedColor` is a case. `analyze.md` says it fails Fit at train0, but `derive` finds that it fits. The derived divider is the set of every input color, and the program cuts at each full line of any color in that set. The analysis took each color as a separate value. `divider-recolored` is kept as a further witness of that branch.
- `gap` is one parameter that `$CutBySize` and `$CutByCount` share. `analyze.md` gives each of them a stored gap of 1. On any grid that both cuts fit, the two cuts give the same tiles, so the gap is the same.

## Judgments
- `@ignore: derive VanishedColor` on `divider`: with no train output, VanishedColor gives every color of the input, as SharedColor does. So the two models are equivalent, and VanishedColor fails Equivalence.
- `@ignore tile_of: store` and `@ignore divider: store` on `panels`: a stored lattice or stored divider lines cut a 29×29 grid exactly as `$CutBySize` does, and match no cell of a grid of another size. So both are subsumed by `$CutBySize`.
- `@ignore value: store` on `line`: the stored value is the parameter `divider`.
- `@ignore: determine prediction` on Determine `gap`: the train outputs give the tile size. The gap is the value at which a cut at that size puts every divider-colored input cell in a gap and no other cell in one. The hint fires because this test reads inputs and outputs together.
- Built witnesses:
    - `fewer-tiles`: train0 cropped to 4×4 tiles. Ordinary, verdict concept. `$CutByCount` and the stored lattice are undefined on it.
    - `smaller-tiles`: tiles of 4. Ordinary, verdict concept. `$CutBySize` is undefined on it.
    - `second-line-color`: an extra full row of 5. Borderline, verdict `divider=SharedColor`.
    - `lost-and-added`: two damaged tiles and one added mark. Borderline, verdict `$Disagreement`. It separates `$Disagreement & $LostMarkOnly` from `$Disagreement` and from `$LostMarkOnly`.
    - `wide-last-tile`: one row of three tiles, the last one a column wider. Foreign. It shows `$OneDamaged & $LostMarkOnly` defined and differing from `$Disagreement & $LostMarkOnly`. On it the concept paints every cell, because a cell of a 5-wide tile frame and a cell of a 6-wide frame are different Positions.
    - `strips`: rows of 8 break every vertical divider. Foreign. It shows `$Disagreement` under the stored divider defined and differing from `$Disagreement` under SharedColor.
- Deletions:
    - The flagged atoms in `$Disagreement & $LostMarkOnly` are kept. That case differs from the others only on witnesses, and the deletions run reads the pairs alone.
    - `other_clash`, `ragged`, the `!tile_cell` disjunct and the two `differ` disjuncts are kept. They decide where a case is undefined, which no pair shows.
    - The `uncommon`, `missing`, `gap_misfit` and `parts.domain` clauses are kept. They state universals that the pairs do not exercise.
    - `panels.tile_of` in the `$ByLines` `tile_cell` clause is kept. The tile box and `crop` imply it, but it states which cells are tile cells.
- Keywords `decompose wallpaper repair crop`: the lattice is a periodic pattern, the output restores the pattern from its copies, and one tile gives the output its frame.

## Unsettled
- The derivations `gap=SepThickness`, `gap=TileDim`, `tile_size=SepTileCount`, `tile_size=SepTileDim`, `tile_count=SepTileCount` and `tile_count=SepTileDim` fit, and each has no `@derive` or `@ignore: derive` line. The Develop budget ran out before they were held. To settle them, hold each one with a witness under the id the `derive` command names, or find the case condition it fails.
- `witness` reports that no run shows `$OneDamaged & divider=SharedColor` defined and differing from `$Disagreement & divider=SharedColor`. The input that settles it has one tile of a different size from the others and no line of one color other than the divider. A one-row lattice from train0 has full columns of 8, so it needs a pattern with no all-8 column.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/e84fef15/analyze.md`, the `divider=SharedColor` line: it says the branch fails Fit at train0. The `derive` command uses the derived colors together as a set, and with that set the branch fits every pair.

## Tickets filed
- none
