# be94b721

## Concept
- Fits every pair: train0–3 and test0 each have one shape with the most cells (8, 6, 8, 7 and 10 cells, of colors 2, 4, 8, 2 and 3), and cropping that shape's bounding box, with its cells in its color and the rest 0, gives every output (`work/task/be94b721/check_concept.py`, `work/task/be94b721/probe.py pairs`).
- Undefined where two shapes tie for the most cells, or where the input has no shape.
- The rule has a relational form as the generator applies it: 4-connected one-color components (`Components`, keyed by color), their cell counts (`Tally`), the one with the highest count (`ArgExtremes`), and its bounding box (`Bbox`). No approximation is needed.
- No witness has verdict `other`.

## Choice points
- `shape`: what counts as one shape
    - `concept`: a 4-connected group of cells of one color
    - `$Conn8`: replaces `colored-shapes` and `crop-biggest`; shapes are 8-connected groups of one color, so cells of one color that touch only at a corner make one shape; parameter `background`; undefined on a tie for the most cells or with no shape. Fits every pair. Witness `diagonal-link`: breaks `colored-shapes` (the concept reads two shapes of 3 that touch at a corner); stored assignment; plausibility `variant`, verdict `$Conn8` (a person counts a one-color figure joined at a corner as one shape); invariant broken: every shape in the inputs is 4-connected.
    - `$ColorClass`: replaces `colored-shapes` and `crop-biggest`; all the cells of one color make one shape wherever they lie, so the kept color is the commonest non-background color of the input (DominantColor read over the non-`background` cells of one input) and the output is the bounding box of all its cells; parameter `background`; undefined on a tie for the commonest such color or with no non-background cell. Fits every pair. Witness `two-pieces-one-color`: breaks `colored-shapes` (two shapes of color 3); stored assignment; plausibility `borderline`, verdict `concept`; invariant broken: no two shapes in an input share a color.
    - `$AnyColorComponent`: replaces `colored-shapes` and `crop-biggest`; shapes are 4-connected groups of non-background cells of any colors, and the crop keeps each cell's own color; parameter `background`; undefined on a tie for the most cells or with no shape. Fits every pair. Witness `touching-colors`: breaks `colored-shapes` (shapes of 2 and 7 touch); stored assignment; plausibility `borderline`, verdict `concept`; invariant broken: no two shapes in an input touch.
- `size-measure`: what makes a shape the biggest
    - `concept`: its number of cells
    - `$BboxArea`: replaces `one-biggest` and `crop-biggest`; the shape with the largest bounding box area; undefined on a tie. Fails Fit at train1 (the plus of 3 has a 3×3 box, larger than the 3×2 block of 4, so the plus is cropped).
    - `$Height`: replaces `one-biggest` and `crop-biggest`; the tallest shape; undefined on a tie. Fails Fit at train1 (shapes of 3 and 4 are both 3 tall, so the model is undefined).
    - `$Width`: replaces `one-biggest` and `crop-biggest`; the widest shape; undefined on a tie. Fails Fit at train0 (shapes of 2 and 1 are both 3 wide, so the model is undefined).
- `box-content`: what fills the cropped box
    - `concept`: the shape's own cells in its color, every other cell `background`
    - `$BoxRegion`: replaces `crop-biggest`; the output is the input's subgrid over the biggest shape's bounding box, other shapes' cells included; parameter `background` (for finding shapes only); undefined where the concept is. Fits every pair. Witness `cell-in-box`: breaks no scene claim; stored assignment; plausibility `variant`, verdict `concept`; invariant broken: the shapes' bounding boxes are disjoint in every input.
- `background`: where the field color comes from
    - `concept`: stored, 0
    - `background=DominantColor`: replaces the stored `background` with the commonest color of the input (DominantColor under `@derive`, one value per color tied for commonest, one output for each); undefined where the concept is undefined at one of those values. Fits every pair (0 is the commonest color of every input). Witness `background=DominantColor`: breaks no scene claim; stored assignment; plausibility `borderline`, verdict `concept`; invariant broken: 0 is the commonest color of every input, filling most of the grid.
- `shape` & `size-measure`, `shape` & `box-content`, `shape` & `background`, `size-measure` & `box-content`, `size-measure` & `background`, `box-content` & `background`: the two branches' changes applied together

## Open parameters
none

## Not formed
- A rule for a tie for the most cells (`one-biggest` broken): no pair, solver header, proposer or variant task gives a tiebreak, and the concept and every branch are undefined there.
- A stored color for the kept shape: the kept color is 2, 4, 8 and 2 across the train pairs, so no single stored value fits them, and the test color 3 is no train color. Selection by color from the input is `$ColorClass`.
- Fewest cells, or the rarest color (RarestColor): every pair keeps the shape with the most cells, so these contradict all of them.
- A fixed output size (ConstOutDim, ConstOutDimAxis): the output sizes are 4×3, 3×2, 4×3, 3×3 and 4×3, so no constant fits.

## Tickets filed
- none
