# df9fd884

## Concept
- The concept case fits every pair: `work/task/df9fd884/probe.py` reproduces train0, train1, train2 and test0.
- Every rule has a relational form: the cups and the object are components of colors, the mouth is a cup's span less its legs, and the move is a shift to a mouth's span and a slide to an edge. The rule needs no approximation.
- No witness has the verdict `other`.
- The concept is undefined at `object-narrower-than-mouth`, `background=DominantColor`, `two-objects` and `cups-of-another-color`, and at `blocked-exit-path` it gives an output that the verdict does not take.

## Choice points
- `object-shape`
    - `concept`: the object lands with its shape unchanged (`exit-other-cup`).
    - `$FlipShape`: replaces `exit-other-cup`; the object lands reflected along the axis of the mouths (top to bottom here); no parameters; undefined nowhere the concept is defined. It fits every pair, since every object in the evidence is symmetric top to bottom. Witness `flipped-shape`: train2 with the object `8 8 / 8 . / 8 .`; breaks no scene claim; `ordinary`, verdict `concept`.
- `slide-stop`
    - `concept`: the object slides until it touches the grid edge (`slide-to-edge`).
    - `$StopAtObstacle`: replaces `slide-to-edge` and drops `clear-path`; the object slides until the next step would leave the grid or meet a cell other than `background`; no parameters; undefined nowhere the concept is defined. It fits every pair. Witness `blocked-exit-path`: a 9×6 grid whose top-left cup spans cols 0–3 and whose bottom-right cup spans cols 2–5, with the object in line with the bottom cup's mouth; breaks `clear-path`; `borderline`, verdict `$StopAtObstacle`; it breaks the invariant that the two cups take column ranges with at least one column between them.
- `slide-direction`
    - `concept`: the object slides in the direction the exit cup's mouth faces (`slide-to-edge`).
    - `$StoredDirection`: replaces `slide-to-edge`; the object slides in a stored direction; parameter `fall_dir`: `DIR_B`; undefined nowhere the concept is defined. It fits every pair. Witness `mouths-flipped`: train0 flipped top to bottom, so the object lines up with the top cup and exits from the bottom one; breaks no scene claim; `variant`, verdict `concept`; it breaks the invariant that the entry cup is the bottom cup, with the object above it.
- `cross-placement`
    - `concept`: the entry cup is the cup whose mouth spans the same columns as the object, and the object moves to span the exit cup's mouth (`object-at-mouth`, `exit-other-cup`).
    - `$KeepOffsetInMouth`: replaces `object-at-mouth` and `exit-other-cup`; the entry cup is the cup whose mouth contains the object's span, and the object moves by the shift that takes the entry mouth onto the exit mouth; no parameters; undefined where no mouth or two mouths contain the object's span. It fits every pair. Witness `object-narrower-than-mouth`: train0 with the object cut to the bar (4,6), (5,6); breaks `object-at-mouth`; `borderline`, verdict `$KeepOffsetInMouth`; it breaks the invariant that the object is exactly as wide as the mouths.
    - `$MirrorAcross`: replaces `exit-other-cup`; the object's column span is mirrored across the grid's vertical center line; no parameters. It fails Fit at test0: it places the object at col 5, and the output has it at col 6.
- `original-cells`
    - `concept`: the object's input cells take `background` (`remove-object`).
    - `$KeepOriginal`: replaces `remove-object`; the object stays in place and a copy exits the other cup; no parameters. It fails Fit at train0.
- `object-count`
    - `concept`: the input holds one object (`one-object`).
    - `$EachObject`: replaces `one-object`; each component of cells that are neither `background` nor `cup_color` is sent out of the cup other than the one whose mouth it lines up with; no parameters; undefined where some component lines up with no mouth. It fits every pair. Witness `two-objects`: train0 with a second object `2 2` at (3,1), (3,2), in line with the top cup's mouth; breaks `one-object`; `borderline`, verdict `$EachObject`; it breaks the invariant that each input holds one cell set other than the background and the cups.
- `background`
    - `concept`: `background` is stored as 7.
    - `background=DominantColor`: replaces the stored `background` with the color that has the most cells in the input; undefined nowhere the concept is defined. It fits every pair. Witness `background=DominantColor`: train0 with 7 recolored 0; breaks `background`; `variant`, verdict `background=DominantColor`; it breaks the invariant that the background is 7.
- `cup-color`
    - `concept`: `cup_color` is stored as 4 (`two-cups`).
    - `$CupByShape`: replaces `two-cups`; the cups are the one-color components of cup shape on a grid edge, whatever their color, and the object is the one other component; no parameters beyond `background`; undefined where the input does not hold two such cups and one other component. It fits every pair. Witness `cups-of-another-color`: train0 with 4 recolored 2; breaks `two-cups`; `variant`, verdict `$CupByShape`; it breaks the invariant that the cups are 4.
- `object-shape` & `slide-stop`, `object-shape` & `slide-direction`, `object-shape` & `cross-placement`, `object-shape` & `original-cells`, `object-shape` & `object-count`, `object-shape` & `background`, `object-shape` & `cup-color`, `slide-stop` & `slide-direction`, `slide-stop` & `cross-placement`, `slide-stop` & `original-cells`, `slide-stop` & `object-count`, `slide-stop` & `background`, `slide-stop` & `cup-color`, `slide-direction` & `cross-placement`, `slide-direction` & `original-cells`, `slide-direction` & `object-count`, `slide-direction` & `background`, `slide-direction` & `cup-color`, `cross-placement` & `original-cells`, `cross-placement` & `object-count`, `cross-placement` & `background`, `cross-placement` & `cup-color`, `original-cells` & `object-count`, `original-cells` & `background`, `original-cells` & `cup-color`, `object-count` & `background`, `object-count` & `cup-color`, `background` & `cup-color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `background` or `cup_color` by `SharedColor` or `VanishedColor`: on one input, with `ex_out` empty, each gives every color of the input, so the parameter takes the object's color and the other colors as well, and the model fails Fit at train0.
- `background` or `cup_color` by `RarestColor`: it gives the object's color in every input, and the model fails Fit at train0.
- `background` or `cup_color` by `ChangedColor`, `UnchangedColor`, `OutNewColor` or `AnyOutNewColor`: each reads `ex_out`, which is empty on a single input, so it gives no value and the model is undefined at every pair.
- `cup_color` by `DominantColor`: it gives 7, the background, and the model fails Fit at train0.
- `CountRankAsc`, `CountRankDesc` and the dimension and tile proposers: none of them gives a single color, and the parameters here are single colors.
- The object stops against the far side of the entry cup's base line in place of the grid edge: the concept finds a cup only on a grid edge, so the two stops agree wherever the cups are found, and the models are equivalent.
- The object stops at the exit cup's mouth: it fails Fit at every pair.
- The object is turned by the half turn that takes one cup onto the other, or flipped left to right: each fails Fit at train2.
- The entry cup is the cup on a stored side in place of the cup the object lines up with: in every input the object lines up with one mouth, and the reading stores an orientation that the alignment already gives, which the program does not distinguish ([Orientation](docs/handbook/principles.md#orientation)).

## Tickets filed
- none
