# b10624e5

## Concept
- Fits every pair (train0, train1, test0), as `scripts/check_concept.py` and `scripts/probe.py` show.
- Each rule has a relational form. The block side u in `scale` is the largest divisor of the template core's extent whose aligned tiling leaves the template quadrant constant on each block, which is a count of cells. On each axis, the scale ratio is the lone core's extent over the template core's extent.
- The concept model is undefined where k does not divide a lone core's extent, which breaks `scalable`. Off that tiling, no rounding of a fractional block side is equivariant, so the concept case stays undefined there (see Not formed).
- No witness has the verdict `other`.

## Choice points
- `template-select`: how the template quadrant is found
    - `concept`: the one quadrant that holds a color other than `background` and `core_color` (rule `template`); `template_corner` is a scene parameter
    - `template_corner=stored`: the template quadrant is a stored parameter, `template_corner` = TL, in place of rule `template`. Defined on every input. Fits every pair. Witness `template_corner=stored`: train0 input turned a half turn, so the full figure sits in the bottom-right quadrant. The stored reading takes the bare top-left core as the template and gives the input. Breaks `template-quadrant` (`template_corner` = TL). `variant`, verdict `concept`. Invariant broken: the full figure sits in the top-left quadrant.
    - `TemplateByMostCells`: the template quadrant is the one with the most non-`background` cells, in place of rule `template`. Fails Fit at train1, where the 4×4 bottom-left core (16 cells) outnumbers the template figure (13 cells).
- `turn`: how the figure turns into each lone core's quadrant
    - `concept`: reflection across each divider between the two quadrants (rule `mirror`)
    - `Rotate`: a quarter turn clockwise for each quadrant step clockwise from the template, in place of `mirror`. Undefined where a core is not square. Fails Fit at train0: the top-right figure would carry the azure block to the right of the core, and train0 output has it above the core (rows 3–4, cols 20–21).
    - `Translate`: the figure is copied unturned, in place of `mirror`. Fails Fit at train0: the green block would stand right of the top-right core, and train0 output has it at the left (rows 5–6, cols 18–19).
- `scale-axes`: how the scale ratio is taken
    - `concept`: on each axis, from that axis's extents (rule `scale`)
    - `SquareScale`: one ratio for both axes, in place of `scale`. Undefined where a core is not a square. Fits every pair. Witness `rectangular-core`: train0 input with the bottom-right lone core cut to 3 rows by 2 columns. `SquareScale` is undefined there, and the concept stretches each axis by its own extent. Breaks `lone-cores` (a square). `variant`, verdict `concept`. Invariant broken: every core is a square. `SquareScale` agrees with the concept wherever it is defined, so its model is subsumed by the concept's and fails Subsumption.
- `clip`: what happens to the part of a scaled figure that leaves the lone core's quadrant
    - `concept`: it is dropped at the quadrant edge (rule `paint`)
    - `GridClip`: it is painted over the dividers and into the other quadrants, and dropped only at the grid edge, in place of `paint`. Defined on every input. Fits every pair: the test's clipped blocks stop at the grid edge, which is also the quadrant edge there. Witness `figure-crosses-divider`: train0 input with the top-right core moved to rows 5–6, cols 14–15. Its mirrored green block falls on cols 12–13. The concept drops that block, and `GridClip` paints it over the divider and into the template quadrant. Breaks no scene claim. `ordinary`, verdict `concept`.
- `core-color`: how the core color is known
    - `concept`: the stored parameter `core_color` = 2
    - `CoreByQuadrants`: the core color is derived as the one non-`background` color that every quadrant holds, in place of the stored `core_color`. Nothing paints where that color is not unique. Fits every pair. Witness `other-core-color`: train0 input with every red (2) cell made magenta (6). The stored core color finds no core and gives the input, and `CoreByQuadrants` grows the figure. Breaks `lone-cores` and `template-quadrant` (`core_color` = 2). `variant`, verdict `CoreByQuadrants`. Invariant broken: every core is red.
    - `core_color=SharedColor`: on one input, every color of that input. Fails Fit at train0: each quadrant then holds a non-core color, so no unique template is found.
    - `core_color=RarestColor`: green and azure on train0. Fails Fit at train0: red then counts as a non-core color in every quadrant.
    - `core_color=DominantColor`: yellow (4), the background. Fails Fit at train0.
