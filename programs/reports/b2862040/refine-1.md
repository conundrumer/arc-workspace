# b2862040

## Departures
- `other-color-ring` (create.md): the Analyze file says `shape_color=RarestColor` is undefined on this witness because the rarest color is tied. That departure holds. The `RarestColor` proposer keeps every color tied for lowest ("ties included"), so the case reads 1 and 2 as shape colors, is defined, and recolors both rings. The `witness --file` run still prints this difference. For the same reason, the Analyze file's statement that `background=DominantColor` is undefined on a tie is wrong, but no witness exercises it.
- `$HoleCountTable` stays as a case, against the Analyze report's Subsumption verdict (create.md). That departure holds. At `count_color` {0: 1, 1: 8, 2: 3}, the witness `two-hole-table` shows the case defined and giving 3. No other case gives 3.
- `$MinHoleSize` is a branch at the hole-condition point (create.md). That departure holds. It forms the Not formed item about a least hole size, as Develop step 3 requires. It fits at 1. At `min_hole_size` 2, `one-cell-hole` separates it from every other case, so it is neither equivalent to nor subsumed by another case.
- `@derive TileDim` on `hole_count` is a branch (create.md). That departure holds, because `derive` reports that it fits.
- `min_hole_size=TileDim` is now a branch, `@derive TileDim: ordinary concept`. It replaces the `@ignore: derive TileDim` line from create.md, which does not hold. The ignore line said that the derived values include 1 on every input with a hole, so the case would be equivalent to the concept. That is false on some extents. On an extent of 12 (and of 14, 18, 20, 23, 24, 26, 27, 28 or 30), TileDim gives no 1. The witness `min_hole_size=TileDim` is a 12x12 grid with a ring around a one-cell hole. The concept recolors the ring. The derived case takes 2 as the least hole size and keeps the ring. The case fits every pair, because every pair has an extent that gives 1. It is not subsumed: at the stored value 1, `$MinHoleSize` recolors that ring.
- The concept branches use constructor names that the Analyze report does not give: `$Shapes4`, `$Escape4`, `$OwnWalls`, `$ShapeInk` and `$AnyHole` (create.md). That departure holds. The Analyze report calls each of these branches `concept`, and a constructor cannot be named `concept`.

## Judgments
- Witness `min_hole_size=TileDim`, ordinary concept. A 12x12 grid is inside the generator's range of 9 to 16, the pairs already have one-cell holes, and the grid breaks no scene claim. `derive` first wrote this witness as the `one-cell-hole` input at `min_hole_size` 2. There, the derived case agrees with the concept and only the reassigned stored case differs, so the pass rebuilt the witness at the stored assignment. On the same grid, `hole_count=TileDim` has no count of 1 and also keeps the ring.
- `@derive RarestColor` on `shape_color`: variant, derived, `@relaxed shapes` (create.md).
- `@derive DominantColor` on `background`: variant, derived, `@relaxed background-field` (create.md).
- `@derive TileDim` on `hole_count`: ordinary, concept (create.md).
- `one-cell-hole`, `two-hole-table` and `two-hole-square-grid`: ordinary, concept. `rarer-ring`: borderline, concept (create.md).
- Sweep: the extra `min_hole_size` value 0 and the 45 one-row additions to `count_color` were not stored (create.md).
- Parse holds the shape and hole machinery for every reading, and `count_color` has no case column (create.md).
- Deletions: three deletions change no pair output. They are the two 8-step `step` rules, which `$DiagEscape` needs, and `dir_elem(D)` in `ink_holed`, which keeps the `$AllInk` adjacency 4-way. All three stay (create.md, run again in this pass with the same result).
- The scene claim `some-shapes-closed` is not in the header (create.md).
- Keywords `count` and `lookup` are for `$OneHole`, `$MinHoleSize` and `$HoleCountTable` (create.md).
- Not formed items. The proposers that read `ex_out`, and `CountRankAsc`/`CountRankDesc`, are not listed by `derive`. Filling the holes fails Fit. `$HoleWallOnly` and `closed_color=OutNewColor` fail Fit (create.md).
- Prune: the gloss of `recolored` and `closing` was reworded.

## Open
- none

## Lib
- Closed with 8-step escape, as an extension of `Closed` (create.md). This is the set of cells that no 8-step walk from the frame edge reaches, grouped into 8-connected regions. In this solver it is in `Parse`, as `own_open8` and `own8`, and as `ink_open8` and `ink8`. Each pair is a `Reach` with `step(V) :- step_offset(_, V)` seeded at the frame edge, then `Components8` over the cells that the walk does not reach. Other sites: `programs/solvers/aa4ec2a5.dl` (`open8`, `own_open8`), `programs/solvers/a5313dff.dl` (`leak`), and `programs/solvers/ac2e8ecf.dl` (`own8`).

## Fixes elsewhere
- none

## Tickets filed
- 10-292_task_b2862040_refine.md
