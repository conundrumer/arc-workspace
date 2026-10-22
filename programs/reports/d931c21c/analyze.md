# d931c21c

## Concept
- Fits every pair, train and test (`probe.py`). Every claim has a relational form, and no witness has the verdict `other`.
- The concept file's rules give each closed outline its own hole: a region that no 8-step walk through cells outside that outline reaches from the frame edge. That definition settles three things the pairs leave open. An outline missing a corner cell is open. A nested outline gets its own outer halo. Where one outline's inner halo and another's outer halo meet in one cell, `inner_color` wins.
- Fact about the evidence: every closed outline lies at least 3 cells (Chebyshev) from every other outline, no outline lies in another outline's hole, every cell of a closed outline is 8-adjacent to its hole, and every gap of a broken outline lies off its corners.

## Choice points
- `hole-walk`
    - `concept`: a hole is the cells that no walk from the frame edge reaches, stepping to any of the eight neighbors through cells outside the outline
    - `$Walk4`: replaces `some-closed-some-open` with the walk taking only the four cardinal steps, so a gap that leaves the hole meeting the outside only diagonally still closes it. Defined on every input. Fits every pair. Witness `missing-corner`: a square outline missing its corner cell. It breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `outline-connectivity`
    - `concept`: an outline is a 4-connected set of `wall_color` cells
    - `$Outline8`: replaces `outlines-on-background` with outlines as 8-connected sets, so pieces that touch at a corner are one outline. Defined on every input. Fits every pair. Witness `touching-piece`: an open bar touches a closed outline diagonally. It breaks `outlines-apart` and stands at the stored assignment. Plausibility `borderline`, verdict `$Outline8`. It breaks the invariant that every closed outline lies at least 3 cells from every other outline.
- `closure-scope`
    - `concept`: each outline alone closes off its own hole, and the inner and outer halos are drawn per outline
    - `$SharedWalls`: replaces `some-closed-some-open`, `outer-halo` and `inner-halo` with these rules. The holes are the regions that all `wall_color` cells together close off. A closed outline is an outline 4-adjacent to a hole. Each hole cell 8-adjacent to a `wall_color` cell takes `inner_color`. Each non-hole `background` cell 8-adjacent to a closed outline takes `outer_color`. Defined on every input. Fits every pair. Witness `nested-outline`: a closed outline sits 3 cells inside a bigger one's hole. It breaks no scene claim and stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant that no outline lies in another outline's hole.
- `halo-meeting`
    - `concept`: a cell in one outline's inner halo and another outline's outer halo takes `inner_color`
    - `$OuterOverInner`: replaces `inner-halo` so that such a cell takes `outer_color`. Defined on every input. Fits every pair. Witness `close-nested`: a closed outline sits 2 cells inside a bigger one's hole, so the line between them is in both halos. It breaks `outlines-apart` and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the invariants that no outline lies in another outline's hole and that closed outlines lie at least 3 cells from other outlines.
- `halo-extent`
    - `concept`: the outer halo runs around every cell of a closed outline
    - `$HoleRim`: replaces `outer-halo` so that the halo runs only around the outline cells that are 8-adjacent to its hole. Defined on every input. Fits every pair. Witness `spur`: a closed outline with a 2-cell spur sticking out. It breaks `outlines-on-background`, because the figure is an outline with a spur, and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the invariant that every cell of a closed outline is 8-adjacent to its hole.
- `outer-halo-adjacency`
    - `concept`: the outer halo is the cells 8-adjacent to the outline
    - `$OuterCardinal`: replaces `outer-halo` with 4-adjacency. Fails Fit at train0: (0,0), (6,0) and (6,6) touch the outline only diagonally and are `2`.
- `inner-halo-adjacency`
    - `concept`: the inner halo is the hole cells 8-adjacent to the outline
    - `$InnerCardinal`: replaces `inner-halo` with 4-adjacency. Fails Fit at train2: (4,8) and (3,7) touch the outline only diagonally and are `3`.
- `hole-paint`
    - `concept`: only the hole cells that touch the outline take `inner_color`
    - `$FillHole`: replaces `inner-halo` and `rest-unchanged` so that the whole hole takes `inner_color`. Fails Fit at train0: (3,3) stays `0`.
- `closed-shape-kind`
    - `concept`: any closed outline gets the halo
    - `$RectOnly`: adds the condition that a closed outline's cells are exactly the border of its bounding box. Fails Fit at train0: its outline is not a rectangle and gets the halo.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: replaces `outlines-on-background` so that `background` is derived as the commonest color of the input. Where several colors tie for commonest, the derivation gives each of them. Fits every pair. Witness `background=DominantColor`: a closed outline of 1 on a field of 4. It breaks `outlines-on-background` and stands at the stored assignment. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that every input's field is 0.
