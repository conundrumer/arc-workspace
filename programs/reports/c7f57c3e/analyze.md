# c7f57c3e

## Concept
- Fits every pair (`work/task/c7f57c3e/check.py`). Each figure keeps its body of `frame-color` cells and takes the other of the two patterns, at its own scale, at the same place relative to its body.
- Where a pattern holds a color that is on every figure in one shape, the concept is the only fitting reading that stays defined. Witness `pattern-colors-shared`: `ordinary`, verdict `concept`.
- The stored `frame-color` makes the concept undefined on a variant task whose body is another color. Witness `$FrameColorsByShape` shows this.
- No witness has verdict `other`. A scene with three or more patterns breaks `two-decorations`, and the generator, which makes one odd figure among copies of one other, does not make such a scene.

## Choice points
- `figure-adjacency`
    - `concept`: a figure is one 8-connected group of non-background cells
    - `$FourAdjacent`: replaces `figures` with 4-connected groups. Undefined where a body has only diagonal contacts. Fails Fit at train1, where the X-shaped figures break into single cells.
- `frame-color`
    - `concept`: stored, 1
    - `$FrameColorsByShape`: replaces the stored `frame-color` with a derivation from the input: each color that every figure carries, whose cells form one shape on every figure up to the figure's scale (in train1 this gives 1 and 2, and elsewhere 1). Undefined where those colors take different places on different figures. Fits every pair, and meets Equivalence and Subsumption.
        - Witness `$FrameColorsByShape`: the stored assignment. It breaks `scaled-copies-of-one-body` (no cell is `frame-color` 1). Plausibility `variant`, verdict `$FrameColorsByShape`. The invariant it breaks: the body is color 1 in every input.
        - Witness `pattern-colors-shared`: the stored assignment. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`. There, `$FrameColorsByShape` takes the 2 cell into the body and is undefined.
    - `$FrameColorsInEveryFigure`: replaces the stored `frame-color` with each color that every figure carries. Undefined where such a color has a different shape on different figures. Fails Fit at train0, where color 2 is on every figure, as the center alone on one figure and as the center and the stem on the others.
    - `frame_color=SharedColor`, `frame_color=VanishedColor`: with `ex_out` empty, each gives every color of the input, background included. Fail Fit at train0.
    - `frame_color=DominantColor`: gives the background. Fails Fit at train0.
    - `frame_color=RarestColor`: gives 8 in train0 and 6 in train1, which are not on every figure. Fails Fit at train0.
    - `frame_color=OutNewColor`, `frame_color=AnyOutNewColor`, `frame_color=ChangedColor`, `frame_color=UnchangedColor`: with `ex_out` empty, these give no value, so they are undefined on every input. Fail Fit at train0.
- `pattern-anchor`
    - `concept`: the pattern is placed relative to the top-left corner of the body
    - `$BboxAnchor`: replaces the anchor in `swap-decorations` with the top-left corner of the figure's bounding box. Undefined where the bodies take different places in their boxes. Fails Fit at train1, because the 6 above one figure moves its box up by one row.
- `pattern-scale`
    - `concept`: the pattern is drawn at the figure's scale
    - `$UnscaledDecoration`: replaces the scaling in `swap-decorations` with one cell for each pattern cell. Fails Fit at train0, on the scale-2 figure.
- `exchange-rule`
    - `concept`: the two patterns swap on every figure
    - `$OddOneOut`: replaces `swap-decorations`. The one figure whose pattern no other figure carries takes the shared pattern, and every other figure takes the odd figure's pattern. Undefined where no single figure is the odd one. Fits every pair. Fails Subsumption: it is defined only where the concept is defined, and there it gives the concept's output.
        - Witness `two-figures-per-pattern`: the stored assignment, with two figures for each pattern. It breaks no scene claim. Plausibility `variant`, verdict `concept`. The invariant it breaks: in every input, exactly one figure carries its pattern. `$OddOneOut` is undefined there.
- `figure-adjacency` & `frame-color`, `figure-adjacency` & `pattern-anchor`, `figure-adjacency` & `pattern-scale`, `figure-adjacency` & `exchange-rule`, `frame-color` & `pattern-anchor`, `frame-color` & `pattern-scale`, `frame-color` & `exchange-rule`, `pattern-anchor` & `pattern-scale`, `pattern-anchor` & `exchange-rule`, `pattern-scale` & `exchange-rule`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A color mapping from input to output: in train0, one figure's 8 cells become 2 on the stem and 3 on the base, and in train1 the changed cells move. No mapping of colors fits.
- A stored background color: the background is 4, 3 and 8 in the three pairs, so it is derived as the commonest color, and no stored value fits.
- Keeping the cells that both patterns share and swapping only the cells where they differ: this gives the concept's grid on every input where either is defined, because a shared cell is cleared and then painted again in its own color.
- A cycle over three or more patterns: no pair, solver header or proposer gives an order among the patterns, and the generator makes two.

## Tickets filed
- 10-540_task_c7f57c3e_analyze.md
