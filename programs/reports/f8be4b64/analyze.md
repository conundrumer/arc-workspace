# f8be4b64

## Concept
- The concept fits every train and test pair (`work/task/f8be4b64/check_concept.py`, and `probe.py fit`). Each plus casts its center color along its row and its column. A hollow plus casts `background`. A beam passes over its own arms, stops before the first `ring_color` cell past them, and leaves every `ring_color` cell as it is. Where two beams cross, the `top_axis` (V) beam shows.
- The model is undefined where two beams along one axis cover one cell in different colors. That takes two centers on one line, which `distinct-lines` rules out, and no pair shows it.
- No witness has verdict `other`. Every rule has a relational form (rays from a center that stop at a cell set, plus a layer order by axis), so nothing is approximated.
- Parameters: `ring_color` = 3 and `top_axis` = V, both stored. `background` = 0 is a scene parameter that the program does not read, because a hollow center's color is read from the cell.

## Choice points
- `same-axis-overlap`: the color of a cell that two beams along one axis cover
    - `concept`: undefined
    - `$NearerBeamShows`: adds a rule: the beam from the nearer center shows. Reads `ring_color` and `top_axis`. Undefined where two such centers are equally near and differ in color. Fits every pair. Witness `same-row-lamps` breaks `distinct-lines`. Plausibility `borderline` (in all 5 inputs no two centers share a row or column). Verdict `NearerBeamShows`.
- `hollow-beam-axes`: where a hollow plus casts
    - `concept`: `background`, along both axes, layered like any beam
    - `$HollowTopAxisOnly`: replaces `cast-cross` for a hollow plus: it casts `background` along `top_axis` only. Reads `ring_color` and `top_axis`. Undefined where two filled beams along one axis overlap. Fits every pair. Witness `hollow-same-row` breaks `distinct-lines`. Plausibility `borderline` (the same invariant). Verdict `NearerBeamShows`.
    - `$HollowSilent`: replaces `cast-cross`: a hollow plus casts nothing. Fails train0: at (3,13) it gives 2 where the output has 0 (it also fails train2, train3 and test0).
    - `$HollowErasesOnTop`: replaces `cast-cross` and `column-on-top`: a hollow plus clears its row and column on top of every beam. Fails train0: at (18,5) it gives 0 where the output has 2.
- `hollow-ring-blocks`: whether a hollow plus's arms stop a beam
    - `concept`: they do, like any `ring_color` cell
    - `$HollowRingsPassable`: replaces `blocked-at-ring`: a beam passes a hollow plus's arms, keeps them, and goes on. Fits every pair. Witness `hollow-ring-in-path` breaks no scene claim. Plausibility `ordinary`. Verdict `concept`.
- `background-beam-blocked`: whether a hollow plus's beam stops at another plus's arm
    - `concept`: it does
    - `$BackgroundBeamUnblocked`: replaces `blocked-at-ring` for a hollow plus's beams: they pass every `ring_color` cell and go on. Fits every pair. Witness `background-beam-blocked` breaks no scene claim. Plausibility `ordinary`. Verdict `concept`.
- `blocker`: what stops a beam
    - `concept`: the first `ring_color` cell past the beam's own arms
    - `$StopAtPlusRing`: replaces `blocked-at-ring`: only an arm of another plus stops a beam, and a lone `ring_color` cell is passed and kept. Fits every pair. Witness `stray-ring-cell` breaks `background`. Plausibility `foreign` (in every input, every non-background cell belongs to a plus). Verdict `concept`.
    - `$StopAtAnyMark`: replaces `blocked-at-ring`: the first non-background cell past the beam's own arms stops it and is kept. Fits every pair. Witness `stray-mark` breaks `background`. Plausibility `foreign` (the same invariant). Verdict `StopAtAnyMark`.
    - `$BeamPassesRings`: replaces `blocked-at-ring`: no cell stops a beam. Fails train1: at (3,0) and (3,1) it gives 6 where the output has 0.
    - `$BlockedAtBox`: replaces `blocked-at-ring`: a beam stops at another plus's 3×3 box. Fails train1: at (3,3) it gives 0 where the output has 6.
    - `$StopAtBeam`: adds a rule: a beam stops where it meets a crossing beam. Fails train0: row 21 crosses the column-20 beam, and at (21,14)–(21,19) it gives 0 where the output has 8.
- `rings-kept`: whether a beam paints its own plus's arms
    - `concept`: it leaves them as they are
    - `$BeamCoversOwnArms`: replaces `rings-kept` for a plus's own arms: its beams paint them. Fails train1: at (2,8) it gives 6 where the output has 3.
- `crossing-layer`: which beam shows where two beams cross
    - `concept`: the beam along the stored `top_axis`
    - `$TopByColorOrder`: replaces `column-on-top` with a stored color order. Fails train0: (3,22) needs 8 over 2, and (21,5) needs 2 over 8.
    - `$TopByScanOrder`: replaces `column-on-top`: the beam of the later plus in row-major order shows. Fails train0: at (21,5) it gives 8 where the output has 2.
- `ring-color-source`: where `ring_color` comes from
    - `concept`: stored, 3
    - `ring_color=SharedColor`: on one input it gives every color of that input, so every cell is a kept ring cell and the output is the input. Fails train0.
    - `ring_color=DominantColor`: gives `background`, so no plus is found and the output is the input. Fails train0.
    - `ring_color=RarestColor`: gives the center colors, so no plus is found and the output is the input. Fails train0.
    - `ring_color=OutNewColor`, `ring_color=AnyOutNewColor`, `ring_color=VanishedColor`, `ring_color=ChangedColor`, `ring_color=UnchangedColor`: they read train outputs, so on one input under `@derive` they give no value and the model is undefined on every input. Fails train0.
- `same-axis-overlap` & `hollow-beam-axes`, `same-axis-overlap` & `hollow-ring-blocks`, `same-axis-overlap` & `background-beam-blocked`, `same-axis-overlap` & `blocker`, `hollow-beam-axes` & `hollow-ring-blocks`, `hollow-beam-axes` & `background-beam-blocked`, `hollow-beam-axes` & `blocker`, `hollow-ring-blocks` & `background-beam-blocked`, `hollow-ring-blocks` & `blocker`, `background-beam-blocked` & `blocker`: the two branches' changes applied together. For example, `$HollowRingsPassable` & `$StopAtAnyMark` stops a beam at the first non-background cell that is not a hollow plus's arm. `crossing-layer` and `ring-color-source` have no non-concept case, so no case takes non-concept branches at two points.

## Open parameters
- none

## Not formed
- `top_axis` derived: no proposer proposes an Axis on its own, and the pairs fix the stored value V, since every crossing shows the column beam.
- `background` stored or derived: the program never reads it, because a hollow center casts the color its cell holds.
- `distinct-centers` as a rule: no rule reads whether center colors differ. On an input with two centers of one color, every case gives one output.

## Tickets filed
- none
