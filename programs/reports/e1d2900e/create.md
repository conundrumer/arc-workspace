# e1d2900e

## Departures
- The concept's `slide-to-touch` now packs the dots that slide to one side of a square along one line against that square, nearest first. `$PathStack` is gone, and `$PathBlocked`'s `dot-on-path` verdict is now `concept`: analyze.md gives `dot-on-path` the verdict `$PathStack` at `ordinary` plausibility on the `$PathStack` branch, with no `@reassigned` line. Witness says to fix the concept case to give that judged output. After the fix, `$PathStack` is equivalent to the concept and fails Equivalence. The old passing-through concept (both dots on one cell) is no longer a case.
- `witness --file programs/reports/e1d2900e/witnesses.json` shows the concept group of `dot-on-path` differing from the solver: (4,0) now lands on (4,3). This follows from the departure above.
- `$PathStack` was removed from every group and `separates` text in the witness file, and `record --all` rewrote the groups.
- The concept constructors have names of my own: `Nearest`, `Pack`, `ByColor`, `AnyBlock`.

## Judgments
- `derive` reports `square_size=TileCount` and `square_size=TileDim`, which analyze.md does not have. I hold them as `@derive` branches under `$SquareSizeChecked`, each `borderline concept` with `@relaxed squares`, because their witnesses need a block that is not 2 by 2.
- Witness `tile-dim` (9 by 9 grid, a 2 by 2 square and a 3 by 3 block) separates `square_size=TileDim` from `square_size=TileCount`, and `$SquareSizeChecked & square_size=TileDim` from `$AnyBlock`. My judgment: `borderline concept`, because it breaks `squares`.
- Witness `tile-count` (9 by 9 grid, a 2 by 2 square and a 4 by 4 block) separates `$SquareSizeChecked & square_size=TileCount` from `$AnyBlock`. My judgment: `borderline concept`, for the same reason.
- `store` printed no line to add. No `@store` branch.
- Determine:
    - `background_color`: the color that is commonest in every input (Mode).
    - `square_color`: a non-background color with no lone cell in any input.
    - `dot_color`: a lone output cell of a non-background color that touches a cell of another non-background color. This is a fact of the outputs alone. Before this change, the plan reported that `extra-color-dot` gave a second dot color.
    - `square_size`: the one extent shared by every square-color component box on both axes.
    - The last plan reported no actions.
- `Bbox<Ident>` in Determine is keyed by component ids. Those ids come from positions, so two components of different examples that share their least cell share one box. On these inputs this changes nothing.
- `lint` hints:
    - Case-marker hints came from one `Components<Roles>` shared by both Roles branches. I split it into `color_piece` and `ink_piece`, one per branch.
    - The `square_color` hint said its test read inputs and outputs together. I rewrote it from inputs alone.
    - I resolved the common-subexpression and negated-use findings in Determine with `out_next`.
- `deletions`: 33 deletions change nothing on the pairs. They are the tie, path-blocked, size-check and stacking structures, which the pairs do not instantiate and the witnesses show, together with Determine guards that only the witness inputs exercise. I kept all of them.
- Comparisons and keys:
    - Choosing the nearest slide uses `ArgExtremes` keyed by `Probe = [c: Cast, dot: Position]`.
    - `$PathBlocked` uses its own `near_clear` instance, so that the instance the other cases share is keyed only by the fields it varies with.
- `$TieEither` uses `TiebreakResolutions<Choice, Position, Pick>`. Each item is `[dot, dir]`, so that two tied dots can both take the same direction. A case with no open tie has the one resolution `$End()`.
- Keywords: `objects move rank`.

## Unsettled
- The audit's relabeling check timed out after 20 s, twice. A longer relabeling run would settle it.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/e1d2900e/analyze.md`, the `dot-on-path` line under Concept and the `$PathStack` line: the verdict `$PathStack` at `ordinary` makes stacking the concept's rule. The concept file's `slide-to-touch` should state the packing, and `$PathBlocked`'s verdict should be `concept`.

## Tickets filed
- none
