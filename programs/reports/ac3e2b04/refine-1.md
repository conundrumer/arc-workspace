# ac3e2b04

## Departures
- (create) The Analyze branches `line_color=derived` and `mark_color=derived` are the constructors `$DerivedLineColor` and `$DerivedMarkColor`, and their witnesses have the ids `derived-line-color` and `derived-mark-color`: the Witness file reads `<rel>=derived` only as the concept branch of a `@store` point, and `<param>=stored` only as the concept branch of a `@derive` point. Here the concept stores both colors, and `derive` offers no derivation of either, so a constructor is the only form that holds them. Judged again: it holds. A `witness --file` run on a copy of the Analyze file, with those two names rewritten to the constructors, prints `witness: ok`.
- (create) The concept case, and every case at `$LineCenter`, is undefined on an input with a mark on no full-length line. The Analyze report gives only a mark on lines of both axes as undefined. Such a mark has no marked line to take a right angle from, and it breaks `marks`. No witness has such an input. Judged again: it holds.
- (create) New branches from Not formed, each in every combination with the others, all fitting every pair. Develop step 3 requires them, and the audit's `witness` check shows each case defined and differing from every other.
    - `$MarkRadius`: a stored `mark_radius` (1) sets the square a mark fills and the square a frame covers. Witness `mark-radius`: the `copy-mark` input with `mark_radius` reassigned to 2.
    - `$BothAxes`: under `$AnyCenterMark`, a mark on no line sends new lines along both axes. Its witness is `ring-off-line`.
- (create) Witness `two-lines-in-4` (train 0 with its lines in 4) shows `$DerivedLineColor` defined and differing from `$AnyCenterMark & $BothAxes & $StoredLineColor`, so that case meets Subsumption.

## Judgments
- Checks: the solver passes train 0–3 and test 0 with 12 witnessed cases, lint is ok, and the audit (witness, dropped cases, derive, store) is ok. `sweep` gives one value per parameter, and `determination-plan` lists no actions.
- `deletions` (24 of 82 change no pair): the same set that create judged. Each one is an edge condition of a scene claim (`whole`, `interior`, `inside(B, ZERO)`, the off-grid clips `in(Q, _)` and `in(R, _)`), an undefined condition, a clause of a non-concept branch that the pairs do not separate, `!mark` in `$KeepMarks`, which only `aligned-marks` exercises, or `around(Sz, P, S_ring)` in `$CopyMark`, which ties the copied ink to the mark's own ring and which no pair exercises because train 1's second mark lands off the grid. All are kept.
- Simplify and Prune: no change. The clauses state each branch once with lib relations, and the header and branch lines are the concept's claims and each branch's change to them.
- (create) A full-length line is a row or column whose every cell is the line color or the mark color, so a mark of any size on a line keeps the line whole, as `copy-mark` needs.
- (create) `$CopyMark` joins mark-color cells to the ring by 4-adjacency (`Components`).
- (create) `mark-radius`: `borderline $MarkRadius`, relaxed `marks`, reassigned `mark_radius`. `ring-off-line` under `$BothAxes`: `borderline concept`, relaxed `marks`. `two-lines-in-4`: `variant $DerivedLineColor`, relaxed `parallel-lines` and `marks`.
- (create) `@derive DominantColor` on `background`: `variant derived`, relaxed `parallel-lines`. `@derive RarestColor` on `mark_color`: `ordinary concept`. `derive` lists these two alone, and lists no derivation of `line_color`.
- (create) Branches dropped under Fit, as the Analyze report gives them: `$OverpaintCrossing`, `$FrameOverBackground` and `$StopAtLastLine` (train 0), and `draw_color=OutNewColor` and `draw_color=AnyOutNewColor` (no value on one input).
- (create) `store`: `roles` reads back the stored `line_color` and `mark_color`, and the other values it lists have no case, so there is no `@store` branch.
- (create) Hint `comp-idiom` on `undefined`: applied, `perp(A1, A2)`.
- (create) Every rule has a relational form, so no rule is approximated.
- (create) Keywords: `lines markers cast cross stamp`.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-7_task_ac3e2b04_refine.md
