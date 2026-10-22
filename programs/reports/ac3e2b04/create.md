# ac3e2b04

## Departures
- The Analyze branches `line_color=derived` and `mark_color=derived` are the constructors `$DerivedLineColor` and `$DerivedMarkColor`. The witness file uses those names, and their witnesses have the ids `derived-line-color` and `derived-mark-color`: the Witness file section reads `<rel>=derived` only as a branch of a `@store` point, and `derive` offers no derivation of either parameter, so a constructor is the only form that holds them. The draft a04b2602 does the same with `DerivedRoles`. With the names rewritten, every Analyze witness gives the outputs the Analyze file gives.
- The concept case, and every case at `$LineCenter`, is undefined on an input with a mark on no full-length line. The Analyze report gives only a mark on lines of both axes as undefined. Such a mark has no marked line to take a right angle from, and it breaks `marks`. No witness has such an input.
- New branches from Not formed, each in every combination with the others, all fitting every pair:
    - `$MarkRadius`: a stored `mark_radius` (1) sets the square a mark fills and the square a frame covers. Witness `mark-radius`: the `copy-mark` input with `mark_radius` reassigned to 2.
    - `$BothAxes`: under `$AnyCenterMark`, a mark on no line sends new lines along both axes. Its witness is `ring-off-line`.
- New witness `two-lines-in-4` (train 0 with its lines in 4). `witness` reported that no run showed `$DerivedLineColor` defined and differing from `$AnyCenterMark & $BothAxes & $StoredLineColor`. This input shows it, so that case meets Subsumption.

## Judgments
- A full-length line is a row or column whose every cell is the line color or the mark color. A mark of any size on a line then keeps the line whole, which is what `copy-mark` needs, where a 5×5 mark covers line cells outside a 3×3 box.
- `$CopyMark` joins mark-color cells to the ring by 4-adjacency (`Components`).
- Plausibility and verdict of `mark-radius`: `borderline $MarkRadius`, relaxed `marks`, reassigned `mark_radius`. It has the same scene as `copy-mark`, and a generator that drew 5×5 marks would frame crossings at that size.
- `ring-off-line` under `$BothAxes`: `borderline concept`, relaxed `marks`, as under `$AnyCenterMark`.
- `two-lines-in-4`: `variant $DerivedLineColor`, relaxed `parallel-lines` and `marks`. It is a color-permuted train pair.
- `@derive DominantColor` on `background`: `variant derived`, relaxed `parallel-lines`. `@derive RarestColor` on `mark_color`: `ordinary concept`. Both are as the Analyze report gives them.
- `line_color` from a proposer (Not formed): `derive` lists no derivation of `line_color`, so there is no branch.
- Branches dropped under Fit, as the Analyze report gives them: `$OverpaintCrossing`, `$FrameOverBackground` and `$StopAtLastLine` (train 0), and `draw_color=OutNewColor` and `draw_color=AnyOutNewColor` (no value on one input, and `derive` does not list them).
- `store`: `roles` reads back the stored `line_color` and `mark_color`. The other values it lists have no case. So there is no `@store` branch.
- Hint `comp-idiom` on `undefined`: applied, `perp(A1, A2)`.
- `deletions`: 24 removals change no pair. Each one is an edge condition of a scene claim (`whole`, `interior`, `inside(B, ZERO)`, the off-grid clip `in(R, _)`), an undefined condition, a non-concept branch the pairs do not separate, or `!mark` in `$KeepMarks`, which only `aligned-marks` exercises. All are kept. Simplify replaced a local defect clause for a uniform ring with a `Unanimous` instance.
- Every rule has a relational form, so no rule is approximated.
- Sweep and determination plan: no actions. Each parameter is covered on the examples (`DominantColor`, `AnyOutNewColor`, `SharedColor` narrowed, `RarestColor`, `DivisorRatio`), so the solver has no Determine comp.
- Keywords: `lines markers cast cross stamp`. `stamp` covers the frame footprint at each crossing, and the mark's own shape under `$CopyMark`.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-3_task_ac3e2b04_create.md
