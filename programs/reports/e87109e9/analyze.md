# e87109e9

## Concept
- The concept fits every pair: train 0, train 1, train 2 and test 0.
- No witness has the verdict `other`. The rigid slide of the block is the rule as the generator applies it, and it has a relational form, so the concept file's rules approximate nothing.

## Choice points
- `legend edge source`
    - `concept`: `legend_edge` is stored, with the value top.
    - `$LegendEdgeDerived`: replaces the stored edge in `legend-strip` and `crop-scene` with a derivation: the edge whose outer line is all `legend_frame_color` and whose next line is not. Undefined on an input with no such edge. Fits every pair. Witness `legend-on-other-edge`, at the stored assignment: it breaks `legend-strip`, plausibility `variant`, verdict `$LegendEdgeDerived`. It breaks the invariant that the legend lies along the top edge.
- `legend frame color source`
    - `concept`: `legend_frame_color` is stored, with the value `5`.
    - `$LegendFrameColorDerived`: replaces the stored color in `legend-strip` with a derivation: the color of the outer line on `legend_edge`. Undefined where that line holds two colors. Fits every pair. Witness `frame-of-other-color`, at the stored assignment: it breaks `legend-strip`, plausibility `variant`, verdict `$LegendFrameColorDerived`. It breaks the invariant that the frame is `5`.
    - `legend_frame_color=SharedColor`, `legend_frame_color=VanishedColor`, `legend_frame_color=ChangedColor`: on one input with `ex_out` empty, each gives every color of that input, or none. Fails train 0.
    - `legend_frame_color=DominantColor`: gives `3` on train 0. Fails train 0.
    - `legend_frame_color=RarestColor`: gives `6` and `8` on train 0, 4 cells each. Fails train 0.
    - `legend_frame_color=OutNewColor`, `legend_frame_color=AnyOutNewColor`, `legend_frame_color=UnchangedColor`: on one input with `ex_out` empty, each gives no color of that input. Fails train 0.
- `legend blank color source`
    - `concept`: `legend_blank_color` is stored, with the value `0`.
    - `$LegendBlankColorDerived`: replaces the stored color in `legend-strip` with a derivation: the commonest color among the strip's cells that are not `legend_frame_color`. Fits every pair. Witness `blank-of-other-color`, at the stored assignment: it breaks `legend-strip`, plausibility `variant`, verdict `$LegendBlankColorDerived`. It breaks the invariant that the boxes are blank in `0`.
    - `legend_blank_color=SharedColor`, `legend_blank_color=VanishedColor`, `legend_blank_color=ChangedColor`: each gives every color of the input, or none. Fails train 0.
    - `legend_blank_color=DominantColor`: gives `3` on train 0. Fails train 0.
    - `legend_blank_color=RarestColor`: gives `6` and `8` on train 0. Fails train 0.
    - `legend_blank_color=OutNewColor`, `legend_blank_color=AnyOutNewColor`, `legend_blank_color=UnchangedColor`: each gives no color of the input. Fails train 0.
- `block color source`
    - `concept`: `block_color` is stored, with the value `8`.
        - `unlisted obstacle`: what a beam does at a cell of a color that no legend box holds.
            - `concept`: the beam stops before that cell.
            - `$PaintOverUnlistedColor`: changes `turn-at-rectangle`: such a cell is no obstacle, and the beam paints it. Fits every pair. Witness `unlisted-rectangle`, at the stored assignment: it breaks `rectangles`, plausibility `borderline`, verdict `concept`. It breaks the invariant that each scene rectangle has a legend color.
            - `$PassUnderUnlistedColor`: changes `turn-at-rectangle`: such a cell is no obstacle, and it keeps its color. Fits every pair. Witness `unlisted-rectangle`, as for `$PaintOverUnlistedColor`.
    - `$BlockColorDerived`: replaces the stored color in `block` and `paint-trace` with a derivation: the one scene color that is not the background and that no legend box holds. Undefined where the scene holds two or more such colors. Fits every pair. Witness `block-of-other-color`, at the stored assignment: it breaks `block`, plausibility `variant`, verdict `$BlockColorDerived`. It breaks the invariant that the block is `8`.
    - `block_color=SharedColor`, `block_color=VanishedColor`, `block_color=ChangedColor`: each gives every color of the input, or none. Fails train 0.
    - `block_color=DominantColor`: gives `3` on train 0. Fails train 0.
    - `block_color=RarestColor`: gives `6` and `8` on train 0, so the beams take two colors. Fails train 0.
    - `block_color=OutNewColor`, `block_color=AnyOutNewColor`, `block_color=UnchangedColor`: each gives no color of the input. Fails train 0.
- `background source`
    - `concept`: the background is derived on each input as the commonest color of the scene.
    - `$BackgroundStored`: replaces that derivation in `field` with a stored color. Fails train 1: its background is `1`, and train 0's background is `3`.
    - `$BackgroundWholeInputMode`: replaces that derivation in `field` with the commonest color of the whole input, legend included. Fits every pair. Witness `small-scene`, at the stored assignment: it breaks `rectangles`, plausibility `borderline`, verdict `concept`. It breaks the invariants that the scene has at least 19 rows and that it holds rectangles.
