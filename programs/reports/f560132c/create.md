# f560132c

## Departures
- The solver has the concept case alone. It has none of the `analyze.md` branches `$RectangleFrame`, `$KeyCornerPlacement` (with `$KeyCornerFromKey` under it), `$TurnKeyPiece` (with `$KeyTurnsWithPiece` under it), `$KeyCornerMap`, `$Pieces8`, `$PiecesByColor` and `background=DominantColor`: the solver with all of them as cases (60 cases on a record `Choice`) hit the runner's per-pair limit on every pair. At the Develop budget, the pace told me to cut to the concept case alone.
- The witness file holds no witness: after the cut, each witness of `witnesses.json` names one case only, so it separates nothing. `witness --file programs/reports/f560132c/witnesses.json` printed no difference for the concept case on the seven witnesses.
- The concept gives one output grid per tiling, through a `TiebreakResolution` column that holds the tiling (the key piece's placement and the three other placements). `analyze.md` says the concept gives each tiling's output where there are several. The record holds the three non-key placements in every order, so one tiling stands as several resolutions with the same grid.

## Judgments
- The square's side is found with no arithmetic: every side up to the input's extent is a candidate `Frame2D` square, and the one whose cell `Tally` equals the `Tally` of the non-background cells is kept.
- Placements are found from the square's corners (a piece cell set on a corner cell, then `!inside(P, ZERO)` as a defect test for cells that fall off the square). I used this in place of `Occurrences`, the precedent of 681b3aeb and b7cb93ac: `Occurrences` tries every shape cell against every frame cell, and since each piece covers a corner (`pieces-tile-square`), only the corner placements can be in a tiling.
- The tiling is an exact enumeration: four distinct pieces, the key piece unturned, each one covering a corner, pairwise disjoint. Since their area equals the square's, they tile it. I did not use `PlacementPruning` (the precedent of b7cb93ac) because it over-approximates and cannot give one output per tiling.
- `unturned` (D4_ID) is a Params fact because the literal ban sends every lib constant through Params. Its determination relation keeps the D4 element that, composed with itself, is itself.
- `background` is determined as the commonest color of every input.
- Lint hints from the cut solver: `single-consumer` on `side` and `key_piece`. I resolved both by putting their atoms inline. The `head-repeat` and `chain-join` hints from the many-case version went away when its relations were removed.
- Deletions: `diag_dirs` and the diagonal `neighbor` in `key_cell` stay, because they state the 2×2 block. The pairs hold no L of three distinct colors outside the key. `corner_dist(Q, _, 0)` in `corner_place` stays, because it states that each piece covers a corner. `background_defect` stays, because it is the universal over inputs. I deleted `square_area.domain`: a square of side n always has cells.
- Keyword `mapping` is on the line for the key color that each square corner takes. `congruent` is there because the pieces are matched up to rotation.

## Unsettled
- The branches named in Departures: to settle them, rebuild them under a parameterization the runner can run inside its per-pair limit. One option is to key the rectangle frames only by the factor pairs of the pieces' area and not by every pair of sub-extents. Another is to share one tiling enumeration across the parses. Then run `record` for their witnesses from `witnesses.json`.
- The audit's derive finding `background=DominantColor` fits and has no `@derive` line. I left it open because the Develop budget had stopped new branches. A `// @derive DominantColor: borderline concept` line on `background`, with the `crowded-scene` witness, would settle it.
- `deletions` ran before the last solver edit, which was the deletion of `square_area.domain` that it proposed. One more `deletions` run would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
