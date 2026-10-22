# c6e1b8da

## Concept
- The concept fits every pair (`check_concept.py`: train0–2 and test0 match).
- No witness with verdict `other`: inside the scene claims, the concept's rules are exact. `restore-whole` reads a still rectangle's extent as the bounding box of its visible cells. In every input the hidden cells of a still rectangle lie inside that box, because a tailed rectangle overlaps it only at a corner or through a tail.

## Choice points
- `background`
    - `concept`: the stored `background`, 0
    - `background=DominantColor`: replaces the stored `background` with the commonest color of each input, ties included; no parameter; undefined on an input where two colors tie for the commonest. Fits every pair. Witness `background=DominantColor`: it stands at the stored assignment and breaks no scene claim; plausibility `borderline`, verdict `concept`; it breaks the invariant that `background` is the commonest color of every input (a still 15×15 rectangle holds more cells than the field).
    - `background=SharedColor`: gives every color of the input, since the input is read alone; undefined on every input with more than one color. Fails Fit at train0.
    - `background=RarestColor`: gives 3 at train0. Fails Fit at train0.
    - `background=OutNewColor`, `background=AnyOutNewColor`, `background=VanishedColor`, `background=ChangedColor`, `background=UnchangedColor`: each reads `ex_out`, which is empty on an input read alone, so it gives no value; undefined on every input. Fails Fit at train0.
- `slide-distance`
    - `concept`: the tail's length (`slide-by-tail`)
    - `$SlideUntilBlocked`: replaces `slide-by-tail`: a tailed rectangle slides toward its tail until the next step would leave the grid or enter another rectangle; no parameter; defined on every input of the scene. Fails Fit at train0: the 5 rectangle reaches cols 11–19, and the output has it at cols 7–15.
- `layering`
    - `concept`: a slid rectangle covers a still one (`slid-on-top`)
    - `$StillOnTop`: replaces `slid-on-top`: a still rectangle covers a slid one where they overlap; no parameter. Fails Fit at train0: rows 11–12, cols 11–12 are 8 in the output, and the branch gives 2.
- `hidden-cells`
    - `concept`: each still rectangle is drawn whole (`restore-whole`)
    - `$HiddenToBackground`: replaces `restore-whole`: a still rectangle keeps only its visible input cells, and a cell a slid rectangle vacates is `background`; no parameter. Fails Fit at train0: rows 4–6, cols 4–6 are 6 in the output, and the branch gives 0.
    - `$RestoreVacatedOnly`: replaces `restore-whole`: a still rectangle keeps its input cells, and a cell a slid rectangle or its tail vacates takes the color of the still rectangle whose bounding box holds it, and `background` elsewhere; no parameter; undefined where two still bounding boxes hold one vacated cell. Fits every pair. Witness `still-rectangles-overlap`: it breaks `tailed-on-top` (a still rectangle hides part of another) and stands at the stored assignment; plausibility `borderline`, verdict `$RestoreVacatedOnly`; it breaks the invariant that no still rectangle overlaps another. The concept is undefined there, because it draws both rectangles whole over the cells they share.
- `tail-place`
    - `concept`: a tail leaves the middle part of a side (`tails`)
    - `$TailAtSideEnd`: replaces `tails`: a tail may also run flush with the end of a side; no parameter. Fails Fit at train0: the 3 rectangle's visible cells (row 12 col 1 over rows 13–14 cols 1–5) read as a body with a tail of length 1 up, so it slides up 1 and row 14 cols 1–5 become 0, where the output has 3.
- `background` & `slide-distance`, `background` & `layering`, `background` & `hidden-cells`, `background` & `tail-place`, `slide-distance` & `layering`, `slide-distance` & `hidden-cells`, `slide-distance` & `tail-place`, `layering` & `hidden-cells`, `layering` & `tail-place`, `hidden-cells` & `tail-place`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The tail kept or dropped in the output: the slid rectangle covers every tail cell, so the two readings give one output on every input.
- An order between two slid rectangles that overlap: no pair shows two slid rectangles meeting, and no reading of the pairs orders them. The concept and every branch are undefined there.
- A still rectangle hidden across a whole side: the input does not show how far that rectangle reaches, and no reading of the pairs gives an extent there.
- Tails thicker than one cell, or two tails on one rectangle: no input shows one, and no reading of the pairs gives a slide for it.

## Tickets filed
- none
