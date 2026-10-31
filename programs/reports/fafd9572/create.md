# fafd9572

## Departures
- `recolor-copy` in the header compares the place of a copy and the place of a key cell from all four edges. The concept file uses the row and the column alone. The solver gives each copy a place built from its dense rank by distance to each of the four edges (`Ordinal` + `DirPack`, as in the 19bb5feb precedent). That place equals a key cell's position in the key's box only where the copies' rank frame and the key's box have the same extent. A row and column counted from the top-left corner alone is a hidden orientation. Under `layout-matches-key` the two readings agree.
- Witness `background=DominantColor`: `witnesses.json` gives the concept and `$LatticeSlot` a grid with the copies turned 6. The solver gives undefined for these, because the key's box (the whole 6 field, 10 by 12) does not match the copies' 2 by 2 frame. The analysis read the slot from the top-left corner, which is the hidden orientation described in the item above. The witness still separates `background=DominantColor` from the concept.
- `$GapFromSpacing` computes the gap on each axis as the fewest lines between two copies that lie apart along that axis, with the gap 0 where no two copies lie apart. `analyze.md` takes the least difference between two copy tops, less the extent. The program cannot use that form, because it bans arithmetic. On `key-with-gap` both forms give undefined, and the recorded groups say the same.
- `$OrderMatch` is undefined on the whole grid where a key cell has no copy at its rank (`unpaired`). This makes `copies-in-another-color` undefined for `$OrderMatch`, as `witnesses.json` gives it. Before that change, the copies with no match stayed as they were and the cells that the key covered were output.
- Three witnesses were added. `skipped-column` (variant, verdict `$LatticeSlot`, relaxed `key`) separates `$LatticeSlot & $GapFromSpacing` from `$Rank`. `missing-copy` (borderline, verdict `concept`, relaxed `layout-matches-key`) shows the `$LatticeSlot` cases defined where `$OrderMatch` is undefined. `copies-in-a-row` (foreign, verdict `$OrderMatch`, relaxed `layout-matches-key`) shows that `axis` changes the output of `$OrderMatch`.

## Judgments
- The header keeps the concept file's rank rule. `analyze.md` gives the generator's rule as the key drawn at a larger scale. That rule is the `$LatticeSlot` model, which `analyze.md` sets as a branch of `slot-correspondence`. If that rule became the header rule, the rank model would have no branch, and `$LatticeSlot` would fail Equivalence.
- `background=DominantColor` is a `@derive DominantColor` line, because `derive` reports that it fits. `$ShapeColorByCount` and `$GapFromSpacing` have no built-in proposer, so each one is a constructor. `store` printed no line to add.
- `$FourConnected` and `$ShapeColorByRepetition` have no constructor. Both fail Fit at train0, as `analyze.md` records.
- Not formed: "key read under a stored D4" fails Equivalence. Its only value across variant tasks is the identity. "Lattice period under the concept" gives no model of its own, because the rank rule reads no period. "Key removed or recolored" fails Fit.
- `corner` and `axis` (reading order of `$OrderMatch`) are stored as TL and V and are not open. "Reading order" is a fixed convention. `analyze.md` lists no open parameters.
- Determine: `background` is the color that is the commonest in every input. `shape_color` is read as the input color of a cell that changes in a train output. This replaces a test that read inputs and outputs together, after the determine-prediction hint. `copy_gap` is the fewest lines free of copy cells between two copy lines. The plan's proposer for `copy_gap` (DivisorRatio) reads a dimension ratio, and the value 1 comes from it by chance.
- The deletions that change nothing (`unpaired`, `perp`, the `copy` atoms in `spacing`, the gap-0 disjunct, the determination atoms) stay. Each one acts only on inputs that the pairs do not hold: the witnesses, a lattice with one line of copies, or two shape sources with different copies. The `impl_choice` atoms in the per-case `out` clauses and the `domain` rules of the `Tally` instances were removed.
- Plausibility and verdicts of the new witnesses: on `skipped-column`, the generator draws copies as the scaled key, so the copies are 2, 3 and 4 (`$LatticeSlot`). On `missing-copy`, a copy left out is unusual, and the copies that are present keep their slot colors (`concept`). On `copies-in-a-row`, the generator never draws this layout (`foreign`).

## Unsettled
- Relabeling audit: a half turn of `corner` (TL to BR) changes no output on any input. Reversing both reading orders keeps the pairing, because the counts must be equal. So no input can show the difference, and a `RIGID` block does not apply to a reading order. A solution would be a parameterization of the reading order up to reversal, such as a diagonal axis together with the primary axis, read by an order component that takes it.
- `corner` and `axis` have no determination relation. The determination plan lists all 8 joint values as fitting every train pair.
- `$ShapeColorByRepetition` limited to parts of more than one cell (Not formed in `analyze.md`) fits every pair but was not formed. It needs a size threshold parameter and a translate-recurrence check. A pass that builds it and its witness would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
