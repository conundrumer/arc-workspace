# d4a91cb9

## Departures
- I replaced the parameters `start_color`, `end_color` and `start_axis` with one relation, `leg_mark(a: Axis, c: Color)` = {(AXIS_V, 8), (AXIS_H, 2)}. It gives, for each axis, the color of the mark whose leg runs along that axis. The header rules `corner` and `l-path` are restated in its terms. This rests on the Determine step: "a different parameterization would give a simpler or more principled model". Under the old parameterization, the assignments (8, 2, V) and (2, 8, H) agree on every input, because an L path from the 8 down its column and along the 2's row is the same set of cells as the path from the 2 along its row and up the 8's column. Choosing one of those two assignments from the evidence means preferring an axis or a color by a literal, so no equivariant determination exists. The keyed form is the Payload rule of [Orientation](docs/handbook/principles.md#orientation): a value that varies by axis is stored keyed by the axis. It has one assignment per output. The concept case's output is unchanged: it passes train0–2 and test0, and it gives the `concept` grids of both witnesses in `witnesses.json`, checked on the second witness's input with `grid`.
- Because of that change, the branches `start_color=RarestColor` and `end_color=RarestColor` from `analyze.md` have no case. After the change, `derive` reports "no built-in derivation fits", because RarestColor proposes a set of colors and `leg_mark` is keyed by axis. Before the change, both branches were written as `@derive RarestColor: borderline concept` with `@relaxed two-marks`. Their combination was dropped with `@ignore: derive end_color=RarestColor` because it fails Fit at train0, as `analyze.md` says. Both runs passed.
- I emptied the witness file (`"witnesses": []`). `witness` lists no case for the two derived-branch names, so I removed those names. Each witness was then left with `concept` alone and separated nothing, so I removed it. `witness --file programs/reports/d4a91cb9/witnesses.json` still fails, and only on those four names, which "denote no case of the solver". That is the departure above, not an error in `witnesses.json`.
- The solver has one case: no `Choice`, no case markers, and no `@witness` lines. `$StartByPlace`, `$CornerByLength` and `path_color=OutNewColor` fail Fit and have no witness in `analyze.md`, so none of them became a constructor or a `@derive` line.

## Judgments
- I dropped the `@scene` lines `two-marks` and `marks-off-line` at Prune. Style admits a `@scene` line only when `@claim` or `@relaxed` denotes it, a rule's text depends on it, or a branch replaces it. With the derived branches gone, none of those holds. If the marks share a line, the concept's corner falls on one of the marks and `Between` gives the straight run, the output `analyze.md` expects.
- `store` reported `leg.axis` in the first parameterization: the full `Axis` set, with no witness and no line to add. The Every value rule of [Orientation](docs/handbook/principles.md#orientation) keeps it enumerated in the program, so I did not hold it as a branch. After the change, `store` reports no findings.
- The only finding the sweep and the plan gave for `leg_mark` is that it is "undecided". Four single-row additions also reproduce every train pair: (V, 2), (H, 8), and a row of path color 4 or another color absent from the inputs. On these inputs each one either names a color no input holds, or puts a corner on the 2 itself, so it changes nothing. No reader of the concept would take any of them, so they are not open values and I stored none. The plan lists no action for `leg_mark`, so I wrote no determination relation for it.
- I wrote `Determine.path_color` as the colors in some train output and in no input (AnyOutNewColor), as the plan asked. The run reports `determination: ok (path_color)`.
- The lint hint `negated-use` on a helper `in_color` was correct, so I inlined it as `!ex_in(_, _, C)`.
- `deletions` found `same_line(A, P_mark, P_corner)` in `leg.axis` changing nothing. `Between` already finds nothing between a mark and a corner that are not on one line of the leg's axis, so I removed the atom and noted this in the comment on `leg`. I rechecked a two-end-mark input afterwards and it gives the expected grid.
- I removed a `@claim corner` line that I had put above the relation `corner`, because `@claim` is for component instances only. The `Between` instance keeps `@claim l-path`.
- Keywords: `markers span`, as in the precedent 0e671a1a, which joins marks with L-shaped legs.
- No performance issues: every run took 3 s or less.

## Unsettled
- Losing the RarestColor branches means the solver no longer covers a variant task whose mark colors change between inputs. To settle it, either a proposer that derives a payload keyed by axis, or a ruling that the redundant (start, end, axis) form is acceptable with a determination that breaks the tie.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/d4a91cb9/analyze.md`, the `start_color` and `end_color` lines under `corner`: they do not note that (`start_color`, `end_color`, `start_axis`) and (`end_color`, `start_color`, the other axis) give the same model output, which makes the stored assignment impossible to determine equivariantly.

## Tickets filed
- none
