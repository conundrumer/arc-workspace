# b4a43f3b

## Departures
- The solver adds the parameter `halves_axis` (AXIS_V) under `$PictureByBlocks` and `$PictureByColors`: these branches replace `pattern_side`, and the Analyze report gives them nothing that fixes the axis the two halves lie along. Under `$StoredSide` the axis comes from `pattern_side`, so it is derived there and not stored a second time.
- The solver adds the branch `pattern_scale=SepTileCount` (`@derive SepTileCount: variant concept`), which the Analyze report does not have: `run_dl.py derive` lists it as fitting, because the separator lattice has two segments and the scale is 2. Its witness `pattern_scale=SepTileCount` (a 2×2 picture in 3×3 blocks, at `pattern_scale` 3) shows the concept defined and the branch undefined.
- The witness file has three witnesses that the Analyze file does not have: `pattern_scale=SepTileCount`, `separator-count-scale-3` and `halves-4x4`. The last two resolve the `witness` findings that no run showed the SepTileCount case defined and differing from the stored-scale case, or from the `$StoredPictureExtent` case.
- `record --all` rewrote the group names of the Analyze witnesses to the listed forms. `witness --file work/task/b4a43f3b/witnesses.json` reports no difference.

## Judgments
- Under `$PictureByBlocks`, "the half is in blocks" reads as: the case's cut of the half is whole, puts one color in each block, and has blocks of more than one cell. With `$ScaleFromBlocks`, this is the Analyze report's "largest block side exceeds 1". With the stored scale or the stored picture extent, it is the plain block test.
- The cut that `$StoredScale` and `$StoredPictureExtent` read makes no separate test for blocks with two colors. A block with two colors gives two colors at one picture cell, so the case is undefined there, as the Analyze report gives.
- Not formed, stored output extent: I built it as a `Size` choice point and ran it. Where it is defined, it gives the concept's output, and no input at any assignment shows it defined and differing. It fails Subsumption, and I took it out.
- Not formed, the other items: the full-resolution picture is `pattern_scale` 1 and fails Fit. SharedColor and RarestColor for `background` fail Fit, and `derive` lists neither. `derive` lists no fitting derivation of `mask_color` or `separator_color`. `$SeparatorAnyLine`, `$StampInMaskColor` and `$SelfFractal` fail Fit per the Analyze report, so I did not build them.
- `store` on `half_ink.value` (one color, 2): a stored value per half fixes the mask's half by its edge. The case is then equivalent to `$StoredSide`, and it takes more non-concept branches. It fails Equivalence: `@ignore value: store`.
- `store` on `block`: a stored cut covers only halves of the pairs' extent, and there it is the derived cut. It fails Subsumption: `@ignore: store`.
- Hints: the case-section hints on `axes`, `pattern_side` and `halves_axis` came from computing the halves only for the axes that some case's parameters gave. Now the dividers are computed on both axes, and each case picks its halves through its own parameter. The head-repeat hint on `halves_of` (Split twice) went away when `picture_side` replaced it, keyed by the picture's edge.
- Deletions: I removed `half_cell` from `half_px`, because the half's box with `crop` already implies it. I removed the "cell no block holds" disjunct from `broken`, because `divide_by_size_2d` and `divide_2d` decompose either every cell or none. I removed `cut` from `blocky`, because any whole cut with blocks of more than one cell is the same test. I kept the other deletions that change nothing, because each one guards a case's undefinedness on an input that the pairs do not show: two halves in blocks, two one-color halves, several separator lines, a dividing line on both axes. I also kept the `side_cand` disjunct for the full extent (`solid-picture` needs it) and the `divider` axis column, which states the axis the halves lie along.
- Witness `pattern_scale=SepTileCount`: `variant concept`. It is a scale-3 variant with a 2×2 picture in 6×6 halves, and that variant's generator pairs the concept's 12×12 output.
- Witness `separator-count-scale-3`: train0 at `pattern_scale` 3. It breaks `scaled-picture` at that assignment, and a scale-3 generator does not produce a picture in 2×2 blocks, so I judge it `foreign`. It shows that the SepTileCount case is defined and differing, which is all it is for. The solver has no `@witness` line for it.
- Witness `halves-4x4`: `variant concept`. It breaks `half-extent`. The concept, `$ScaleFromBlocks` and SepTileCount give the 8×8 output, and `$StoredPictureExtent` is undefined.
- Determine: the sweep finds only the stored value of each parameter, and the plan lists no actions, so the solver has no `Determine` comp.
- Keywords: `decompose` (the separator cuts the input into halves), `crop` (the picture half gives the content), `scale` (the picture read down, the mask blown up), `tile-arrangement` (the output arranges copies of the picture), `stamp`.
- The run gives 9 witnessed cases of 96. Every pair passes, and lint and the audit are clean.

## Open
- The `@derive SepTileCount` line's witness stands at `pattern_scale` 3. Only the witness file's `assign` records this, because the audit refuses `@reassigned` under a `@derive` line. A form for that line would settle it (ticket 10-357).

## Lib
- Centered on one axis: `axis_of(D, A), dist_pair(P, D, K, K)`, the per-axis form of `centered`. Solver-local form here: `divider($MiddleLine(), A, L) :- in(P, _), axis_elem(A), split(P, A, L, _), axis_of(D, A), dist_pair(L, D, K, K).` The grep finds the same shape in `programs/solvers/c48954c1.dl:44` (`axis_centered`), `programs/solvers/d23f8c26.dl:37`, `programs/solvers/29c11459.dl:92` and `programs/solvers/00576224.dl:69`. A lib relation `axis_centered(p: Box, a: Axis)` would state it.

## Fixes elsewhere
- none

## Tickets filed
- 10-356_task_b4a43f3b_create.md
- 10-357_task_b4a43f3b_create.md
