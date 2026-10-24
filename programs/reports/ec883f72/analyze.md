# ec883f72

## Concept
- Fits every pair (train0–3, test0) at `background` = 0. The rule has a relational form: bends of a 1-wide wall and diagonal steps, with no number that counts nothing. No witness has verdict `other`.
- How the generator applies the rule: it puts a solid core in a pocket that a rectangle outline, clipped by the grid edge, closes off one cell from the core. It then casts the core's color diagonally outward from each outer corner of that outline. On every input the generator produces, the concept's "every bend casts" and "paint to the edge" agree with this. They part only on walls that step inward (`stepped-wall`), where the verdict goes to `$ConvexBendsOnly`, not to the concept.
- Probe: `work/task/ec883f72/probe.py` runs every branch's model over the pairs and over the witness inputs in `work/task/ec883f72/witness_inputs.json`.

## Choice points
- `ray-origin`
    - `concept`: each ray leaves a bend of the wall, from the bend's diagonal neighbor that points away from both of its wall neighbors
        - `bend-selection`
            - `concept`: every bend casts
            - `$ConvexBendsOnly`: replaces `corner-rays`. Only a bend whose outward diagonal neighbor lies outside the pocket casts (the pocket is the 4-connected non-wall region holding the core). No parameters. Undefined where the concept is undefined. Fits every pair. Witness `stepped-wall`: breaks `wall-gap` (the bottom arm is 3 rows from the core); stored assignment; `borderline`; verdict `$ConvexBendsOnly`; breaks the invariant that the wall is a rectangle outline clipped by the grid edge, so every bend turns away from the pocket.
    - `$CoreCornerRays`: replaces `corner-rays`. From each corner of the core's box, a ray runs along that corner's outward diagonal. Each cell past the ray's first wall cell becomes the core's color. No parameters. Undefined where the concept is undefined. Fits every pair. Witness `uneven-gap`: breaks `wall-gap` (2 rows to the bottom arm, 1 column to each side arm); stored assignment; `borderline`; verdict `concept`; breaks the invariant that the core is one cell from every arm that faces it.
- `ray-blocking`
    - `concept`: a ray paints every cell to the grid edge, ink included
    - `$RayStopsAtInk`: replaces `corner-rays`. A ray stops before the first non-background cell. No parameters. Same domain as the concept. Fits every pair (no ray meets ink in any pair). Witness `stepped-wall` (the inward ray from (3,3) meets the bottom arm at (5,1)): breaks `wall-gap`; stored assignment; `borderline`; verdict `$ConvexBendsOnly`; breaks the rectangle-outline invariant.
    - `$RayKeepsInk`: replaces `corner-rays`. A ray paints background cells only and carries on past ink. No parameters. Same domain as the concept. Fits every pair. Witness `stepped-wall`: breaks `wall-gap`; stored assignment; `borderline`; verdict `$ConvexBendsOnly`; breaks the rectangle-outline invariant.
- `core-identification`
    - `concept`: the core is the solid-rectangle object and the wall is the other one
    - `$WallByShape`: replaces `core`. The wall is the 1-wide object (no 2×2 block) that has a bend, and the core is the other object, whatever its shape. No parameters. Undefined unless exactly one object is 1-wide with a bend. Fits every pair. Witness `bent-core` (a 2×2 core with one more cell below it): breaks `core`; stored assignment; `variant`; verdict `$WallByShape`; breaks the invariant that every core is a solid rectangle.
    - `$CoreByRarity`: replaces `core`. The core is the color with the fewest cells (RarestColor on one input). Fails Fit at train3: 5 (12 cells) is rarer than 4 (20 cells), so the 5-wall would be taken as the core.
- `ray-color`
    - `concept`: the core's color, derived per input
    - `ray_color=stored`: replaces `corner-rays`. One stored ray color. Fails Fit at train1: train0 needs 3 and train1 needs 6.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest color of the input. Undefined where that color is tied. Fits every pair. Witness `background=DominantColor` (train0 with the field recolored 7): breaks `background`; stored assignment, where the concept is undefined (it finds two non-solid objects); `variant`; verdict `background=DominantColor`; breaks the invariant that the background is 0 in every input.
    - `background=SharedColor`: fails Fit at train0. On that input alone it gives 0, 3 and 9, and at 3 the input has no solid core, so the model is undefined.
- `ray-origin` & `ray-blocking`, `ray-origin` & `core-identification`, `ray-origin` & `ray-color`, `ray-origin` & `background`, `bend-selection` & `ray-blocking`, `bend-selection` & `core-identification`, `bend-selection` & `ray-color`, `bend-selection` & `background`, `ray-blocking` & `core-identification`, `ray-blocking` & `ray-color`, `ray-blocking` & `background`, `core-identification` & `ray-color`, `core-identification` & `background`, `ray-color` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The bend cell itself takes the ray color: every pair keeps the wall color there (train0 output (3,3) is 9).
- Rays from the core's corners that paint every background cell on the diagonal, pocket cells included: train0 output (2,2) stays 0.
- Rays from the free ends of the wall's arms: each free end has one wall neighbor and sits on the grid edge, so no diagonal points away from two neighbors. No pair shows a ray there.

## Tickets filed
- none
