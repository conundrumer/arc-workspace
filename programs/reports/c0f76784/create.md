# c0f76784

## Departures
- The `$RankBySize` model (`$HoleSide & $RankBySize`, at every hole region) is not a case. `subsumed` in `impl_choice` drops it, and `witness --file` prints "`$RankBySize` denotes a model that is no case of the solver" on each of the eight Analyze witnesses. This rests on the Subsumption condition. A hole side is the shorter side of the bounding box of a hole that is a solid square, so `$KeyByMinSide & $RankBySize` gives the output of `$HoleSide & $RankBySize` wherever that case is defined, at every assignment, and no input can show them differ. A case that leaves under Subsumption is not an error of the Analyze report. Every other branch's model gives the output the Analyze file gives it.
- Constructor names the report does not give: `HoleSide`, `MeasureKey`, `Enclose4`, `OutlineSide` and `OutlineAdj8` are the concept branches of their points. `KeyByOutlineSide {m: OutlineMeasure, adj: OutlineAdjacency}` is the hole-measure branch. The report names `$KeyByOutlineSide` both as that branch and as the concept branch of `outline-measure` under it, and two constructors cannot share one name.
- `outline-adjacency` is a field of both `KeyByOutlineSide` and `FillBboxInterior`. `adjacency_clash` drops each case whose two fields differ, so a case that takes both branches reads one adjacency, as the report gives.
- Two witnesses that the Analyze file lacks, `diagonal-pieces` and `rank-mixed-shapes`, are in the witness file. The `witness` resolutions under Judgments give why.

## Judgments
- `@derive DominantColor: variant derived`, `@relaxed square-outlines`, on `background`: the witness is train 0 with `0` and `1` swapped. A variant task routinely gives the field another color, and the generator fills the holes on it, which is the derived output.
- `@derive RarestColor: variant derived`, `@relaxed square-outlines`, on `frame_color`: the witness is train 0 with `5` and `1` swapped. A variant task routinely gives the outlines another color, and the generator fills the holes on it, which is the derived output.
- `store` printed no findings, so no `@store` line is held.
- Not formed: neither item states a model with a relational form that fits. "5 plus the side" is color arithmetic. The ascending rank fails Fit at train 2.
- `witness` reported that no run shows `$OutlineAdj8` defined and differing from `$OutlineAdj4`, under `$FillBboxInterior` and under `$KeyByOutlineSide`. I built `diagonal-pieces`, a 4×4 outline drawn as two pieces that meet only at two corners. On it, the 8-adjacent object fills its 2×2 interior 7, the outline side 4 fills 7, and the 4-adjacent pieces fill 6. Plausibility `foreign`, verdict `concept`, `@relaxed square-outlines`: the outline is not closed under 8-steps, as in `corner-gap`. The concept case fills 7, because a 4-step walk finds the hole closed.
- `witness` reported that no witness separates `$KeyByAxisExtent` from `$KeyByArea`, `$KeyByMinSide` and `$KeyByMaxSide` at `$RankBySize`, and then `$KeyByArea` from `$KeyByMinSide`. I built `rank-mixed-shapes`, with holes of 1×5, 2×2 and 1×3. On it, each ranked measure gives its own grid, and the ranked axis extent gives two grids. Plausibility `borderline`, verdict `any`, `@relaxed square-outlines`, as for `hole-2x3`.
- `case section` hints on `obj8`, `obj4` and `obj_cell`: kept under a marker per adjacency, with `@ignore: case section`. A case that takes `$OutlineAdj4` reads `obj_box` only at the key `[$OutlineAdj4(), Id]`, and the hint's static reading loses that key through the `Bbox<Obj>` record (ticket 10-659).
- `common-subexpr` hint in Determine: resolved by the helper `changed`.
- Determine: `background` is the input color of the cells a train pair changes. `frame_color` is the color of the unchanged cells beside a changed cell. The plan listed both because the proposers derive them from cell counts, a fact other than the one the concept reads.
- The sweep found 45 to 50 single-row changes of each fill table that fit every train pair, each a row at a key that no pair holds. No reader of the concept takes such a row, so no table is widened.
- `deletions`: the 24 deletions that change nothing remove structure that the pairs never instantiate: non-square or non-solid holes, diagonal leaks, adjacency clashes, the outline and area measures under `$RankBySize`, and the `impl_choice` guards. The pairs run only the witnessed cases, so those guards show no effect. Each deletion stays.

## Open
- `$Enclose8`, `$WallsOfFrameColor` and `$FillBboxInterior`, each a case that takes `$HoleSide & $MeasureKey`, look subsumed by `$KeyByMinSide` at the same hole-region branch, by the reasoning that dropped `$HoleSide & $RankBySize`. To settle it, a reviewer would rule whether those branch-model cases leave, and which case then stands for each of those branches.
- The fill tables are left to fit, as the determination plan lists them under "undecided". A determination relation for each table would read the tables from the evidence. That relation would need the hole and measure derivations moved into `Parse`.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-658_task_c0f76784_create.md
- 10-659_task_c0f76784_create.md
- 10-660_task_c0f76784_create.md