- `background`: how the background is known
    - `concept`: the stored parameter `background` = 4
    - `background=DominantColor`: the commonest color of the input. Fits every pair. Witness `background=DominantColor`: train0 input with each lone core grown to 11×11, so red outnumbers yellow. The derivation reads red as the background, finds no single template quadrant and gives the input, and the concept grows the figure at each core. Breaks no scene claim. `borderline`, verdict `concept`. Invariants broken: yellow is the commonest color of each input, and no lone core is more than 4 cells on a side.
    - `background=SharedColor`: every color of the input. Fails Fit at train0: no cell then counts as figure.
- `divider-color`: how the cross is found
    - `concept`: the stored parameter `divider_color` = 1
    - `divider_color=SharedColor`: every color of the input. Only one color can hold both a full row and a full column, so the cross is the full row and column of whatever color forms them. Fits every pair. Witness `divider_color=SharedColor`: train0 input with the cross made orange (7). The stored color finds no cross and gives the input, and the derivation grows the figure. Breaks `cross` (`divider_color` = 1). `variant`, verdict `divider_color=SharedColor`. Invariant broken: the cross is blue.
    - `divider_color=DominantColor`, `divider_color=RarestColor`: yellow, and green with azure, on train0. Neither forms a full row and column, so no cross is found. Each fails Fit at train0.
- `figure-extent`: what the template carries
    - `concept`: every non-`background` cell of the template quadrant (rules `mirror`, `paint`)
    - `FigureOnly`: only the 8-connected piece of non-`background` cells that holds the template core, in place of `mirror`'s whole quadrant. Defined on every input. Fits every pair. Witness `detached-block`: train0 input with a maroon 2×2 block at rows 2–3, cols 1–2, away from the figure. The concept carries that block to each lone core, and `FigureOnly` leaves it out. Breaks `template-quadrant` (blocks attached around the core). `borderline`, verdict `concept`. Invariant broken: every template block touches the rest of the figure.
        - `adjacency`: which cells join the figure's piece
            - `concept`: 8-adjacency
            - `Adjacency4`: 4-adjacency. Fits every pair: the test's diagonal azure block also touches the green and maroon blocks along a side. Witness `corner-touching-block`: train0 input with a maroon 2×2 block at rows 2–3, cols 3–4, which touches the azure block only at a corner. `FigureOnly` with 8-adjacency carries the block, and `FigureOnly & Adjacency4` leaves it out. Breaks `template-quadrant`. `borderline`, verdict `concept`. Invariant broken: every template block shares a side with the rest of the figure.
- `template-select` & `turn`, `template-select` & `scale-axes`, `template-select` & `clip`, `template-select` & `core-color`, `template-select` & `background`, `template-select` & `divider-color`, `template-select` & `figure-extent`, `turn` & `scale-axes`, `turn` & `clip`, `turn` & `core-color`, `turn` & `background`, `turn` & `divider-color`, `turn` & `figure-extent`, `scale-axes` & `clip`, `scale-axes` & `core-color`, `scale-axes` & `background`, `scale-axes` & `divider-color`, `scale-axes` & `figure-extent`, `clip` & `core-color`, `clip` & `background`, `clip` & `divider-color`, `clip` & `figure-extent`, `core-color` & `background`, `core-color` & `divider-color`, `core-color` & `figure-extent`, `background` & `divider-color`, `background` & `figure-extent`, `divider-color` & `figure-extent`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Resampling a fractional block side off the `scalable` tiling (sample from the core's near edge, from its far edge, or at cell centers): a reflection of the task changes which cells round which way, so none of these readings gives an equivariant model.
- A template at a different scale on each lone core's two axes, from a non-square template core: the template core is square in every input, and per-axis scaling (the concept) already reads each axis's extents separately. No reading differs from the concept here.
- The cross found away from the grid center: the concept finds the cross by its full row and column of `divider_color` wherever they lie, and no reading reads its position.

## Tickets filed
- none
