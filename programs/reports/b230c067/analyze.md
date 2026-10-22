# b230c067

## Concept
- Fits every pair. Every witness's verdict is `concept` or a branch's name, so the concept case has no witness with verdict `other`.
- The test is the only input in which an object is joined only at a corner, so 8-adjacency is a reading the test supports, not one the train pairs show. 4-adjacency still fits, because the parts a 4-adjacent reading splits the test objects into come out in the right colors by chance.
- In every pair the odd object also has a unique cell count, a unique bbox extent, the fewest cells and the smallest bbox. Each of those readings fits every pair and is a branch at `odd-object`.

## Choice points
- `adjacency`
    - `concept`: objects are 8-connected components.
    - `$FourAdjacent`: replaces `objects-of-one-color` with 4-connected components. Defined on every input. Fits every pair. Witness `diagonal-odd`: breaks no scene claim, `ordinary`, verdict `concept`.
- `odd-object`
    - `concept`: an object is odd when no other object has its shape up to translation (`copies-take-copy-color`, `odd-takes-odd-color`).
    - `$UniqueCount`: replaces both rules. An object is odd when no other object has its cell count. Defined on every input. Fits every pair. Witness `same-size-odd`: breaks no scene claim, `ordinary`, verdict `concept`.
    - `$UniqueBbox`: replaces both rules. An object is odd when no other object has its bbox extent (height, width). Defined on every input. Fits every pair. Witness `same-size-odd`: breaks no scene claim, `ordinary`, verdict `concept`.
    - `$UniqueCongruent`: replaces both rules. An object is odd when no other object has its shape up to a D4 transform and translation. Defined on every input. Fits every pair. Witness `rotated-odd`: breaks no scene claim, because under translation the turned L is a different shape. `ordinary`, verdict `concept`.
    - `$FewestCells`: replaces both rules. Each object with the fewest cells (ties included) is odd. Defined on every input. Fits every pair. Witness `larger-odd`: breaks no scene claim, `ordinary`, verdict `concept`.
    - `$SmallestBbox`: replaces both rules. Each object with the smallest bbox area (ties included) is odd. Defined on every input. Fits every pair. Witness `larger-odd`: breaks no scene claim, `ordinary`, verdict `concept`.
    - `$OutsideMajority`: replaces both rules. Objects of the commonest shape (up to translation) take `copy_color`, and every other object takes `odd_color`. Defined on every input. Fits every pair. Witness `two-odd`: breaks `copies-and-one-odd`, `borderline`, verdict `$OutsideMajority`. It breaks this invariant of the inputs: exactly one object lacks a copy.
    - `$CopyCountClass`: replaces both rules and reads `copy_count` (2) as a parameter. Objects whose shape class has exactly `copy_count` members take `copy_color`, and every other object takes `odd_color`. Defined on every input. Fits every pair. Witness `three-copies`: breaks `copies-and-one-odd` at the stored `copy_count`, `variant`, verdict `concept`. It breaks this invariant of the inputs: each input has two copies.
    - `$ShapeTable`: replaces both rules with a stored table from shape to output color. Fails Fit at test0, because no train pair has the test shapes as keys (Unseen key).
