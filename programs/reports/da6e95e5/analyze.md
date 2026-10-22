# da6e95e5

## Concept
- The concept fits every pair. `probe.py` parses each frame as four corner brackets of one color and each shape as one 8-connected component strictly inside a frame. In each pair exactly one frame holds a shape of its own color, and the bounding box of that shape is the output.
- No witness has verdict `other`. The generator applies the rule as the concept file states it. In every input, each shape's bounding box is exactly its frame's rectangle inset by 2. `$FrameInset` reads that invariant as the crop window.

## Choice points
- `crop window`
    - `concept`: the bounding box of the matching shape (`crop-matching-shape`)
    - `$FrameInset`: replaces `crop-matching-shape`. The output is the matching frame's rectangle inset by `inset` cells on every side, copied from the input. Parameter `inset`: 2, stored and fixed by Fit, and 1 fails every pair. It is undefined where the concept is undefined, and where the inset leaves no cells. It fits every pair. Witness `wide-frame`, at the stored assignment: a 9×9 frame of 9 around a 3×3 shape of 9. The concept gives the 3×3 shape, and `$FrameInset` gives the 5×5 window with a ring of background. It breaks no scene claim of the concept case. Plausibility `variant`, verdict `concept`. The invariant of the inputs it breaks: every shape's bounding box is its frame's rectangle inset by 2, which leaves a gap of one cell between the shape and the brackets on every side.
- `shape adjacency`
    - `concept`: a shape is one 8-connected component (`framed-shape`)
    - `$FourAdjacent`: replaces `framed-shape` with 4-connected shapes. A frame matches when it holds one 4-connected piece, in the frame's color. It is undefined where the matching shape splits into several pieces. It fails Fit at test0: the X of 2 in the frame at rows 22–28, cols 3–9 splits into five pieces, so no frame matches and the model is undefined.
- `selection`
    - `concept`: the shape whose color equals its frame's color (`crop-matching-shape`, `one-match`)
    - `$MostCommonColor`: replaces the selection in `crop-matching-shape`, and `one-match`. The output crops the framed shape whose color is the grid's most common non-background color. It is undefined where that color ties, or where that color fills several shapes. It fails Fit at train2: 2 is the most common color, and it fills two shapes, the one in the frame of 2 (rows 2–9, cols 2–10) and the one in the frame of 8 (rows 4–11, cols 13–21).
- `crop window` & `shape adjacency`, `crop window` & `selection`, `shape adjacency` & `selection`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Crop of the whole frame interior inside the brackets: this is the `$FrameInset` program at `inset` 1, and Fit fixes `inset` at 2.
- The shape whose color no other shape has: in train0 every shape has its own color (6, 1, 4, 2, 8), so this reading selects no single shape.
- The shape inside a frame of the commonest frame color: in train2 the four frames have four different colors, so no frame color is commonest.
- The output when several frames hold a shape of their own color: no pair and no source gives an output for it, so a branch would add an output that nothing supports.
- A frame found from the colored cells nearest a shape, in place of four brackets: it gives the same frame on every input whose frames are four corner brackets, and no source gives it as a separate reading.

## Tickets filed
- none
