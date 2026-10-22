# b2bc3ffd

## Concept
- Fits every pair (checked by `probe.py`). It has no witness with verdict `other`. Each of its rules has a relational form: the jump distance is the object's cell count, which counts cells the task has.
- On every input where the concept is defined, the concept reads `jump` with the cells moved past the far edge lost (see `overflow`). Where two moved objects of different colors land on one cell, or a moved object lands on a floor cell, the concept is undefined (see `collision`).

## Choice points
- `object`: what an object is
    - `concept`: a connected component of ink cells, as `component-color` and `adjacency` read it
    - `$ColorClass`: replaces `objects`: all cells of one color form one object, wherever they lie; no parameters added; defined wherever the concept is. Fits every pair. Witness `same-color-pieces`: breaks `objects` (two objects of one color); plausibility `variant`; verdict `concept`; invariant broken: each color forms one object.
- `component-color`: which ink cells join one component
    - `concept`: only cells of one color
    - `$MultiColor`: replaces `objects`: 4-connected components of all ink cells, of any colors, and an object jumps by its whole cell count; no parameters added; defined wherever the concept is. Fits every pair. Witness `touching-colors`: breaks no scene claim; plausibility `variant`; verdict `concept`; invariant broken: a background column separates any two objects.
- `adjacency`: which cells count as touching
    - `concept`: 4-adjacency
    - `$Adj8`: replaces `objects`: 8-connected components; no parameters added; defined wherever the concept is. Fits every pair. Witness `diagonal-contact`: breaks `objects` (two objects of one color at 4-adjacency); plausibility `borderline`; verdict `$Adj8`; invariant broken: each color forms one 4-connected object.
- `floating`: how an object that does not touch the line next to the floor moves
    - `concept`: it jumps by its cell count from where it is
    - `$FromFloor`: replaces `jump` for such an object: it lands with its lowest cell its cell count above the line next to the floor; no parameters added; defined wherever the concept is. Fits every pair. Witness `floating-object`: breaks `grounded`; plausibility `borderline`; verdict `concept`; invariant broken: every object touches the line next to the floor.
    - `$GroundedOnly`: replaces `jump` for such an object: it stays; no parameters added; defined wherever the concept is. Fits every pair. Witness `floating-object`: breaks `grounded`; plausibility `borderline`; verdict `concept`; invariant broken: every object touches the line next to the floor.
- `overflow`: what happens to cells that a jump takes past the far edge
    - `concept`: they are lost
    - `$Clamp`: replaces `jump` for such an object: it moves only until it reaches the far edge; no parameters added; defined wherever the concept is. Fits every pair. Witness `overflow`: breaks `fits`; plausibility `borderline`; verdict `any`; invariant broken: every object's cell count is at most the number of lines between it and the far edge.
    - `$OverflowUndefined`: replaces `jump` for such an object: the model gives no output; no parameters added; undefined on every input where an object would leave the frame. Fits every pair. Witness `overflow`: breaks `fits`; plausibility `borderline`; verdict `any`. The concept's model subsumes it: it fails Subsumption.
- `collision`: which color a cell takes when two moved objects land on it
    - `concept`: none; the model is undefined there
    - `$LargerOnTop`: adds a rule: the object with more cells paints over the other; no parameters added; defined wherever the concept is, and on such inputs. Fits every pair. Witness `collision`: breaks no scene claim; plausibility `borderline`; verdict `any`; invariant broken: a background column separates any two objects, and no object stands over another.
    - `$SmallerOnTop`: adds a rule: the object with fewer cells paints over the other; no parameters added; defined wherever the concept is, and on such inputs. Fits every pair. Witness `collision`: breaks no scene claim; plausibility `borderline`; verdict `any`; invariant broken: as for `$LargerOnTop`.
- `floor-source`: where `floor_side` and `floor_color` come from
    - `concept`: both stored
    - `$FloorDerived`: replaces `floor`: the floor is the one edge line that is all one color other than `background`; `floor_side` and `floor_color` are derived from it, and the heading is away from that side; undefined where no edge line, or more than one, is like that. Fits every pair. Witness `rotated-floor` (the test input turned a quarter turn clockwise): breaks `floor`; plausibility `variant`; verdict `$FloorDerived`; invariant broken: the floor lies along the bottom edge in color 8.
- `floor-extent`: which cells are floor, which stay and are not ink
    - `concept`: every cell of `floor_color`
    - `$FloorLineOnly`: replaces `floor` and `objects`: only the floor line is floor; cells of `floor_color` elsewhere are ink; no parameters added; defined wherever the concept is. Fits every pair. Witness `floor-colored-object`: breaks no scene claim; plausibility `borderline`; verdict `concept`; invariant broken: `floor_color` appears only in the floor line.
    - `$FloorMoves`: replaces `keep-floor` and `objects`: no cell is floor, so the floor line is ink like any other; `floor_color` is no longer read; defined wherever the concept is. Fails Fit at train0: the floor line, an object that does not touch the line next to the floor, jumps 8 lines and leaves the frame, and train0's output keeps it.
- `background`: where `background` comes from
    - `concept`: stored, 7
    - `background=DominantColor`: replaces `background`: the value is the commonest color of the input, by `DominantColor` with the `@derive` directive; undefined where two colors tie for commonest. Fits every pair (7 is the commonest color of every input). Witness `background=DominantColor` (the test input with 7 recolored 4): breaks `fits` (at `background` 7, the 4 field is one object of 49 cells); plausibility `variant`; verdict `background=DominantColor`; invariant broken: the background is 7.
- `object` & `component-color`: `$ColorClass` & `$MultiColor` is `$ColorClass` alone. `component-color` does not exist with `$ColorClass`, and stands under the concept branch of `object`.
- `object` & `adjacency`: `$ColorClass` & `$Adj8` is `$ColorClass` alone. `adjacency` does not exist with `$ColorClass`, and stands under the concept branch of `object`.
- Every other pair of points, `component-color` & `adjacency` included: the two branches' changes applied together.
    - `$FloorMoves` & `$GroundedOnly`: the floor line does not touch the line next to the floor, so it stays. This case fits every pair, and differs from `$GroundedOnly` on `floor-colored-object`: there the floor-colored object joins the floor line, the joined object touches the line next to the floor, and it jumps 10 lines out of the frame, which leaves no floor.

## Open parameters
none

## Not formed
- The jump distance as another measure of the object (height, width, box area, perimeter): train0's 9 object has height 2, width 3, and box area 6, and it jumps 4, which is its cell count.
- A heading stored apart from `floor_side`: the heading is away from the floor in every variant task, so it is derived data (Redundant value).
- Vacated cells keep a trace: every pair's output clears the cells an object left.
- Cells past the far edge wrap to the floor side: the wrapped cells would land in or under the floor line, which `keep-floor` keeps, and no reading of a jump gives that.
- `background` by `SharedColor` or `RarestColor`: on a single input, `SharedColor` gives every color of that input, and `RarestColor` gives an object color, so each fails Fit at train0.
- `floor_color` by a proposer: `UnchangedColor`, `ChangedColor` and `ChangedPairs` read `ex_out`, which is empty in a run on one input, so they derive nothing. `SharedColor` gives several values, and `DominantColor` and `RarestColor` give 7 or an object color. Each fails Fit at train0.

## Tickets filed
none
