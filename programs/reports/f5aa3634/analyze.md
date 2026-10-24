# f5aa3634

## Concept
- Fits every pair (train0–2, test0): the objects are the 4-connected groups of non-`background` cells, two objects are the same when their colored cells match up to translation, and the output is the one object class with more than one member, cropped to its bounding box on `background` (`background` = 0, stored). It is undefined where no class, or more than one class, repeats.
- Every branch below fits every pair as well. On the pairs, every reading of adjacency, sameness, selection, frame and background gives the same output, so no pair separates them, and each separation comes from a witness in `programs/reports/f5aa3634/witnesses.json`.
- No witness has verdict `other`. The rule as the generator applies it ("show the object that appears twice") is the concept file's `crop-repeated`. It has a relational form and is no approximation.
- The lib `Components` call raised `no souffle binary on PATH`, and a Python flood fill stood in for it in the probes (`progress-analyze.md`).

## Choice points
- `adjacency`
    - `concept`: objects are 4-connected components of the non-background cells
    - `$Adjacency8`: replaces `scattered-objects` with 8-connected objects, so a cell meeting its object at a corner only belongs to it. No parameters, and undefined where the concept is (no class, or several classes, repeat). Fits every pair. Witness `diagonal-joint`: train0's input with a 4 at (3,1) and (9,8), each meeting one copy at a corner only. It breaks `one-repeated-object` (under 4-adjacency the 4-cell is an object that also occurs twice). Plausibility `variant`, verdict `$Adjacency8`. It breaks the invariant that every object of every input is 4-connected.
- `color-match`
    - `concept`: two objects are the same when the color at each cell matches as well as the cell set
    - `$ShapeOnly`: replaces `one-repeated-object` and `crop-repeated`: objects are classed by cell set alone, and the output is the distinct crops of the repeated class's members. No parameters, and undefined where no class or several classes repeat, or the members give more than two distinct crops. Fits every pair. Witness `recolored-distractor`: two copies of train0's object and one same-shaped object in 6/1/4. Breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant that no two objects of an input share a shape apart from the copies.
- `transform-match`
    - `concept`: two objects are the same up to translation alone
    - `$Congruent`: replaces `one-repeated-object` and `crop-repeated`: objects are classed up to D4 plus translation, and the output is the distinct crops of the repeated class's members. No parameters, and undefined where no class or several classes repeat, or the members give more than two distinct crops. Fits every pair. Witness `mirrored-distractor`: two copies of train0's object and one left-right mirror of it. Breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant that no two objects of an input are congruent apart from the copies.
- `selection`
    - `concept`: the one class with more than one member
    - `$MostFrequent`: replaces `one-repeated-object` and `crop-repeated` with the class of highest count. No parameters, and undefined on a tie for the highest count. Fits every pair. Witness `triple-and-pair`: train0's object three times, train0's 7/2 object twice, and one other object. It breaks `one-repeated-object`. Plausibility `variant`, verdict `$MostFrequent`. It breaks the invariant that each input holds exactly two copies of one object and one of each other.
    - `$CopyCount`: replaces `one-repeated-object` and `crop-repeated` with the class of exactly `copies` members. Parameter `copies` = 2, and undefined where no class or several classes have `copies` members. Fits every pair. Witness `triple-and-pair` (it gives the pair, the 7/2 object). It breaks `one-repeated-object`. Plausibility `variant`, verdict `$MostFrequent`. It breaks the same invariant.
- `output-frame`
    - `concept`: the object's own cells on `background` inside its bounding box
    - `$CropRegion`: replaces `crop-repeated` with the input's subgrid at each copy's bounding box, as the set of distinct subgrids. No parameters, and undefined where the concept is. Fits every pair. Witness `decoy-in-bbox`: a repeated L, with a one-cell 6 inside one copy's box that touches the L at no side or corner. Breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant that no object's bounding box holds a cell of another object.
- `background`
    - `concept`: `background` stored as 0
    - `background=DominantColor`: derives `background` per input as its commonest color, replacing the stored value in `scattered-objects` and `crop-repeated`. Undefined on an input whose commonest color is tied, and where the concept is. Fits every pair (0 is the commonest color of every input). Witness `background=DominantColor`: train0's input with 0 recolored to 1. It breaks `scattered-objects` (the field is not 0), and with 0 stored the whole grid is one object, so the concept is undefined. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that the field is 0 in every input.
- `adjacency` & `color-match`, `adjacency` & `transform-match`, `adjacency` & `selection`, `adjacency` & `output-frame`, `adjacency` & `background`, `color-match` & `transform-match`, `color-match` & `selection`, `color-match` & `output-frame`, `color-match` & `background`, `transform-match` & `selection`, `transform-match` & `output-frame`, `transform-match` & `background`, `selection` & `output-frame`, `selection` & `background`, `output-frame` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Selecting the largest object by cell count: fails Fit at train1, where the unique object at rows 1–4, cols 1–3 has 9 cells and each copy has 7.
- Selecting by place (lowest, topmost, rightmost object): fails Fit at train1. The lowest and the rightmost object there is the unique 6/8/4 object at rows 10–14, cols 8–10, and the topmost is the unique object at rows 1–4.
- Selecting by a color the object holds: the repeated objects' palettes {3,5,8}, {5,8}, {5,7,9}, {3,4,8} share no color, so no stored color picks them.
- `background` derived by SharedColor: it gives 0, 2, 3, 5 and 8 on every input, so it determines no single field color.
- An output height fixed at ConstOutDimAxis's 3 (every train output has 3 rows): the test output has 4 rows, so it fails Fit at test0, and the crop already gives the height.

## Tickets filed
- none