- `beam directions`
    - `concept`: the program enumerates every cardinal direction.
    - `$BeamDirectionsStored`: replaces `beam-each-way` with a stored set `beam_dirs`, with the value top, bottom, left and right. Fits every pair. Witness `three-beams`, at the assignment `beam_dirs` = top, bottom and left: it breaks no scene claim, plausibility `ordinary`, verdict `concept`.
- `slide`
    - `concept`: the block slides as one rigid square.
    - `$PerCellSlide`: replaces `beam-each-way` and `turn-at-rectangle`: each block cell slides on its own, as the lib's `Slide` gives per node, and turns where it stops. Fails train 0: both block columns of the right beam stop at col 17, so the beam that turns up is 1 cell wide, and the output's is cols 16–17.
- `turn reading`
    - `concept`: the marker's side gives a turn sense relative to the beam's heading.
    - `$MarkerAbsoluteSide`: replaces `turn-at-rectangle`: the beam turns toward the grid side that the marker's side names. Undefined where the beam moves along the axis of that side. Fails train 0: the left beam meets `1` while it moves left.
- `beam crossing`
    - `concept`: beams cross each other freely.
    - `$StopAtBeam`: replaces `paint-trace`: a beam stops before a cell that another beam covers. Fails train 2: both beams that cross at output rows 4–5, cols 3–4 run on past it, to col 0 and to row 0.
- `blocked after a turn`
    - `concept`: a beam whose first step after a turn is blocked turns again, by the sense of what blocks it.
    - `$StopWhenTurnBlocked`: changes `turn-at-rectangle`: that beam ends there. Fits every pair. Witness `turn-into-rectangle`, at the stored assignment: it breaks `rectangles` and `square-hits`, plausibility `borderline`, verdict `concept`. It breaks the invariants that no two rectangles touch and that each turn has a free step after it.
- `block color source` & `unlisted obstacle`: under `$BlockColorDerived`, a scene with a rectangle of a color no legend box holds has two candidate block colors. The model is undefined there, so `unlisted obstacle` exists only under the concept branch of `block color source`.
- `legend edge source` & `legend blank color source`, `legend edge source` & `block color source`, `legend edge source` & `background source`, `legend edge source` & `beam directions`, `legend edge source` & `slide`, `legend edge source` & `turn reading`, `legend edge source` & `beam crossing`, `legend edge source` & `blocked after a turn`, `legend frame color source` & `legend blank color source`, `legend frame color source` & `block color source`, `legend frame color source` & `background source`, `legend frame color source` & `beam directions`, `legend frame color source` & `slide`, `legend frame color source` & `turn reading`, `legend frame color source` & `beam crossing`, `legend frame color source` & `blocked after a turn`, `legend blank color source` & `block color source`, `legend blank color source` & `background source`, `legend blank color source` & `beam directions`, `legend blank color source` & `slide`, `legend blank color source` & `turn reading`, `legend blank color source` & `beam crossing`, `legend blank color source` & `blocked after a turn`, `block color source` & `background source`, `block color source` & `beam directions`, `block color source` & `slide`, `block color source` & `turn reading`, `block color source` & `beam crossing`, `block color source` & `blocked after a turn`, `background source` & `beam directions`, `background source` & `slide`, `background source` & `turn reading`, `background source` & `beam crossing`, `background source` & `blocked after a turn`, `beam directions` & `slide`, `beam directions` & `turn reading`, `beam directions` & `beam crossing`, `beam directions` & `blocked after a turn`, `slide` & `turn reading`, `slide` & `beam crossing`, `slide` & `blocked after a turn`, `turn reading` & `beam crossing`, `turn reading` & `blocked after a turn`, `beam crossing` & `blocked after a turn`, `legend edge source` & `unlisted obstacle`, `legend frame color source` & `unlisted obstacle`, `legend blank color source` & `unlisted obstacle`, `background source` & `unlisted obstacle`, `beam directions` & `unlisted obstacle`, `slide` & `unlisted obstacle`, `turn reading` & `unlisted obstacle`, `beam crossing` & `unlisted obstacle`, `blocked after a turn` & `unlisted obstacle`: the two branches' changes applied together
- `legend edge source` & `legend frame color source`: the edge is derived from the frame color that the frame branch gives.
    - `$LegendEdgeDerived` & `$LegendFrameColorDerived`: the edge and the frame color are found together: the edge whose outer line is all one color c and whose next line is not all c, with c as the frame color.

## Open parameters
- none

## Not formed
- A stored relation from the marker's side to the turn sense: no element of ARC's symmetry group changes that relation, so no variant task stores another value of it. The opposite relation fails every pair.
- An output that keeps the legend strip: every pair's output has the scene's size.
- A beam whose next step meets a rectangle with only part of its width: no pair, solver header, lib component or proposer gives a reading other than the rigid slide's turn, except the per-cell slide of `$PerCellSlide`, which is formed.
- `legend_box_count` and `legend_box_extent` as parameters the program reads: the program finds the boxes as the runs between frame lines, and it reads neither value.

## Tickets filed
- none
