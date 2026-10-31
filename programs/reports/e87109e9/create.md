# e87109e9

## Departures
- The witness file has one more witness than `witnesses.json`, `legend-colored-field`: `witness` reported that no run showed `$BackgroundWholeInputMode` defined and differing from `$BackgroundSceneMode` among the cases that take `$BlockColorDerived`. On this witness the scene background 3 is a legend marker color and one frame-color 5 cell stands in the scene. Under `$BlockColorDerived`, the whole-input background leaves 8 as the only candidate, and the scene background leaves 5 and 8 and is undefined. My judgment: plausibility `foreign`, because the generator never makes the field a legend color. Verdict `concept`, because the concept case and `$BlockColorDerived & $BackgroundWholeInputMode` both give the scene unchanged. No `@witness` line records it, because it pins a combination case and is no branch's witness.
- The concept case is undefined where the legend has no frame line, and where a box holds a non-blank cell that is not on a side perpendicular to the legend edge (`malformed`). With these two guards, the concept gives `null` on `frame-of-other-color` and `blank-of-other-color`, as `witnesses.json` gives. They are how the `legend-strip` claim makes the model undefined, and the runs show no other difference.

## Judgments
- Every branch that `analyze.md` gives a witness is a constructor, including the four derivations of `legend_edge`, `legend_frame_color`, `legend_blank_color` and `block_color`: each one is a derivation of the solver's own, not a built-in proposer. `derive` reports that no built-in derivation fits, and `store` prints no line to add.
- `unlisted obstacle` is a field of `$BlockColorStored`, as `analyze.md` nests it under the concept branch of `block color source`. `$LegendEdgeDerived & $LegendFrameColorDerived` finds the edge and the frame color together through `framed_edge`, as `analyze.md` gives for that pair.
- The walk is a `Propagation` over beams `[box, heading]`, which follows precedent d9f24cd1. A step goes to the next translate of the block where that translate covers no obstacle and stays in the scene. A hit turns the heading by the sense of the obstacle's color. `cover` lists each translate of the block by the scene cells it covers. That one relation gives the candidate boxes, the hit test and the painted cells.
- All 256 combinations of the branches are in `impl_choice`, and the runner keeps 11 witnessed cases. The pairs run takes 2–19 s, so there is no performance problem.
- `determination-plan` asked for determination relations for `block_color`, `legend_blank_color`, `legend_edge` and `legend_frame_color`. The frame and blank colors are the colors that every train output drops: the frame color is the one that has cells on the border, and the blank color is the one that has none. The legend edge is the edge whose outer line holds one color in every train input. The block color is the color that every output adds, under the alignment to each corner. A hint said the first form of `legend_edge` read inputs and outputs together. I rewrote it to read inputs alone. `beam_dirs` is left to the fit set, because no clause reads it from the evidence.
- Hints: the `case section` hints came from shared clauses that stood under a case marker. I moved those clauses above the markers. I inlined `covered` (single-consumer) and `out_color` (negated-use). I removed the `common-subexpr` hint by adding `border_color`.
- `deletions` reports 28 deletions that change nothing. Each one is a guard that the pairs never use: `line_defect`, `malformed`, `inside(B, ZERO)`, `defined`, and the clauses of the non-concept branches. Witnesses use these guards, or they state the claim (`exit-at-edge`, `legend-strip`), so they stay. The `train(E)` atoms in Determine stay by the test-inputs rule.

## Unsettled
- `deletions` ran before the last edits to `Determine`: the `legend_edge` rewrite, `border_color`, and the inlining of `out_color`. The program clauses did not change after that run. Another `deletions` run would settle whether those Determine edits leave a deletion that changes nothing.
- The audit's `store` check did not check `bg_mode.item`, `cover`, `hit`, `in_strip`, `obstacle`, `place`, `scene`, `scene_box.cell`, `scene_in`, `trace`, `walk.edge` and `walk.reached`, because each has over 20000 rows on an input. This check is open.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
