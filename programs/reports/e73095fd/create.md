# e73095fd

## Departures
- `$OutlineBox` finds its candidate rectangles as the bounding box of two rectangular `background` regions, one giving the top-left cell and the other the bottom-right cell. The probe in `work/task/e73095fd/probe.py` tries every rectangle. The two differ only on a rectangle whose first or last row or column is itself a whole `wire` line inside it, which is a crossing line that lies against the ring. On every pair and every witness, the outputs are the same: `witness --file programs/reports/e73095fd/witnesses.json` reports no difference.
- The header's `@rule fill-box-inside` states the relation the program runs: a box is a `background` region that is a rectangle, whose ring of cells is `wire` where it lies on the grid, and whose ring corners on the grid are true corners. The rule has a relational form, so it has no `@approximated:` line and no witness under it. `band-between-lines` and `side-continues-past-corner` stand under their branches only, and `@relaxed box-outline` of `side-continues-past-corner` stands under `$SomeTrueCorner`.
- I added the witness `third-color`. Before it, no witness separated `background=DominantColor` from `wire=RarestColor`, because on an input of two colors the two derivations agree. On `third-color`, one cell has a third color, and that color is rarer than `wire`.

## Judgments
- `third-color`: borderline, verdict concept. The stray third color breaks `wire-network`. The generator draws two colors only, so a third color comes only under unusual conditions. The box is still a box of the concept, so the generator would fill it.
- Determine: `background` and `fill` are the input and output colors of the cells that a train output changes. `wire` is the color of an unchanged cell beside a changed cell. The plan reports all three as determined.
- Lint hints: the `common-subexpr` hint on `stray` showed that `stray` and `broken_line` repeat the span-cell join, so `span_cell` now holds that join. The `case section` hints showed that the marker of the shared box tests did not list `$OutlineBox`, and the marker now lists it.
- `deletions`: the 40 deletions that change nothing remove the tests of the non-concept branches, the `OutlineBox` span tests, and the ring tests. On the pairs, no pair has the structure that those tests guard against. The witnesses separate each of those branches. `!inside(W, B)` in `met` stays, because a `$OutlineBox` box holds `wire` lines inside it. The two bound enumerators stay, as the tool says they do.
- Keywords: `objects bbox enclose`. A box's inside is closed off by its `wire` outline, with the grid edge standing in for a missing wall. The bounding box of a region decides whether that region is a rectangle.
- `$WholeBoxOnly`, `$NoCornerTest`, `background=SharedColor`, `background=RarestColor`, `wire=SharedColor`, `wire=DominantColor`, `fill=OutNewColor` and `fill=AnyOutNewColor` fail Fit, as `analyze.md` gives. They have no constructor and no derive line. No item under Not formed states a model that fits and differs from a formed one.
- The audit checks all passed, and none were skipped. The pairs run passes all 4 pairs with 8 witnessed cases of 96.

## Unsettled
- `$OutlineBox` is not checked for equivalence with the probe's every-rectangle model on an input where a crossing line lies against the ring. A witness with such a line, run against the probe, would settle it.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- none
