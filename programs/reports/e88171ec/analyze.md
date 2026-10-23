# e88171ec

## Concept
- Fits every pair at the stored assignment (`hole_color` 0, `fill_color` 8, `margin` 1). Each input has one rectangle of 0 that is the unique largest by area: train0 rows 4–9, cols 4–8 (area 30, next 25); train1 rows 3–6, cols 5–8 (16, next 12); train2 rows 10–13, cols 7–12 (24, next 20); test0 rows 12–16, cols 10–15 (30, next 25).
- The generator applies the rule like this: it places a box of hole color in the noise, and it fills the part of that box that is one cell in from the box's edge. The concept's rule, the largest-area rectangle of hole color, is an approximation of that placed box. The two give different outputs where noise joins the hole into a larger rectangle that is thinner. `thin-extension` shows this, and its verdict is the output of `$RankInterior` and `$RankMinSide`. No witness has the verdict `other`.
- In the evidence, noise of hole color touches the hole and makes long runs through it: train0 (5,3); train2 row 11, cols 5–13; test0 rows 15–17, cols 10–12. Away from the hole, the noise makes no rectangle of 0 with an area above 6.

## Choice points
- `fill-region`: which cells take `fill_color`
    - `concept`: the cells `margin` or more in from the edge of one hole region, which an extremum picks
        - `hole-region`: what the extremum ranks
            - `concept`: the rectangles of hole color
                - `ranking`: which rectangle of hole color is the hole
                    - `concept`: the largest area
                    - `$RankInterior`: replaces `one-largest-hole` and `fill-inset`. The hole is the rectangle with the largest inside area, (rows − 2) × (cols − 2). Fits every pair. Witness `thin-extension`: it breaks no scene claim, it stands at the stored assignment, its plausibility is `ordinary`, and its verdict is `$RankInterior`. `$RankMinSide` is in the same group.
                    - `$RankMinSide`: replaces `one-largest-hole` and `fill-inset`. The hole is the rectangle with the longest shorter side, and area breaks a tie. Fits every pair. Witness `thin-extension`: it breaks no scene claim, it stands at the stored assignment, its plausibility is `ordinary`, and its verdict is `$RankInterior`, which is the output of this branch too.
                    - `$RankPerimeter`: replaces `one-largest-hole` and `fill-inset`. The hole is the rectangle with the largest sum of rows and cols, and each rectangle that ties is filled. Fits every pair: in train2 the 1×9 run at row 11, cols 5–13 ties the hole, and that run has an empty inside. Witness `perimeter-run`: it breaks no scene claim, it stands at the stored assignment, its plausibility is `ordinary`, and its verdict is `concept`. This branch picks the 1×10 run and returns the input.
                    - `$RankLongSide`: replaces `one-largest-hole` and `fill-inset`. The hole is the rectangle with the longest longer side, and area breaks a tie. It fails Fit at train0, where it picks the 8×1 run at rows 4–11, col 7.
                    - `$RankOneSide`: replaces `one-largest-hole` and `fill-inset`. The hole is the rectangle that extends farthest along a stored axis, and area breaks a tie. It fails Fit at train0 at each axis value. On the vertical axis it picks rows 4–11, col 7. On the horizontal axis it picks row 6, cols 2–8.
            - `$ComponentErosion`: replaces `one-largest-hole` and `fill-inset`. The hole is the largest 4-connected component of hole color. Each cell of that component whose 8 neighbors are all in it takes `fill_color`. It fails Fit at test0, where it also paints (16,11).
            - `$ComponentBbox`: replaces `one-largest-hole` and `fill-inset`. The hole is the bounding box of the largest 4-connected component of hole color. It fails Fit at train0. There the box is rows 3–11, cols 2–8, and the branch paints rows 4–10, cols 3–7.
        - `tie`: what happens when two hole regions share the top score
            - `concept`: each tied region takes the fill
            - `$TieUndefined`: adds to `fill-inset` the requirement that one region has the top score, and is undefined on a tie. Fits every pair. Where it is defined, its output is the concept's, so it is subsumed by the concept and fails Subsumption. Witness `two-holes`, on which it is undefined: it breaks scene claim `one-largest-hole`, it stands at the stored assignment, its plausibility is `variant`, and its verdict is `concept`. It breaks the invariant of the inputs that each input has one hole.
    - `$LocalErosion`: replaces `one-largest-hole` and `fill-inset`. Each hole-color cell whose 8 neighbors all have the hole color takes `fill_color`, and no region is picked. Defined on every input. It fails Fit at test0. There it also paints (16,11), because rows 15–17, cols 10–12 are all 0.
- `frame-edge`: the margin on a side of the hole that lies on the grid edge
    - `concept`: the margin applies on every side
    - `$FrameAsHole`: replaces `fill-inset`. Cells past the grid edge count as hole color, so a side of the hole that lies on the grid edge keeps no margin. Fits every pair, because no hole in the evidence touches the grid edge. Witness `frame-edge-hole`: it breaks no scene claim, it stands at the stored assignment, its plausibility is `ordinary`, and its verdict is `concept`.
- `hole_color`: how the program gets the hole color
    - `concept`: stored, 0
    - `hole_color=SharedColor`: replaces the stored `hole_color` with each color of the input alone. On train0 that is 0, 4 and 5, so the whole grid is one hole rectangle. It fails Fit at train0.
    - `hole_color=DominantColor`: replaces the stored `hole_color` with the commonest color of the input. On train0 that is 4. It fails Fit at train0.
    - `hole_color=RarestColor`: replaces the stored `hole_color` with the rarest color of the input. On train0 that is 5. It fails Fit at train0.
- `fill_color`: how the program gets the fill color
    - `concept`: stored, 8
    - `fill_color=OutNewColor`: replaces the stored `fill_color` with a color that is in every train output and in no input. A run leaves `ex_out` empty, so the derivation gives no value, and the branch is undefined on every input. It fails Fit at train0.
    - `fill_color=AnyOutNewColor`: replaces the stored `fill_color` with a color that is in some train output and in no input. For the same reason it is undefined on every input. It fails Fit at train0.
- `fill-region` & `frame-edge`, `hole-region` & `frame-edge`, `ranking` & `frame-edge`, `tie` & `frame-edge`, `hole-region` & `tie`, `ranking` & `tie`, `hole_color` & `fill-region`, `hole_color` & `hole-region`, `hole_color` & `ranking`, `hole_color` & `tie`, `hole_color` & `frame-edge`, `hole_color` & `fill_color`, `fill_color` & `fill-region`, `fill_color` & `hole-region`, `fill_color` & `ranking`, `fill_color` & `tie`, `fill_color` & `frame-edge`: the two branches' changes applied together

## Open parameters
none

## Not formed
- `hole_color` derived by `VanishedColor`, `ChangedColor` or `UnchangedColor`: each one reads the train outputs. A run leaves `ex_out` empty, so on one input each one gives no value or every color. Those cases fail at train0 in the same way as `fill_color=OutNewColor` and `hole_color=SharedColor`.
- A derivation of `margin`: no proposer gives the width of a band inside a region.
- `margin` as an open parameter: each pair fixes it at 1, because each fill leaves exactly one ring of 0.

## Tickets filed
none
