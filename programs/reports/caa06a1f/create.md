# caa06a1f

## Departures
- The witness `block-bottom-left` and the `@store` witness `parse.block_at=stored` carry `@relaxed background-band` beside `@relaxed periodic-block`, which is the only claim `analyze.md` gives: at the stored `block_corner` (top-left), `background-band` says the band lies along the bottom and right edges. On each of those inputs the band lies along other edges, so the claim is false of them.
- `$DeriveCorner`'s `periodic-block` text says the rectangle holds the corner's cell, where `analyze.md` says the rectangle "sits at that corner": `Parse.block_at` tests that the corner's own cell is off the band, and that on some axis no off-band cell reaches the edge of the opposite corner. That is the bounding-box test with the corner's cell required to be a block cell.
- The witness file has three witnesses that `witnesses.json` does not have: `block-top-middle`, `stored-corner-elsewhere` and `block-full-width`. They resolve the pairs of cases that `witness` reported unseparated (see Judgments). It also has the `parse.block_at=stored` witness that `store` wrote.

## Judgments
- The parse follows the precedent of 484b58aa: each cell's place along each axis is its edge distance modulo the block's `min_period` (from `OffsetInvariance`), and a cell's class is its pair of places on two perpendicular edges. Places are taken from every edge, so the classes do not depend on an orientation. Like 50a16a69, the shift sends each block cell's color to the class of the cell it moves to. Because of that, no off-frame cell needs a class.
- The block test and the band color are in `Parse<Key>`, keyed per corner, so that `Determine` reads the same derivation per example.
- `$ColorSuccessor` needs a direction for "follows". `analyze.md` says this branch reads no `shift_dir`, so the branch has its own parameter `follow_dir` (right). The sweep found that the train pairs admit all four directions and the test refutes three. `follow_dir` is not open, because the test pair separates its values. The determination keeps the directions that point away from the block's corner and along which each block color has one successor in every input. On test0 that leaves right alone, because down gives 5 two successors.
- `[$ColorSuccessor, $DeriveCorner($ShiftTowardCorner)]` is left out of `impl_choice`. `$ColorSuccessor` reads no shift direction, so `$ShiftTowardCorner` changes nothing in that case. Its model is the model of `[$ColorSuccessor, $DeriveCorner($Absolute)]`, and it takes more non-concept branches, so it fails Equivalence.
- `store` reported `block_at` as one value (top-left) on every input. The `@store block_at` line above `.init parse` records that branch (no test that the block sits at the corner), at `variant stored`. Its witness is train 0 turned a quarter turn: the concept is undefined, and the generator's output is the checkerboard that the stored branch gives.
- `witness` reported that no run showed `$StoredCorner & parse.block_at=stored` defined and differing from `$DeriveCorner & $Absolute`. Witness `block-top-middle` resolves it: the block touches the top edge at no corner. The stored-`block_at` cases give the continued pattern, and every derived-`block_at` case is undefined. Plausibility `foreign` (the generator always puts the block at a corner). Verdict `stored`, since the stored cases continue the pattern one cell left and up.
- `witness` reported that no run showed the `$ColorSuccessor` case with `block_at` derived defined and differing from the same case with `block_at` stored. Witness `stored-corner-elsewhere` resolves it: the three-color-cycle input at `assign` `parse.block_at` = bottom-right. The derived case gives the left move, and the stored case is undefined, because the bottom-right corner is not `block_corner`. Plausibility `variant` (a half-turn variant stores bottom-right). Verdict `concept`.
- `witness` reported that no run showed `$StoredCorner` defined and differing from `$DeriveCorner & $Absolute` among the `$ColorSuccessor` cases. Witness `block-full-width` resolves it: the block spans the full width, so both top corners hold a block. The stored-corner cases are defined, and `$DeriveCorner` is undefined. Plausibility `borderline` (the band lies along one edge only). Verdict `any`.
- `shift-amount` branches `$ShiftByBlockExtent` and `$ShiftByBandWidth` are not constructors: both fail Fit, as `analyze.md` states (test0 and train0 give the unmoved pattern).
- Not formed items: the color table fails Fit (Unseen key), and the color swap fails Fit at test0. The background read from a whole edge row and column is defined only where the band covers both far edges, and there it gives the concept's output, so it fails Subsumption. The continuation along every period translation gives the concept's continuation wherever `periodic-block` holds. No `@derive` line: `derive` reports that no built-in derivation fits.
- Determination: `block_corner` is the corner where every example's input holds a block. `shift_step` is the least step at which no train output disagrees with the block moved toward a value of `shift_dir`. The plan's proposer for it, `DivisorRatio`, is a ratio of grid dimensions and has no relation to the step. `shift_dir` and `shift_axis` are left undecided, as the plan gives. The open values are left and up from `analyze.md`. The sweep found that down and right also fit the train pairs, and the test refutes them.
- Hints: `head-repeat` on `shift` is kept under `@ignore`. The open-value column records the stored direction, and the direction column is what the move reads in every case, including `$ShiftTowardCorner`, whose open value is an axis. `single-consumer` on `class_color` is kept under `@ignore`, as in 484b58aa. `corner_color` was inlined to resolve its `single-consumer` hint. The relation `band` was renamed to `band_color`, because `band` is a Souffle reserved word.
- Deletions: the `parse.block_at` atoms in `period.cell` and `successor.item` were removed, because `corner` already restricts every reader to a corner that holds a block. The aperiodic disjunct of `place`, the corner key columns, `params.shift_axis` (a set that 50a16a69 narrows to one axis) and the determination's defect relations stay. Each of them states a part of the model that the pairs do not exercise.
- Keywords: `wallpaper`, `move`, and `mapping` for `$ColorSuccessor`'s successor recoloring.
- Performance: none. Each run takes a few seconds or less.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
