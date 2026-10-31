# f9a67cb5

## Departures
- The header has no `@scene walls-apart` line: no `@claim` or `@relaxed` line names it, no rule text depends on it, and no branch replaces it ([Style: Header](docs/handbook/style.md#header)).
- `background=DominantColor` is a case, with the witness `background=DominantColor` in the witness file: `run_dl.py derive` reports that DominantColor fits `background`, a parameter that only `$WallAnyColor` reads. `analyze.md` gives no such branch, because the concept case has no `background` parameter. Develop step 4 holds every built-in derivation that fits.
- `water_color=stored` is a `@store` line on the program relation `water_color`, the color of the spout cell. It is not a constructor. `analyze.md` gives the branch with a witness, and Develop step 4 holds it whatever `store` reports.
- The concept constructors are named `WallColor` (wall-color point) and `DrainCell` (gap-drain point).

## Judgments
- `@derive DominantColor: variant derived` with `@relaxed background` on `background`: its witness is train0 with colors 0 and 1 swapped. A color permutation of an input is routine in a variant task. At the stored assignment (background 0), `$WallAnyColor` reads every 1 cell as wall and gives the input back, and the derived background gives the water flow that the generator would pair with the input. That input breaks the `background` scene claim.
- `run_dl.py store` printed "make it a parameter" for `water_color` and gave no `@store` form. I wrote `// @store: ordinary concept`, which is the plausibility and verdict of the `water_color=stored` witness. The runner accepted it, and the case is witnessed. Lint rejected `@reassigned` under a `@store` line, so that witness's reassignment of `water_color` to 3 is only in its `assign`.
- Water never enters a wall cell sideways (`!wall(Q, W)` in `beside`). The rule does not say this. It matters only on inputs that break `walls-apart`, and `deletions` reports that it changes no pair.
- Hint `common-subexpr` on `beside`, kept with `@ignore`: `beside` steps across the flow and `ahead` steps along it. They share only the frame.
- Hint `common-subexpr` on the two `water.edge` clauses: merged into one disjunction.
- Hint `single-consumer` on `water_color`: resolved by the `@store` line. The relation is that point's derived branch.
- Hint `determine prediction` on `Determine.wall_color`, kept with `@ignore`. The clause reads the value from the evidence: the input color that is neither the spout's nor the color the water paints over.
- Determination: `source_color` is the color the outputs paint; `background` is the color the water paints over; `wall_color` is the remaining input color. `determination-plan` reports no actions.
- `deletions`: seven deletions change no pair. These are `!wall(Q, W)` in `beside`, which is kept as above, and `!source(P)` in the `$WallAnyColor` wall, which is kept because the branch excludes the source and water never flows back onto it. The other five are the `$DrainWholeGap` gap rule and edge, which no pair reaches because every gap in the pairs is one cell wide.
- Not formed: no item in `analyze.md` states a model that fits. The whole-basin fill and the short-stopping spread fail Fit, several sources give the concept's output, and the off-edge source has no reading. So Develop step 3 adds no branch.
- No wall_color derivation fits (`derive` lists none), so the parameter has no `@derive` or `@ignore: derive` line.
- `witness` and `witness --file programs/reports/f9a67cb5/witnesses.json` both report ok after `record --all`. The audit is clean.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- `scripts/run_dl.py store`, the message for a derived relation with one value on every input: it suggests "make it a parameter" and gives no `@store` line to add. Develop step 5 expects the command to print the directive line.

## Tickets filed
- none
