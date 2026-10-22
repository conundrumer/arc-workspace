# b7256dcd

## Departures
- `$ShapeColorMulticell` has no constructor, and the witness file lists it in no group: it fails Subsumption. Where it is defined, its color is the one non-background color with more than one cell, which is also the strictly commonest one, so `$ShapeColorCommonest` gives the same output, and the same holds with every other branch beside it.
- The header has no `@scene marker-touches-at-most-one-shape` line: no `@claim` or `@relaxed` line denotes it, no rule text depends on it, and no branch replaces it, so Style leaves it out.
- The concept case keeps a cell of the background color only where that cell is not a cell of the shape color (`!shape_cell(S, P)` in the first `out` clause). This reads `keep-background` ("each other cell") literally. Without it, the case `background=DominantColor` gave a total all-6 grid on the witness `background=DominantColor`, where the Analyze file gives undefined; with it, the run agrees with the Analyze file.
- Witnesses `corner-joined` and `dominant-background` are added to the witness file. The Analyze file has neither of them.

## Judgments
- Develop step 3 formed `marker-touches-at-most-one-shape` (Not formed) as the branch `$OneShapePerMarker`: the output is undefined where a marker cell is 4-adjacent to two shapes. It met Fit and Relational form. It then failed Subsumption and left. Where it is defined, no marker touches two shapes, and the same case with `$AnyShapes` gives the same output. No input shows it defined and differing.
- The `@store` branches that `store` prints on `commonest.mode`, `commonest_one.item`, `commonest_one.value`, `multicell.item` and `multicell.value` (each 6) carry `@ignore ...: store` lines for Equivalence. A stored 6 there gives the model of the `$StoredShapeColor` case with the same other branches. The `multicell` lines went with `$ShapeColorMulticell`.
- `@derive DominantColor: borderline concept` on `background`, per the Analyze report's witness `background=DominantColor`.
- Witness `corner-joined`: `borderline $Shapes8`, `@relaxed one-marker-per-shape`. Two pieces of 6 touch at a corner, and only one marker touches the joined shape, so the piece a 4-connected reading leaves alone has no marker. A person reads the two pieces as one shape and colors it 3. A second marker, 4, two steps from the lone piece, makes `$Shapes8` differ from `$NearestMarker` too, which `witness` requires.
- Witness `dominant-background` (a further witness of `background=DominantColor`, with no `@witness` line): verdict `derived`, plausibility `borderline`. It is a one-row grid `6 6 3 0 0 0 7`, the only shape in which both backgrounds give a defined output: the shape's neighbors other than its marker must be shape cells or off the grid. A reader takes 0 as the background there. This task's generator draws inputs whose background is 7 and the commonest color, so only an unusual generator gives such an input.
- Concept constructors take these names: `Shapes4`, `MarkedOnly`, `OneMarkerCell`, `StoredShapeColor`. The cases are all 32 combinations of the four points, each also under `background=DominantColor`; `run` shows 8 witnessed cases, and each passes every pair.
- `$NearestMarker` and `$NearestMarker8` measure distance through every grid cell (GraphDistance seeded with the shape's cells, with 4-step or 8-step edges). Each one keeps the markers at the least distance (ArgExtremes) and takes their one color (Unanimous).
- `deletions`: the 16 deletions that change no pair are all in the clauses for unmarked shapes and in `!shape_cell(S, P)`. No pair has an unmarked shape, and no pair has a background equal to the shape color. The witnesses exercise each of them, so all stay.
- Keywords `objects markers rank`: `rank` is for the nearest-marker extremum and the commonest-color extremum.
- `determination-plan` lists no actions: `background` is covered by DominantColor and `shape_color` by VanishedColor. The sweep finds no value beyond the stored ones.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-413_task_b7256dcd_create.md
