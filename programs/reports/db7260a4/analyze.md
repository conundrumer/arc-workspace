# db7260a4

## Concept
- The concept fits every train pair and the test pair. No witness has the verdict `other`. The `fill` rule as `concept.md` states it is the generator's rule, and it has a relational form.
- The concept's `spread` stops at any wall cell on its line. A wall cell that stands on a cup's floor therefore stops it, and only the pocket beside that cell fills (witness `floor-bump`, which `$FillBasinFlood` gets).

## Choice points
- `fill-height`
    - `concept`: a held cup fills from its floor up to the end of the shorter of its two walls
    - `$FillToTallerRim`: replaces `fill`. A held cup fills up to the end of the taller wall. No parameters of its own, and defined wherever the concept is. Fits every pair. Witness `unequal-walls`: the cup's right wall ends one row lower than its left wall. It breaks no scene claim, and it stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant that the two walls of every cup end on one line.
- `fill-region`
    - `concept`: a held cup fills the cells between the two wall cells that the `spread` meets on its line
    - `$FillBasinFlood`: replaces `fill`. A held cup fills every non-wall cell that a 4-walk from the landing cell reaches, at the highest level line at which that set touches neither the side edges nor the bottom edge. No parameters of its own, and defined wherever the concept is. Fits every pair. Witness `floor-bump`: a wall cell stands on the cup's floor at (5,4). It breaks `cups`, and it stands at the stored assignment. Plausibility `borderline`, verdict `$FillBasinFlood`. It breaks the invariant that the inside of every cup is a plain rectangle of background.
    - `$FillComponentBox`: replaces `fill`. A held cup fills every non-wall cell in the bounding box of the 4-connected wall component under the landing cell. No parameters of its own. Fails Fit at train3: there the component's box spans cols 4–7, so (3–5, 4) fill as well as col 6.
- `leak`
    - `concept`: water that reaches a hole runs out through it and falls on from the hole's cell, and the cup stays empty
    - `$LeakSpills`: replaces `spread`. A cup with a hole sends the water straight to the `pool`, whatever lies under the hole. No parameters of its own. Fails Fit at test0: there the expected output fills the lower cup under the top cup's hole.
    - `$LeakKeepsWater`: replaces `spread`. A hole in the floor does not stop the cup from filling. No parameters of its own. Fails Fit at train2: there the leaky cup stays empty and the bottom row fills.
- `pool`
    - `concept`: every non-wall cell of the edge line toward `fall` takes `water`
    - `$PoolSpreadsToWalls`: replaces `pool`. The water spreads along the edge line from the cell where it lands, in both directions, until it meets a wall cell. No parameters of its own, and defined wherever the concept is. Fits every pair. Witness `wall-on-edge-row`: a lone wall reaches the bottom row at col 5, and the water lands at col 8. It breaks no scene claim, and it stands at the stored assignment. Plausibility `variant`, verdict `$PoolSpreadsToWalls`. It breaks the invariant that no wall cell lies on the bottom row.
- `trail`
    - `concept`: the cells the water only falls through stay as they are
    - `$DrawTrail`: replaces `erase-drop`. Every cell the water falls through takes `water`. Fails Fit at train0: rows 1–2 of col 4 stay 0 there.
- `drop-cell`
    - `concept`: the drop cell becomes `background`
    - `$KeepDrop`: replaces `erase-drop`. The drop keeps its cell. Fails Fit at train0: (0,4) is 0 in the output.
- `water`
    - `concept`: stored, 1
    - `water=RarestColor`: replaces the stored `water` in `drop`. Water is the color with the fewest cells in the input. Undefined on an input where two colors tie for the fewest cells. Fits every pair. Witness `water=RarestColor`: train0 input with the drop recolored 3. It breaks `drop`, and it stands at the stored assignment. Plausibility `variant`, verdict `water=RarestColor`. It breaks the invariant that the drop is color 1.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: replaces the stored `background` in `drop` and `erase-drop`. Background is the color with the most cells in the input. Undefined on an input where two colors tie for the most cells. Fits every pair. Witness `background=DominantColor`: train0 input with background 4. It breaks `drop`, and it stands at the stored assignment. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that the background is 0.
- `fall`
    - `concept`: stored, down
    - `$FallFromDropEdge`: replaces the stored `fall` in `drop` and `fall`. The water falls away from the grid edge that the drop lies on. Undefined on an input where the drop lies on a corner or on no edge. Fits every pair. Witness `drop-on-side-edge`: train0 input turned a quarter turn clockwise. It breaks `drop` and `cups`, and it stands at the stored assignment. Plausibility `variant`, verdict `$FallFromDropEdge`. It breaks the invariant that the drop lies on the top row.
- `fill-height` & `fill-region`, `fill-height` & `leak`, `fill-height` & `pool`, `fill-height` & `trail`, `fill-height` & `drop-cell`, `fill-height` & `water`, `fill-height` & `background`, `fill-height` & `fall`, `fill-region` & `leak`, `fill-region` & `pool`, `fill-region` & `trail`, `fill-region` & `drop-cell`, `fill-region` & `water`, `fill-region` & `background`, `fill-region` & `fall`, `leak` & `pool`, `leak` & `trail`, `leak` & `drop-cell`, `leak` & `water`, `leak` & `background`, `leak` & `fall`, `pool` & `trail`, `pool` & `drop-cell`, `pool` & `water`, `pool` & `background`, `pool` & `fall`, `trail` & `drop-cell`, `trail` & `water`, `trail` & `background`, `trail` & `fall`, `drop-cell` & `water`, `drop-cell` & `background`, `drop-cell` & `fall`, `water` & `background`, `water` & `fall`, `background` & `fall`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A derived `wall`: no input-only proposer gives 2. `DominantColor` gives 0, `RarestColor` gives 1, and `SharedColor` gives 0, 1 and 2 on every input.
- `water=SharedColor` and `background=SharedColor`: on every input, `SharedColor` gives every color of that input, 0, 1 and 2, so no derivation of it gives one value.
- The derivations that read `ex_out` (`OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs`, `VanishedNewPairs`): with `ex_out` empty, they give no value on a lone input, so a case that takes one is undefined on every pair.
- A water amount fixed by the drop's cell count, as in the `settle` rule of 28a6681f: in train0, a one-cell drop fills six cells.
- A reading for water that lands on the top of a wall: the scene claim `no-landing-on-rim` excludes such an input, and no source gives a reading other than the concept's `spread`, which runs both ways from the landing cell.

## Tickets filed
- none
