# b6afb2da

## Departures
- The solver and the witness file carry `$BorderTurns`, a third branch of `role-reading` that the Analyze files do not hold: Develop step 3 forms the Not formed claim (the border is the cells missing an 8-neighbor, and a corner is a border cell with border cells it joins on both axes). The branch meets Fit on every pair and has a relational form. On `notched-block` it gives (3,3), (3,4) and (4,3) `corner_color`, which no other case gives.
- The groups of `programs/witnesses/b6afb2da.wit.json` name the solver's constructors (`$ShapeCells`, `$MixedColors`, `$BoxRoles`, `$Border4`, `$BorderTurns`, ...) in place of the Analyze file's `concept` and branch-only names: `record --all` rewrote them. `witness --file work/task/b6afb2da/witnesses.json` reports no difference.

## Judgments
- Choice shape: `Choice = [cells: Cells, role: Role]`. `Cells` is `ShapeCells | AnyNonBackground {color: ObjectColor}`, and `ObjectColor` is `MixedColors | PerColorObjects`. `Role` is `BoxRoles {adjacency: Adjacency} | CellNeighbors {border: Border} | BorderTurns`. The nesting follows the Analyze report's choice points. Concept constructors take my names: `ShapeCells`, `MixedColors`, `BoxRoles`, `Objects4`, `Border4`. `impl_choice` is the full product, 15 cases. The run witnesses 7 of them, and `witness` reports no unseparated pair and no case left undistinguished.
- `$EdgeInside` gets no constructor: the Analyze report gives it no witness, because it fails Fit at train0.
- Parse: one relation `link(c, p, d, q)` states which touching rectangle cells join. `$PerColorObjects` adds `apart` facts for touching cells of different colors. `$BoxRoles` forms objects as the `Canon` classes of `link`, with `$Objects4` taking cardinal links and `$Objects8` all eight. `$CellNeighbors` and `$BorderTurns` read `open_dir`, the complement of `link`, so a cell past the grid edge counts as outside. Rests on these facts:
    1. `Components` takes its steps per instance, not per key, and cannot keep cells of different colors apart within one key.
    2. A first draft therefore needed 4 `Components` instances and 2 `Rim8` instances, keyed by `Cells` for the mixed readings and by `Color` for `$PerColorObjects`.
    3. `store` then flagged the per-color `Color` key (5 on every train input) on `color_objects.node` and `color_rim8.cell` as stored-reading branches. Those branches came from the key alone, and the concept does not give them.
    4. With `link`, the concept case still reads 4-connected objects of `shape` cells, and `store` and `derive` report nothing to hold.
- `apart` covers every touching pair of differently colored cells, not only rectangle cells: `link` reads it only between rectangle cells, so the narrower body changed nothing (`deletions`).
- `deletions` lists 9 deletions that change no pair. Each one removes structure the pairs never instantiate: the self edge for an isolated cell, `dir_elem` on `$Objects4` (no diagonal-only contact), `apart` (one non-background color), and the `$Border8` rim clause (no notch). All of them are kept. The 4 bound enumerators are kept as the report directs.
- `$BorderTurns` witness: `notched-block`, `foreign $CellNeighbors`. That is the witness's one verdict, and the generator never draws a notched block.
- `background` is a Scene parameter in the concept file. It is in Params under `$AnyNonBackground`, the branch that reads it. `@scene background` gives its value 0.
- `@claim`: `Canon` is a construction, so its instance has no directive. `Bbox` carries `@claim corner edge interior`.
- Keywords `objects bbox border`.
- Determine: `sweep` gives a unique value for each parameter, and `determination-plan` lists no actions, because every parameter is covered on the examples. The solver has no Determine comp.
- No built-in derivation fits (`derive`), and `store` prints no `@store` line, so the solver has no `@derive` or `@store` branch.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- none
