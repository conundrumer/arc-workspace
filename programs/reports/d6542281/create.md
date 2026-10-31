# d6542281

## Departures
- `impl_choice` leaves out every `$UniqueDotPlacement & $PlaceOverAny` combination. It fails Fit at train0, train2, test0 and test1. Copies placed over any cell cover each dot more than once, so no dot keeps a placement and no shape is completed. `analyze.md` gives each branch as fitting on its own, and its pair line says the two changes may be applied together.
- The witness file adds `fragment-sizes`.
- The branches `analyze.md` gives no witness, because they fail Fit, are not formed: `$Adjacency4` (train0), `$AllPlacements` (train0, train1), `$MatchUpToD4` (train0) and `$AnchorByRarestColor` (train2).

## Judgments
- The solver works: every train and test pair passes, lint is clean, the audit is clean apart from the skipped `store` check under Unsettled, and the determination run is ok.
- The Not formed item ("drawing only the cells a copy adds") is not formed. As `analyze.md` states, it draws the concept's output on every input, so it fails Equivalence.
- Hint `case section` (the `case_ov` clauses that name `$GroupByReach`): moved under the `$LargestMatch, $UniqueDotPlacement, $MostDotsPerDot` and `$GroupByReach` markers.
- Hint `case section` on the clause that writes erased dots to `out`: its head now names `$EraseUncovered`.
- Hint `common-subexpr` in `within.shape` and `within.cell`: the shared atoms are factored into `larger`.
- Hint `common-subexpr` in `Determine`'s `contradicted`: merged into one disjunction.
- Hint `common-subexpr` between `shape_obj` and `dots_obj` under `$ShapeBySize`: kept, with `@ignore`. The two clauses are the two sides of one size threshold.
- Hint `determine prediction`: the first `group_reach` determination tested guessed reaches against facts of the inputs and outputs together. It was replaced by a fact of the inputs alone.
- `shape_min_size` determination: it keeps a threshold where every train object of at least that many cells holds several colors and every smaller one holds one, which gives 3, 4 and 5.
- `group_reach` determination: it keeps a reach where no dot group lies on the shapes at more than one translation, and every group of more than one dot lies on them at one. This is the scene claim `dots-from-one-shape` at that reach, and it gives 2, 3 and 4.
- Both determinations draw candidates from `sub_extent` of the train inputs. For a reach, a distance across the frame, that is a grounded domain. For a size threshold the grounding is loose.
- `bg_corner` has no determination relation: the plan lists it as undecided.
- Witness `group_reach=SepTileCount`, judged `variant concept`. A one-row, two-cell shape is unusual, but the input breaks no scene claim. The derived reach is a separator tile count, which nothing in the task reads.
- Witness `fragment-sizes`, judged `variant concept`. Its fragments of 3 and 4 cells are larger than any in the task, and it breaks no scene claim. I built it because the audit found that removing any one `shape_min_size` value changed no output. Thresholds 3, 4 and 5 now give three different grids.
- Witness `reach-steps`, judged `variant concept`. Lone dots three and then four columns apart, like `near-groups`. I built it because the audit found the same for `group_reach`. Reaches 2, 3 and 4 now give three different grids.
- Witnesses `shape-at-top-right`, `shape-at-bottom-left` and `shape-at-bottom-right`, judged `ordinary concept`, as `analyze.md` judged `shape-at-corner`, whose D4 images they are. I built them because the audit found that removing `bg_corner` TR, BL or BR changed no output.
- `witness` without `--file` reported no unseparated pair and no undifferentiated case. After the witnesses above, the audit's open-values check passes.
- Keywords are `objects markers stamp count rank merge`. `count` covers `$ShapeBySize` and `$MostDotsPerDot`, `rank` covers `$MostDotsPerDot`'s maximum, and `merge` covers `$GroupByReach`.
- Proposed gloss change for `merge`: it reads "like-valued pieces …". `$GroupByReach` fuses dots of different colors that are within a reach, so the gloss could drop "like-valued".
- Performance: a run takes 5–17 s. `candidate` and `landing` are computed for each `CopyPastEdge` × `CopyOverCells` pair, although only `misfit` depends on them. This keeps one `Copy` key, at about four times the rows.
- `src/` was not read.

## Unsettled
- The audit's `store` check skipped `paint` and `seat`, which have over 20000 rows on an input. A `store` run with a higher row cap would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
