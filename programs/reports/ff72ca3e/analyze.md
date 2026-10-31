# ff72ca3e

## Concept
- Fits every pair: train0–3 and test0 (probe `work/task/ff72ca3e/probe.py`). No witness has verdict `other`. The generator applies the rule as written. Each yellow (`center_color` 4) grows a red (`fill_color` 2) square with radius one less than the Chebyshev distance to its nearest gray (`blocker_color` 5), and every yellow keeps its color. This has a relational form: the radius is the least distance to a blocker cell, minus one, and the square is the cells within that Chebyshev distance of the center.
- The pairs never separate whether the grid edge also bounds the square. In train3 and test0 the square meets the edge at exactly the radius the gray gives (scene claim `square-fits`). They never show two centers near each other either (`squares-apart`).

## Choice points
- `edge-limit`
    - `concept`: only `blocker_color` cells bound the square. A square that reaches past the grid is cut off at the edge.
    - `$EdgeBounds`: replaces `square-radius`. The radius is the smaller of the nearest-blocker Chebyshev distance minus one and the center's distance to the nearest grid edge. No new parameter. It is defined everywhere the concept is, and also where a center has no blocker. Fits every pair. Witness `edge-bounds` breaks `square-fits` at the stored assignment. Plausibility `variant`, verdict `concept`. The input invariant it breaks: every square lies wholly inside the grid.
- `blockers`
    - `concept`: only `blocker_color` cells stop a square.
    - `$CentersBlock`: replaces `square-radius`. The other `center_color` cells join the blocker set. No new parameter. It is undefined where a center has neither a blocker nor another center. Fits every pair. Witness `centers-block` breaks `squares-apart` at the stored assignment. Plausibility `variant`, verdict `concept`. The input invariant it breaks: no square holds or meets another center's square.
- `center-cover`
    - `concept`: every `center_color` cell keeps its color, including one that lies inside another center's square.
    - `$CoverCenters`: replaces `paint-square`. Every square cell except that square's own center takes `fill_color`, so a center inside another square is painted over. No new parameter. Its domain is the concept's. Fits every pair. Witness `cover-centers` breaks `squares-apart` at the stored assignment. Plausibility `variant`, verdict `concept`. The input invariant it breaks: no square holds another center.
- `center_color`
    - `concept`: stored, 4.
    - `center_color=RarestColor`: derives the center color as each rarest color of the input. It is undefined where the input has no non-background cell. Fails Fit at train1: 4 and 5 each have one cell, so both are rarest and the gray also grows a square.
- `fill_color`
    - `concept`: stored, 2.
    - `fill_color=OutNewColor`: derives the fill color as a color in every train output and in no input. Under `@derive` it reads no output, so it gives no value on any input and is undefined everywhere. Fails Fit at train0.
- `edge-limit` & `blockers`, `edge-limit` & `center-cover`, `center_color` & `edge-limit`, `center_color` & `blockers`, `center_color` & `center-cover`, `center_color` & `fill_color`, `fill_color` & `edge-limit`, `fill_color` & `blockers`, `fill_color` & `center-cover`: the two branches' changes applied together
- `blockers` & `center-cover`: the model of `$CentersBlock` alone. Under `$CentersBlock`, no square holds another center, so the `center-cover` property exists only with the concept branch of `blockers`, and the point stands at the concept.

## Open parameters
- none

## Not formed
- The square's four sides grow independently until each meets a blocker or the edge: fails Fit at train1. The only gray is on the left, yet the square stops at col 6 on the right as well.
- Only a gray in the center's row or column bounds the square: fails Fit at train0. The center (2,3) is bounded by the gray at (4,1), which shares neither its row nor its column.
- Manhattan or Euclidean distance in place of Chebyshev distance: fails Fit at train0. The Manhattan distance from (2,3) to its nearest gray is 4, which would give radius 3 where the output has radius 1.
- A square that would leave the grid makes the model undefined: no reader of the concept takes leaving the frame as an error. Where this reading differs from the concept, it differs as `$EdgeBounds` does, on inputs that break `square-fits`.
- The order in which overlapping squares are painted: every square paints the one `fill_color`, so no order changes an output.
- A derived `blocker_color`: no proposer that reads one input gives 5 alone. DominantColor gives 0, SharedColor gives 0, 4 and 5, and RarestColor gives 4 or the tie of 4 and 5.
- A derived `background`: the program never reads it, so it is a scene parameter only.

## Tickets filed
- none
