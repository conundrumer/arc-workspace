# e41c6fd3

## Concept
- Fits every pair (train0–2, test0), with each copy read as the cells of one color. The copies in every input are identical, so the two edges of `align_axis` give one output on each pair.
- No witness has the verdict `other`. The concept file's rule is the rule the generator applies, and nothing in it is an approximation.
- `anchor` is the one parameter that only the train outputs fix: copy 8 is the topmost copy in train0 and not in train1, the middle copy in train0 and the leftmost in train1, so no positional reading picks it out.

## Choice points
- `copy-reading`
    - `concept`: a copy is all the cells of one non-background color
    - `$ObjectComponents`: replaces `copies-of-one-shape` with each 4-connected component of one color being a copy; same parameters; undefined where the `anchor` color has more than one component. Fits every pair. Witness `two-copies-one-color`: color 2 forms two copies at different heights. Breaks `copies-of-one-shape` at the stored assignment. Plausibility `variant`, verdict `$ObjectComponents`.
        - `adjacency`
            - `concept`: 4-adjacency
            - `$Adjacency8`: components join at corners as well; same parameters; undefined where the `anchor` color has more than one 8-connected component. Fits every pair. Witness `diagonal-shape`: a shape joined only at corners, on which the 4-adjacency reading finds three anchor components and is undefined. Breaks no scene claim of the concept case. Plausibility `variant`, verdict `$Adjacency8` (the concept case gives the same output). It breaks this invariant of the inputs: every copy is 4-connected.
- `alignment-reference`
    - `concept`: the copy's line on each edge of `align_axis` meets the anchor's line on that edge; undefined where the two edges give different outputs
    - `$AlignCenter`: replaces `align-to-anchor` with the copy's span on the slide axis and the anchor's span having one center; it reads only `align_axis`; undefined where the two spans differ in length by an odd count. Fits every pair. Witness `taller-copy`: the 2 copy is two rows taller than the anchor, so the concept's two edges give different outputs and it is undefined. Breaks `copies-of-one-shape` at the stored assignment. Plausibility `borderline`, verdict `any`. It breaks this invariant of the inputs: all copies have one shape, so their spans are equal in length.
- `slide-axis`
    - `concept`: the stored `align_axis`
    - `$AxisFromLayout`: replaces `align_axis` with a derivation: the slide axis is the one whose cross axis has the copies' spans pairwise disjoint. It runs both edges of that axis, as the concept does, and is undefined where they disagree. Undefined where the spans are pairwise disjoint on both axes or on neither. Fits every pair: the column spans are pairwise disjoint in every input, and in each input some two row spans overlap. Witness `stacked-copies`: copies are stacked in disjoint rows and share columns, so a vertical slide makes them collide. Breaks `disjoint-columns` at the stored assignment. Plausibility `variant`, because the transposed variant task gives this input. Verdict `$AxisFromLayout`. It breaks this invariant of the inputs: no two copies share a column.
- `background-source`
    - `concept`: the stored `background`
    - `background=DominantColor`: replaces the stored `background` with the commonest color of the input; undefined where that count ties. Fits every pair. Witness `background=DominantColor`: a 4×4 grid in which colors 8 and 2 each outnumber color 0. Breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: color 0 covers most of every input. No witness was found on which this branch is defined and differs from the concept. Where the dominant color is a copy color, the 0 cells become one class that spans the frame, and that class slides out of the frame or lands on its own place.
    - `background=SharedColor`, `background=RarestColor`, `background=UnchangedColor`: each fails Fit at train0. On one input with `ex_out` empty, SharedColor gives every color of the input and RarestColor gives the three tied copy colors. UnchangedColor gives nothing.
- `anchor-source`
    - `concept`: the stored `anchor`
    - `anchor=SharedColor`, `anchor=RarestColor`, `anchor=DominantColor`, `anchor=UnchangedColor`: each fails Fit at train0. On train0's input, SharedColor gives `0 2 4 8`, RarestColor gives the tied `2 4 8`, DominantColor gives `0`, which is no copy, and UnchangedColor gives nothing with `ex_out` empty.
- `originals`
    - `concept`: a moved copy's old cells become `background`
    - `$KeepOriginals`: replaces `clear-rest` by drawing each moved copy over the input. Fails Fit at train0.
- `copy-reading` & `alignment-reference`, `copy-reading` & `slide-axis`, `copy-reading` & `background-source`, `alignment-reference` & `slide-axis`, `alignment-reference` & `background-source`, `slide-axis` & `background-source`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A positional reading of the anchor (topmost, leftmost, middle, largest copy): no such reading picks copy 8 in all three train pairs, and the copies are all the same size.
- A derivation of `align_axis` from the grid's dimensions: the axis proposers give axes of the grid's dimensions, and those give both axes on one input. The derivation from the layout is `$AxisFromLayout`.
- A tie order for copies that collide after the slide: `disjoint-columns` holds in every input, so no pair or witness of the fitting branches has a collision to order. The concept is undefined there.
- Copies that keep their column order with closed gaps, or that pack against the anchor: the train outputs keep every copy's columns.

## Tickets filed
none