- `object-cells`
    - `concept`: objects are made of the `object_color` cells, and any other cell keeps its color.
        - `object_color`
            - `concept`: stored, 8.
            - `object_color=RarestColor`: derives the rarest color of the input. Undefined on an input where colors tie for rarest. Fits every pair. Witness `object_color=RarestColor`: breaks no scene claim, `borderline`, verdict `concept`. It breaks this invariant of the inputs: background cells outnumber object cells.
            - `object_color=DominantColor`: fails Fit at train0, where it derives 0.
            - `object_color=SharedColor`, `object_color=VanishedColor`: fail Fit at train0, where each derives both 0 and 8.
            - `object_color=OutNewColor`, `object_color=AnyOutNewColor`, `object_color=ChangedColor`, `object_color=UnchangedColor`: fail Fit at train0. With `ex_out` empty, each derives no value, so the model is undefined there.
    - `$NonBackgroundObjects`: replaces `objects-of-one-color` and `rest-kept`. Objects are the components of the cells that are not `background`, and `background` (0) becomes a parameter. Defined on every input. Fits every pair. Witness `stray-cell`: breaks `objects-of-one-color`, `borderline`, verdict `concept`. It breaks this invariant of the inputs: each input has only 0 and 8.
        - `background`
            - `concept`: stored, 0.
            - `background=DominantColor`: derives the commonest color of the input. Undefined on an input where colors tie for commonest. Fits every pair. Witness `$NonBackgroundObjects & background=DominantColor`: breaks no scene claim, `borderline`, verdict `concept`. It breaks this invariant of the inputs: background cells outnumber object cells.
            - `background=RarestColor`: fails Fit at train0, where it derives 8.
            - `background=SharedColor`, `background=VanishedColor`: fail Fit at train0, where each derives both 0 and 8.
            - `background=OutNewColor`, `background=AnyOutNewColor`, `background=ChangedColor`, `background=UnchangedColor`: fail Fit at train0. With `ex_out` empty, each derives no value.
        - `shape-colors`
            - `concept`: shapes compare by cell set alone.
            - `$ColoredShapes`: shapes compare by cell set and the color of each cell. Defined on every input. Fits every pair. Witness `recolored-copy-cell`: breaks `objects-of-one-color`, `borderline`, verdict `$NonBackgroundObjects`. It breaks this invariant of the inputs: each input has only 0 and 8.
- `copy_color`
    - `concept`: stored, 1.
    - `copy_color=SharedColor`, `copy_color=DominantColor`, `copy_color=RarestColor`, `copy_color=VanishedColor`: fail Fit at train0. From an input alone they derive 0 or 8 or both, and never 1.
    - `copy_color=OutNewColor`, `copy_color=AnyOutNewColor`, `copy_color=ChangedColor`, `copy_color=UnchangedColor`: fail Fit at train0. With `ex_out` empty, each derives no value.
- `odd_color`
    - `concept`: stored, 2.
    - `odd_color=SharedColor`, `odd_color=DominantColor`, `odd_color=RarestColor`, `odd_color=VanishedColor`: fail Fit at train0. From an input alone they derive 0 or 8 or both, and never 2.
    - `odd_color=OutNewColor`, `odd_color=AnyOutNewColor`, `odd_color=ChangedColor`, `odd_color=UnchangedColor`: fail Fit at train0. With `ex_out` empty, each derives no value.
- `adjacency` & `odd-object`, `adjacency` & `object-cells`, `adjacency` & `object_color`, `adjacency` & `background`, `adjacency` & `shape-colors`, `adjacency` & `copy_color`, `adjacency` & `odd_color`, `odd-object` & `object-cells`, `odd-object` & `object_color`, `odd-object` & `background`, `odd-object` & `copy_color`, `odd-object` & `odd_color`, `object-cells` & `copy_color`, `object-cells` & `odd_color`, `object_color` & `copy_color`, `object_color` & `odd_color`, `background` & `copy_color`, `background` & `odd_color`, `shape-colors` & `copy_color`, `shape-colors` & `odd_color`, `copy_color` & `odd_color`: the two branches' changes applied together
- `odd-object` & `shape-colors`: the odd-object branch's test is made on shapes that carry the color of each cell, under `$NonBackgroundObjects`.
    - `$UniqueCount` & `$ColoredShapes`, `$UniqueBbox` & `$ColoredShapes`, `$FewestCells` & `$ColoredShapes`, `$SmallestBbox` & `$ColoredShapes`, `$ShapeTable` & `$ColoredShapes`: `$NonBackgroundObjects` with that odd-object branch alone. Of these, all but `$ShapeTable` compare no shapes, so the shape-colors property does not exist with them. `$ShapeTable` fails Fit either way.
- `object_color` and `background` stand under different branches of `object-cells`, and `shape-colors` and `object_color` do too, so no case takes a non-concept branch at both points of either pair.

## Open parameters
- none

## Not formed
- The odd object picked by its place in the grid: the odd object is top-right in train0 and train1, left in train2 and top-left in test0. No place property separates it from both copies in every pair, so no reading by place can be stated.
- The odd object picked by its color: in every input all objects have one color, so color has nothing to separate. Where colors differ is the domain of `$ColoredShapes`.

## Tickets filed
- none
