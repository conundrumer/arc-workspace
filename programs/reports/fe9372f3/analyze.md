# fe9372f3

## Concept
- Fits every pair (train0, train1, test0), as `work/task/fe9372f3/check_concept.py` and `work/task/fe9372f3/probe.py` show. No witness has verdict `other`. Each rule has a relational form: the dash colour is the stride index along a ray, counted from the arm tip, mod the pattern length. The single 5-cell plus means the arm length (1), the center and the tips are all fixed in every input. So the branches below part from the concept only on a longer-armed plus, a stray cell, a recoloured plus, or a grid the plus outnumbers.

## Choice points
- `dash-phase` (where the dash pattern's count starts)
    - `concept`: one step past each arm tip, `dash_pattern[(k - 1) mod 3]` at k steps past the tip
    - `$PhaseFromCenter`: replaces `dashed-cardinal-rays`. The cell at distance d from the center takes `dash_pattern[(d - 2) mod 3]`. Parameters unchanged, and it is undefined nowhere the concept is defined. Fits every pair. Witness `long-arms` (a plus with arms two cells long) breaks `one-plus` at `arm_length` 1. Plausibility `variant`, verdict `concept`. Invariant broken: every plus has arms one cell long.
    - `$PhaseFromEdge`: replaces `dashed-cardinal-rays`. The phase is anchored at the far grid edge, whose cell takes the pattern's last colour. Fails train0 (train0 output row 4, cols 6–9 are `8 8 4 8`, and the edge cell is 8). It also fails train1 and test0.
- `dash-period` (what fixes the dash period)
    - `concept`: the stored cyclic `dash_pattern` 8 8 4
    - `$PeriodFromSpan`: replaces `dashed-cardinal-rays` and `dash_pattern` with `dash_color` 8 and `accent_color` 4. The period is derived as the plus's span `2·arm_length + 1`: span − 1 cells of `dash_color`, then one of `accent_color`. Defined wherever the concept is. Fits every pair. Witness `long-arms`: with span 5 the dashes run `8 8 8 8 4`. Breaks `one-plus` at `arm_length` 1. Plausibility `variant`, verdict `concept`. Invariant broken: every plus has arms one cell long.
- `diagonal-origin`
    - `concept`: each diagonal ray starts one diagonal step from the center
    - `$DiagFromCorner`: replaces `diagonal-rays`. Each diagonal ray starts at the plus's bounding-box corner, `arm_length` steps out, and leaves the nearer diagonal cells as they are. Defined wherever the concept is. Fits every pair. Witness `long-arms`: cells (3,4), (3,6), (5,4), (5,6) stay 0. Breaks `one-plus` at `arm_length` 1. Plausibility `variant`, verdict `concept`. Invariant broken: every plus has arms one cell long.
- `ray-stop`
    - `concept`: every ray runs to the grid edge and paints over whatever it crosses
    - `$HaltAtObstacle`: replaces the extent in `diagonal-rays` and `dashed-cardinal-rays`. Each ray stops before the first input cell that is not `background`. Defined wherever the concept is. Fits every pair. Witness `halt-at-obstacle`: the test input with a stray 3 at (11,13) on the right ray. The concept paints (11,13) 8 and runs on to the edge. The branch keeps the 3 and leaves cols 14–16 at 0. Breaks `one-plus` (every other cell `background`). Plausibility `borderline`, verdict `any`. Invariant broken: no cell outside the plus is non-background.
- `plus-locator`
    - `concept`: the plus is the non-`background` cells: the center has four non-`background` neighbours, and each tip ends the non-`background` run out of the center
    - `$PlusByColor`: replaces the plus finding in `diagonal-rays` and `dashed-cardinal-rays`. The plus is found by the stored `plus_color` 2, which becomes a parameter. The branch is defined everywhere and returns the input where no plus of that colour exists. Fits every pair. Witness `recolored-plus`: the test plus in 3. The concept shoots the rays, and the branch returns the input. Breaks `one-plus` at `plus_color` 2. Plausibility `variant`, verdict `concept`.
- `background`
    - `concept`: `background` stored, 0
    - `background=DominantColor`: `background` is derived as each colour with the highest cell count of the one input. It is undefined where that gives nothing (never). Fits every pair. Witness `background=DominantColor`: the plus filling a 3×3 grid, so 2 outnumbers 0. The concept paints the four corners 1. The branch takes 2 as background, finds no plus, and returns the input. Breaks no scene claim. Plausibility `borderline`, verdict `concept`. Invariant broken: every grid is at least 7×10, and the field outnumbers the plus.
    - `background=RarestColor`: `background` is derived as the rarest colour of the input, which is 2. The program then finds plus centers all over the 0 field, and their rays conflict. Fails train0 (and train1, test0).
    - `background=SharedColor`: `background` is derived as every colour of the input, {0, 2}. No cell is non-background, so the output is the input. Fails train0 (and train1, test0).
- `dash-phase` & `dash-period`, `dash-phase` & `diagonal-origin`, `dash-phase` & `ray-stop`, `dash-phase` & `plus-locator`, `dash-phase` & `background`, `dash-period` & `diagonal-origin`, `dash-period` & `ray-stop`, `dash-period` & `plus-locator`, `dash-period` & `background`, `diagonal-origin` & `ray-stop`, `diagonal-origin` & `plus-locator`, `diagonal-origin` & `background`, `ray-stop` & `plus-locator`, `ray-stop` & `background`: the two branches' changes applied together
- `plus-locator` & `background`: under `$PlusByColor` the program reads `background` only to stop rays under `$HaltAtObstacle`. So a case that takes `$PlusByColor` and a derived background, and the concept branch at `ray-stop`, has `$PlusByColor`'s model alone. `background`'s property exists with the concept locator, and with `$PlusByColor` only together with `$HaltAtObstacle`. It stands at the concept.
    - `$PlusByColor` & `background=DominantColor`: `$PlusByColor`'s model (with `$HaltAtObstacle` as well: `$PlusByColor & $HaltAtObstacle` with the derived background as the stopping colour)

## Open parameters
- none

## Not formed
- Dash pattern as `dash_color`, `accent_color` and a stored period: this only reparameterizes the stored `dash_pattern`. At each of its assignments it agrees on every input with the concept at the pattern it spells, so it adds no rule. `$PeriodFromSpan` carries the split form where it changes the model.
- A dash pattern or diagonal colour per direction (payload keyed by direction): every pair gives one pattern for all four cardinal rays and one colour for all four diagonals, and the plus is D4-symmetric. By the Orientation "Every value" item (0ca9ddb6), each orientation type gets one payload.
- A stored subset of directions (reassigned set): the plus is D4-symmetric, so no variant task can pick out a subset of its directions. All eight are used in every pair.
- Deriving `diag_color` or a `dash_pattern` colour by a proposer: 1, 4 and 8 occur in no input. Every proposer that gives a colour missing from the input reads `ex_out` (OutNewColor, AnyOutNewColor), and `ex_out` is empty under a `@derive` branch. The ones that read only the input (SharedColor, DominantColor, RarestColor, UnchangedColor) give 0 or 2, and those fail every pair.
- The whole ray picture as a stored stamp anchored at the center (GRID_STAMP): test0's down ray reaches 18 cells past the center, and no train pair shows more than 7. The stamp has no entry there and fails test0 (row 19, col 7 is 8 in the output). This is the unseen-key case of Fit, a lookup failure rather than a new claim.
- Dashed diagonals, plain cardinal rays, or rays that start before the tip: every pair contradicts them.

## Tickets filed
- none
