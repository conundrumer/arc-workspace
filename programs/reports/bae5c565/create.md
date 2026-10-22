# bae5c565

## Departures
- The witness file holds a witness `stalk-recolored` that the Analyze file lacks, with a `@witness stalk-recolored: variant concept` line and `@relaxed stalk` under `$StalkByColor`: `witness` reported that no run showed `$NonBackground` defined and differing from `$StalkByColor` in the pair of cases that take `$StalkTakesPaletteColor`. The input is train1 with the stalk in 2. `$StalkByColor` finds no cell of color 8 and is undefined, and the concept builds the mountain around the 2 stalk. Plausibility `variant`: a color swap gives that input, and it breaks the color 8 of the `stalk` claim. Verdict `concept`: the stalk is the one line off the palette row, whatever its color.
- `parse.ink` carries `@ignore: store`: `store` asked to make its constant color 8 a parameter. A stalk found by a stored color is the `$StalkByColor` branch, so that stored reading is equivalent to `$StalkByColor` and fails Equivalence.
- The concept branches have constructors with names of my own: `$StoredSide`, `$NonBackground`, `$ToFarEdge`, `$FromStalk`, `$KeepStalkColor`.

## Judgments
- The concept is undefined where the stalk is not one unbroken run along one column. `stalk_end` is a `Unanimous` instance over the stalk cells whose neighbor toward the palette is not a stalk cell. Each `out` fact of the rest needs an apex, so with no stalk end, the case gives no total grid. That gives the undefined outputs that the Analyze file gives the concept on `background=DominantColor`, `palette-on-left` and `stray-cell`.
- The slope through the apex has a relational form for `stepped-fill`'s "d rows past the stalk's end at distance d": the cells on the two diagonals through the apex, on the side away from the palette. Each column fills from its slope cell to the far edge. No arithmetic is needed.
- `$HeightFromStalkLength` uses a `Gravity` instance to set the stalk down on the edge opposite the palette. The apex is the stalk's top after that drop. This states "L - d cells from the edge" without a count.
- `$DistanceFromCenter` puts the apex at the center column of the base's row. On an even width no cell is centered, so the case has no apex and is undefined.
- `edge_ink.domain` was removed: `deletions` showed that it changed nothing. An edge with no ink never has the most ink unless every edge has none, and the case is undefined both ways.
- The other changeless deletions stay: the pairs never use the structure they guard. These are the `$FillToStalkEnd` cut, the apex atom that makes a case undefined with no stalk, the `side` atoms that fix the direction, and the disjunct for a non-background palette cell above the stalk.
- The enumerators were renamed to the names the lint gave (`palette_side_choice`, `stalk_find_choice`, `column_extent_choice`, `stalk_paint_choice`).
- The common-subexpr hints on `stalk_column` and `fill` were resolved by the relation `same_column`. `column_color`, `stalk_column` and `fill` read it.
- Determination: `background` is the color of the output's palette row, and `stalk_color` is the color of `parse.ink` on the inputs. `Parse` is shared with the program. `palette_side` has no determination relation: the plan gives it as covered by enumeration over the four directions, with no proposer that reads another fact.
- Not formed: a step other than one row per column, a palette row that stays, and mirrored palette colors all fail Fit. A separate stored edge for the mountain is a redundant value, so it is derived data. Every reading of `stalk-reach` gives the concept's output. So Develop step 3 adds no branch.
- `derive` lists only `DominantColor` for `background`, and it is the `@derive` line. `store` prints no `@store` line to add.
- The header leaves out `square-grid` and `stalk-reach`: no `@claim` or `@relaxed` denotes them, and no rule text depends on them.
- Keywords: `lines markers cast`. Each palette color is cast down its column, the stalk marks the apex, and the model works column by column.
- Nine cases are witnessed: the concept, the six non-concept branches, `background=DominantColor`, and `$StalkByColor & $StalkTakesPaletteColor`. That last case is witnessed by its own output on `background=DominantColor`.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-565_task_bae5c565_create.md