- `wall_color`
    - `concept`: stored, 1
    - `wall_color=RarestColor`: replaces `outlines-on-background` so that `wall_color` is derived as the rarest color of the input. Where several colors tie for rarest, the derivation gives each of them. Fits every pair. Witness `wall_color=RarestColor`: a closed outline of 5 on a field of 0. It breaks `outlines-on-background` and stands at the stored assignment. Plausibility `variant`, verdict `wall_color=RarestColor`. It breaks the invariant that every input's outlines are 1.
- `hole-walk` & `outline-connectivity`, `hole-walk` & `closure-scope`, `hole-walk` & `halo-meeting`, `hole-walk` & `halo-extent`, `hole-walk` & `outer-halo-adjacency`, `hole-walk` & `inner-halo-adjacency`, `hole-walk` & `hole-paint`, `hole-walk` & `closed-shape-kind`, `hole-walk` & `background`, `hole-walk` & `wall_color`, `outline-connectivity` & `closure-scope`, `outline-connectivity` & `halo-meeting`, `outline-connectivity` & `halo-extent`, `outline-connectivity` & `outer-halo-adjacency`, `outline-connectivity` & `inner-halo-adjacency`, `outline-connectivity` & `hole-paint`, `outline-connectivity` & `closed-shape-kind`, `outline-connectivity` & `background`, `outline-connectivity` & `wall_color`, `closure-scope` & `halo-extent`, `closure-scope` & `outer-halo-adjacency`, `closure-scope` & `inner-halo-adjacency`, `closure-scope` & `hole-paint`, `closure-scope` & `closed-shape-kind`, `closure-scope` & `background`, `closure-scope` & `wall_color`, `halo-meeting` & `halo-extent`, `halo-meeting` & `outer-halo-adjacency`, `halo-meeting` & `inner-halo-adjacency`, `halo-meeting` & `hole-paint`, `halo-meeting` & `closed-shape-kind`, `halo-meeting` & `background`, `halo-meeting` & `wall_color`, `halo-extent` & `outer-halo-adjacency`, `halo-extent` & `inner-halo-adjacency`, `halo-extent` & `hole-paint`, `halo-extent` & `closed-shape-kind`, `halo-extent` & `background`, `halo-extent` & `wall_color`, `outer-halo-adjacency` & `inner-halo-adjacency`, `outer-halo-adjacency` & `hole-paint`, `outer-halo-adjacency` & `closed-shape-kind`, `outer-halo-adjacency` & `background`, `outer-halo-adjacency` & `wall_color`, `inner-halo-adjacency` & `closed-shape-kind`, `inner-halo-adjacency` & `background`, `inner-halo-adjacency` & `wall_color`, `hole-paint` & `closed-shape-kind`, `hole-paint` & `background`, `hole-paint` & `wall_color`, `closed-shape-kind` & `background`, `closed-shape-kind` & `wall_color`, `background` & `wall_color`: the two branches' changes applied together
- `closure-scope` & `halo-meeting`: the model of `$SharedWalls` alone. Under shared walls, an outer halo covers only cells outside every hole, so no cell is in both halos and `halo-meeting` has no property to decide. Its property exists only with the concept branch of `closure-scope`, so it stands at the concept.
    - `$SharedWalls` & `$OuterOverInner`: the model of `$SharedWalls`
- `hole-paint` & `inner-halo-adjacency`: the model of `$FillHole` alone. When the whole hole takes `inner_color`, the adjacency of the inner halo decides nothing. Its property exists only with the concept branch of `hole-paint`, so it stands at the concept.
    - `$FillHole` & `$InnerCardinal`: the model of `$FillHole`

## Open parameters
none

## Not formed
- The frame edge counts as wall: with the frame as wall, the outside of every outline is closed off too. The reading needs a rule that picks which closed region is the outside, and no pair gives one.
- `outer_color` or `inner_color` derived by `OutNewColor` or `AnyOutNewColor`: these read train outputs, and a run on an input has `ex_out` empty. So the branch is undefined on every input and is no model of the task.
- `background` or `wall_color` derived by `SharedColor`: every input holds both 0 and 1, so the derivation gives both colors and fixes neither parameter.
- The inner halo as the 8-adjacency rim of the hole, and the outer halo as the cells 8-adjacent to the outline plus its hole: under the concept's 8-step walk, every cell 8-adjacent to a hole and outside it is a cell of the outline. So both readings give the concept's model (Equivalence).

## Tickets filed
- `10-754_task_d931c21c_analyze.md`
