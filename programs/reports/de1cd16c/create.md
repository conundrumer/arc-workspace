# de1cd16c

## Departures
- The concept's parameter `extreme` (most) is not stored. The program fixes "most" through a `Mode` instance: this rests on [Types](docs/handbook/solver-file.md#types), which allows no type for the two ends of an order, and no lib type encodes them. The pairs fix the value (analyze.md, Not formed), so no case reads another value.
- `out_dim` is one number read on both axes, `out_dim(1)`, with `out_pos` derived in Params through `helpers.frame_pos`: this follows the concept file's `out_dim`×`out_dim`.
- The tie choice point is encoded twice: by the `Tie` field of `Choice` and by a `TiebreakResolution` column on `out`. `$UniqueMost` writes `$Sole()` there, so a tie gives two colors on one cell and the concept is undefined. `$TieAll` writes `$Tied(<region id>)`, so it gives one grid per tied region: this follows [Types](docs/handbook/solver-file.md#types), which gives `TiebreakResolution` for the grids a case gives on one input, one per resolution of a tie.
- The witness file has a witness that is not in witnesses.json, `corner-block`: it resolves the `witness` finding that no run showed `$RarestSpeck & $ComponentRegion` defined and different from `$ComponentRegion`.

## Judgments
- The concept branches take the constructor names `IsolatedSpeck`, `ColorRegion`, `BoxOwner` and `UniqueMost`. The witness file names no concept branch, so no name in it was rewritten for them.
- `$SpeckDensity`, `$RegionArea` and `out_dim=ConstOutDim` fail Fit (analyze.md), and they have no constructor. `derive` reports that no built-in derivation fits, and `store` reports no findings. Develop steps 3 and 4 therefore add no branch.
- The Not formed items of analyze.md give no branch: `extreme` fewest, `ConstOutDimAxis` and `DominantColor` fail Fit, and the count of non-fill cells is a reading that no reader of the concept takes.
- All 16 combinations of the four choice points are cases. The run shows 6 witnessed cases: the concept, the four branch models, and `$RarestSpeck & $ComponentRegion`. That last case is undefined on `tiny-region`, where no other case is undefined, and the run takes that as its witness.
- `corner-block` witness: a 2×2 block of 3 fills the bottom-right corner of region 1. This makes region 1 non-rectangular, so it breaks `rectangular-regions`. Plausibility `borderline`, verdict `concept` (output 8: region 8 holds 3 of the 5 specks of color 4). The generator puts no region inside the box of another region, and a reader who sees this grid still takes the isolated color 4 as the speck color.
- Hint `common-subexpr` on the component-region `region_color` clause: I removed the per-unit `region_color` clauses and used one fill-color lookup over `region`. The next hint, `single-consumer` on that relation, led me to inline it into `winner`.
- Hint `head-repeat` on `out`, where the `$Tied` resolution repeated the color: the resolution now holds the region's `Ident`. The tie is between regions, and under `$ComponentRegion` two tied components can share a color.
- Determination: `sweep` gives `out_dim` unique at 1. `determination-plan` lists `out_dim (ConstOutDim exact)` as covered. The concept determines `out_dim` from the same fact, the output extent, so no `Determine` relation was written.
- Deletions: `color_count.domain` was removed, because every color in that domain has a cell, so the domain adds no key. `in(P, Col)` was removed from the component-region clause, because `part.label` binds `Col`. These were kept:
    - `dir_elem(D)` in `same_neighbor` and in the `$NeighborOwner` clause, because they state the 4-neighbor claims.
    - `!speck.value(S, Col)` in the component-region clause, because without it each speck becomes a region.
- Markers: the shared clauses stand under markers that list both branches of one point, such as `// --- $IsolatedSpeck, $RarestSpeck ---`. Those markers cover every case.

## Unsettled
- `deletions` ran before the two deletions it suggested were applied. It was not run again after those edits: running `deletions` once more would settle that the final solver has no further dead atoms.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
