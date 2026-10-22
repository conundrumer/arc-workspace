# b190f7f5

## Concept
- Fits every pair (`probe.py` checks it). The rule `stamp-shape` has a relational form: the output cell decomposes, by `concat_2d`, into a pattern cell and a cell of the shape's square, and takes the pattern cell's color where both are inked. No approximation stands in for it.
- The split axis and the block side are derived per input: the train inputs are all split side by side, and the test input is split top over bottom; train0 and train1 have 3×3 halves, and train2 and test0 have 4×4 halves.
- No witness with verdict `other` was found. A pattern half that holds 8, and halves that are equal rectangles and not squares, break scene claims. On each of them, the concept's clauses give the output a person would draw.

## Choice points
- `template-half`: which half is the shape
    - `concept`: the half that holds only `template_color` and `background`
    - `$MonoTemplate`: replaces `template-half`. The shape is the half whose non-`background` cells are of one color, and those cells are the shape. It reads no `template_color`. It is undefined where both halves, or neither half, are of one color. It fits every pair. Witness `template-in-other-color` (the shape drawn in 5): breaks `template-half`, `variant`, verdict `$MonoTemplate`. Invariant broken: every input draws the shape in 8. It fails Subsumption by `$FewerColorsTemplate`. Where `$MonoTemplate` is defined, one half has one color and the other half has none or two or more. Where the other half has two or more, `$FewerColorsTemplate` picks the same half. Where the other half has none, both give an all-`background` output.
    - `$FewerColorsTemplate`: replaces `template-half`. The shape is the half with fewer non-`background` colors, and its non-`background` cells are the shape. It reads no `template_color`. It is undefined where the two halves have equally many colors. It fits every pair. Witness `template-in-other-color`: breaks `template-half`, `variant`, verdict `$FewerColorsTemplate`. Invariant broken: every input draws the shape in 8.
    - `$StoredTemplateSide`: replaces `template-half` with a stored side of the split (the second half, from train0), whose non-`background` cells are the shape. It fails Fit at train1, where the shape is the first half.
- `template_color`: the value of `template_color`
    - `concept`: stored, 8
    - `template_color=VanishedColor`: derived. On an input alone, with `ex_out` empty, it gives every color of that input, so both halves hold only `template_color` and `background`, and the model is undefined. It fails Fit at train0.
- `bg`: the value of `background`
    - `concept`: stored, 0
    - `bg=DominantColor`: derived. On test0 the derivation gives 0 and 8, each with 12 cells, and the model is undefined there. It fails Fit at test0.
- `split-axis`: the axis that the input divides along into two halves
    - `concept`: derived per input, the long axis
    - `$StoredSplitAxis`: replaces `two-square-halves` with a stored axis (side by side, from the train pairs). It fails Fit at test0, which is split top over bottom.
- `block-side`: n, the side of each half
    - `concept`: derived per input, the short side of the input
    - `$StoredBlockSide`: replaces `two-square-halves` and `output-size` with a stored n (3, from train0). It fails Fit at train2.
- `template-frame`: the frame of the shape that each block copies
    - `concept`: the whole half
    - `$TemplateBbox`: replaces `output-size` and `stamp-shape`. The frame is the bounding box of the `template_color` cells, and the blocks have that box's size. It is undefined where the half holds no `template_color` cell. It fits every pair. Witness `shape-short-of-square` (the 8 shape fills only the top-left 2×2 of its 3×3 half): `ordinary`, verdict `concept`.
- `pattern-frame`: the frame of the pattern that indexes the blocks
    - `concept`: the whole half
    - `$PatternBbox`: replaces `output-size` and `stamp-shape`. The pattern is the bounding box of its non-`background` cells. It fails Fit at train0, where pattern row 2 is empty.
- `roles`: which half indexes the blocks
    - `concept`: the pattern indexes the blocks, and each block holds the shape
    - `$SwapRoles`: replaces `stamp-shape`. The shape's cells index the blocks, and each block holds the pattern in its own colors. It fails Fit at train0.
- `stamp-color`: the color of a stamped cell
    - `concept`: the color of the pattern cell
    - `$TemplateColorStamp`: replaces `stamp-shape`. A stamped cell keeps the shape's own color. It fails Fit at train0.
- `template-half` & `bg`, `template-half` & `split-axis`, `template-half` & `block-side`, `template-half` & `template-frame`, `template-half` & `pattern-frame`, `template-half` & `roles`, `template-half` & `stamp-color`, `template_color` & `bg`, `template_color` & `split-axis`, `template_color` & `block-side`, `template_color` & `template-frame`, `template_color` & `pattern-frame`, `template_color` & `roles`, `template_color` & `stamp-color`, `bg` & `split-axis`, `bg` & `block-side`, `bg` & `template-frame`, `bg` & `pattern-frame`, `bg` & `roles`, `bg` & `stamp-color`, `split-axis` & `block-side`, `split-axis` & `template-frame`, `split-axis` & `pattern-frame`, `split-axis` & `roles`, `split-axis` & `stamp-color`, `block-side` & `template-frame`, `block-side` & `pattern-frame`, `block-side` & `roles`, `block-side` & `stamp-color`, `template-frame` & `pattern-frame`, `template-frame` & `roles`, `template-frame` & `stamp-color`, `pattern-frame` & `roles`, `pattern-frame` & `stamp-color`, `roles` & `stamp-color`: the two branches' changes applied together
- `template-half` & `template_color`: each non-concept branch of `template-half` reads no `template_color`, so the model is that branch's model alone. `template_color` exists only with the concept branch of `template-half`.
    - `$MonoTemplate` & `template_color=VanishedColor`: the model of `$MonoTemplate`
    - `$FewerColorsTemplate` & `template_color=VanishedColor`: the model of `$FewerColorsTemplate`
    - `$StoredTemplateSide` & `template_color=VanishedColor`: the model of `$StoredTemplateSide`

## Open parameters
- none

## Not formed
- Halves as equal rectangles in place of squares: one program serves both. The block extent on each axis is read from the half, so no model differs.
- The shape found as the half whose colors are absent from the output: it reads the output, which a test input does not have.
- `template_color` derived by `SharedColor`, `RarestColor`, `OutNewColor` or `DominantColor`, and `bg` derived by `SharedColor` or `RarestColor`: on the full evidence, none of them gives the stored value alone.
- An overlay of the two halves cell by cell (`PanelCombine`): the output is n²×n², not a half's frame.

## Tickets filed
- none
