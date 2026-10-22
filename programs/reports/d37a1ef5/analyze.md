# d37a1ef5

## Concept
- The concept fits every pair (train0–2 and test0, checked by `probe.py`). The concept model reads each region that `frame_color` cells close off from the grid edge as one interior. Its marks are the non-`background` cells of that interior. It keeps the bounding box of those marks and fills the rest of the interior with `frame_color`. An interior with no mark fills whole.
- Each rule has a relational form, through the `Closed` and `Bbox` components. No rule is approximated.
- No witness has the verdict `other`.
- Two witnesses have a branch's verdict, so the concept model is not what a person expects on them:
    - `broken-outline` has the verdict `$InteriorByFrameBox`.
    - `recolored-frame` has the verdict `$FrameColorFromOutline`.

## Choice points
- `kept-region`: which interior cells stay open
    - `concept`: the bounding box of the marks
    - `$EmptyLinesFilled`: replaces `fill-outside-box` and `keep-box`; a cell stays open only when its row and its column each hold a mark. No parameters. Defined on every input. Fails Fit at train0: (3,4) and (4,4) stay 0 in the output, and column 4 holds no mark.
    - `$UniformDepth`: replaces `fill-outside-box` and `keep-box`; the interior fills ring by ring to the depth of the shallowest mark. No parameters. Undefined on no input. Fails Fit at train1: the shallowest mark, (4,3), sits at depth 1, and the output fills row 3, which is also at depth 1.
    - `$RayFromFrame`: replaces `fill-outside-box` and `keep-box`; a cell fills when a straight run from it to the frame on some side holds no mark. No parameters. Defined on every input. Fails Fit at train0, at (4,3).
    - `$MarkHull`: replaces `fill-outside-box` and `keep-box`; the kept cells are the convex hull of the marks. No parameters. Defined on every input. Fails Fit at train0: (4,3) and (4,4) stay 0, outside the hull of (3,3), (3,6) and (4,5).
- `mark-set`: which interior cells are marks
    - `concept`: the non-`background` cells
        - `background`: how the background color is found
            - `concept`: stored, 0
            - `background=DominantColor`: replaces the stored `background` with the commonest color of the input. Undefined on no input. Fits every pair. Witness `background=DominantColor`. It breaks no scene claim and stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that background surrounds the frame on every side. Verdict `concept`.
            - `background=SharedColor`: replaces the stored `background` with each color of the input. Fails Fit at train0, where its output holds several grids.
            - `background=RarestColor`: replaces the stored `background` with the rarest color of the input. Fails Fit at train0.
    - `$MarkColorStored`: replaces the marks in `marks-inside` with the interior cells of a stored `mark_color` (5). Other cells of the interior are filled over. Parameters `frame_color` and `mark_color`. Defined on every input. Fits every pair. Witness `other-color-mark`. It breaks `marks-inside` and stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that one color draws every mark. Verdict `concept`.
        - `mark-color`: how the mark color is found
            - `concept`: stored, 5
            - `mark_color=RarestColor`: replaces the stored `mark_color` with the rarest color of the input. Undefined on no input. Fits every pair. Witness `mark_color=RarestColor`. It breaks `background`, because a 3 cell sits outside the frame, and stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that no cell outside the frame is non-background. Verdict `concept`, which is the output of `$MarkColorStored`.
            - `mark_color=DominantColor`: replaces the stored `mark_color` with the commonest color of the input. Fails Fit at train0.
            - `mark_color=SharedColor`: replaces the stored `mark_color` with each color of the input. Fails Fit at train0.
- `mark-scope`: which marks the box bounds
    - `concept`: the marks inside the frame's interior
    - `$GlobalMarksBox`: replaces `marks-inside` and `fill-outside-box`; one box bounds every non-`background`, non-`frame_color` cell of the grid. Each interior fills outside that box. Parameters `background` and `frame_color`. Defined on every input. Fits every pair. Witness `stray-mark-outside`. It breaks `background` and stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that no cell outside the frame is non-background. Verdict `concept`.
- `interior`: which cells form the interior
    - `concept`: each region that `frame_color` cells close off from the grid edge
    - `$InteriorByFrameBox`: replaces `one-frame`; the interior is every non-`frame_color` cell strictly inside the bounding box of the `frame_color` cells. Parameters `background` and `frame_color`. Defined on every input. Fits every pair. Witness `broken-outline`. It breaks `one-frame` and stands at the stored assignment. Plausibility `foreign`. It breaks the invariant that every outline is closed. Verdict `$InteriorByFrameBox`.
- `empty-frame`: an interior with no mark
    - `concept`: fills whole
    - `$EmptyFrameKept`: adds to `fill-outside-box` that an interior with no mark keeps its input. Parameters `background` and `frame_color`. Defined on every input. Fits every pair. Witness `empty-frame`. It breaks `marks-inside` and stands at the stored assignment. Plausibility `borderline`. It breaks the invariant that every frame holds a mark. Verdict `concept`.
- `frame-color`: how the frame color is found
    - `concept`: stored, 2
    - `$FrameColorFromOutline`: replaces the stored `frame_color` in `one-frame` with a value the program derives. The value is each color, other than the corner cell's color, whose absence closes cells off from the grid edge. The branch is undefined on an input where no color does so. Fits every pair. Witness `recolored-frame`. It breaks `one-frame` and stands at the stored assignment. Plausibility `variant`. Verdict `$FrameColorFromOutline`.
    - `frame_color=SharedColor`: replaces the stored `frame_color` with each color of the input. Fails Fit at train0.
    - `frame_color=DominantColor`: replaces the stored `frame_color` with the commonest color of the input. Fails Fit at train0.
    - `frame_color=RarestColor`: replaces the stored `frame_color` with the rarest color of the input. Fails Fit at train0.
- `kept-region` & `mark-set`, `kept-region` & `mark-scope`, `kept-region` & `interior`, `kept-region` & `empty-frame`, `kept-region` & `frame-color`, `kept-region` & `background`, `kept-region` & `mark-color`, `mark-set` & `mark-scope`, `mark-set` & `interior`, `mark-set` & `empty-frame`, `mark-set` & `frame-color`, `mark-scope` & `interior`, `mark-scope` & `empty-frame`, `mark-scope` & `frame-color`, `mark-scope` & `background`, `mark-scope` & `mark-color`, `interior` & `empty-frame`, `interior` & `frame-color`, `interior` & `background`, `interior` & `mark-color`, `empty-frame` & `frame-color`, `empty-frame` & `background`, `empty-frame` & `mark-color`, `frame-color` & `background`, `frame-color` & `mark-color`: the two branches' changes applied together
- `background` & `mark-color`: no case takes a non-concept branch at both, because the two points stand under different branches of `mark-set`
- `mark-set` & `background`: `background` stands under the concept branch of `mark-set`, because `$MarkColorStored` reads no background, so `$MarkColorStored` & `background=DominantColor` is the model of `$MarkColorStored` alone

## Open parameters
- none

## Not formed
- A fill color stored apart from `frame_color`: the fill takes the frame color in every variant task, so this is a redundant value.
- The box's non-mark cells cleared to `background` in place of kept: those cells are `background` already, so the two models are equivalent.
- Marks that touch the frame (`gap-to-frame`): no reading of the pairs gives a different output there.

## Tickets filed
- 10-685_task_d37a1ef5_analyze.md
