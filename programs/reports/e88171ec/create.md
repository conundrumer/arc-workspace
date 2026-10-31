# e88171ec

## Departures
- The `tie` choice point and its branch `$TieUndefined` are not in the solver, and the witness file drops `$TieUndefined` from every group, including the undefined group of `two-holes`: the branch fails Subsumption. Where it is defined, its output is the output of the case that takes `$EachTied` with the same ranking, and `witness` found no run showing it defined and different. `analyze.md` gives the same result. `two-holes` stays because it separates `$RankPerimeter` from the concept, and its `separates` text now says that. Its `@witness` line now stands under `$RankPerimeter`.
- `fill-inset` takes the restated rule that `analyze.md` gives (the generator fills the inside of the box it placed). The concept file's largest-area rule stands under that rule as its `@approximated:` line: the placed box is not a fact of the grid, so the restated rule has no relational form. For the same reason, `thin-extension` (verdict `$RankInterior` at `ordinary`) does not call for a fix to the concept case: the approximation disagrees with the rule on that witness.
- Added witness `grown-hole` (`ordinary other`, under `@approximated:`). It is train1 with (7,7) and (7,8) set to 0, so that noise grows the 4x4 hole into a 5x4 rectangle. Every case fills the 5x4 rectangle's inside, and the generator fills the 4x4 inside. Each case runs an approximation of the placed box, and the header needs a witness on which each such case's output is not the verdict. This witness is that for all of them.
- Added witness `wide-noise` (`ordinary $RankMinSide`, under `$RankMinSide`). It is train1 with five cells set to 0, so that noise makes a 3x7 rectangle beside the 4x4 hole. Area and inside area pick the 3x7 rectangle, and the shorter side keeps the 4x4. `witness` reported that no witness separated `$RankInterior` from `$RankMinSide`. The clauses of the two branches differ, and this input separates them. The verdict is `$RankMinSide` because the generator placed the 4x4 box.

## Judgments
- `wide-noise` and `grown-hole` are `ordinary`: train0 (5,3) and train2 row 11 show that the generator lets hole-color noise touch the box, and each witness changes at most five cells next to the hole. Neither witness breaks `one-largest-hole`.
- The rectangles are enumerated from the input as a Slide over hole-color runs, then a Reach along each base line, then a Bbox. This follows the draft a64e4611, which is not a precedent. The program never computes a box that is not empty.
- `$RankPerimeter` ranks by a Tally of the distinct (axis, line) pairs that a rectangle's cells lie on, which is rows plus columns, so the program does no arithmetic and treats both axes alike.
- `$RankInterior` combined with `$FrameAsHole` ranks by the inside at the margin on every side, and fills by the FrameAsHole rule. This applies the two changes together, as `analyze.md` gives.
- The determination-plan's first run listed `fill_color` (AnyOutNewColor), `hole_color` (SharedColor) and `margin` (DivisorRatio). `margin` matched DivisorRatio only by chance, because the input and output have the same size. Determine derives the two colors from the cells each pair changes. It derives `margin` as the narrowest run of hole color between the painted block's side and the first other color, through a Ray over each train pair. The second plan run listed no actions.
- Deletions hints kept: the `dir_elem` atoms narrow Dir8 to Dir; `rim.d`, `kept.*` and `!dist(B, D, 0)` carry `$FrameAsHole`, and no pair touches the grid edge; `inner.domain` gives a 0 score to rectangles with no inside, and without it those rectangles have no score in Order; `!rim` and `secondary_score` are the claims of their branches; the Determine guards keep the determination to pairs that have outputs. Removed: the `blank(_)` guard, `area.domain`, `span.domain`, and a `changed` atom that `gap.clear` implies. The `blank` relation was inlined after its single-consumer hint.
- `deletions` ran twice. The first run was before the edits that it led to, and the second run came after the last edit.
- `store` printed no line to add, and `derive` found no derivation that fits.

## Unsettled
- The four branches that are not concept branches are witnessed only alone. The cases that combine a ranking branch with `$FrameAsHole` are not witnessed cases: a witness of a 6x6 or larger hole on the grid edge where the rankings differ would settle whether those combinations are distinct cases.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
