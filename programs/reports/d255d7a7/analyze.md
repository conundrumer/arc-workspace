# d255d7a7

## Concept
- The concept fits every pair, train and test, and the probe `work/task/d255d7a7/probe.py` gives each pair's output.
- No witness has the verdict `other`. The rule as the generator applies it is the concept file's rule: each cup is drawn at the far end of its handle, and the handle is not drawn.

## Choice points
- `carried`: what travels with the cup
    - `concept`: the cells inside the bracket travel with it
        - `contents-reach`: which cells count as inside
            - `concept`: the cells of the bracket's box
            - `$EdgeSlab`: replaces `slide-to-handle-end`; the slab from the grid edge at the cup's open side to its closed side, across the cup's width, travels; defined wherever the concept is. Fits every pair. Witness `inset-cup`: breaks `cup`; stored assignment; `borderline`, verdict `concept`; breaks the invariant that every cup's open side lies on the grid edge.
        - `contents-order`: the order of the contents along the handle axis
            - `concept`: kept
            - `$MirrorContents`: replaces `slide-to-handle-end`; the contents land reversed along the handle axis inside the cup. Fails Fit at train0, train1 and train2.
    - `$BracketOnly`: replaces `slide-to-handle-end`; the bracket moves and the cells inside it stay. Fails Fit at train0.
- `pose`: the cup's orientation after it moves
    - `concept`: translated
    - `$Reflect`: replaces `slide-to-handle-end`; the cup and its contents are reflected across the line through the middle of the handle, so the cup opens the other way. Fails Fit at train0.
- `landing`: where the cup stops
    - `concept`: its closed side on the handle's last cell
    - `$EdgeLanding`: replaces `slide-to-handle-end`; the cup stops with its closed side on the grid edge the handle points to; defined wherever the concept is. Fits every pair. Witness `short-handle`: breaks `handle`; stored assignment; `variant`, verdict `concept`; breaks the invariant that every handle reaches the grid edge opposite its cup.
- `handle-fate`: what becomes of the handle
    - `concept`: cleared to `background`
    - `$KeepHandle`: replaces `clear-vacated`; the handle cells keep `frame`. Fails Fit at train0.
- `heading`: where the slide direction comes from
    - `concept`: each cup's own handle
    - `$SharedHeading`: adds one heading per input, read from the cups; undefined on an input whose cups open toward different edges. Fits every pair. Witness `split-heading`: breaks `same-facing`; stored assignment; `variant`, verdict `concept`; breaks the invariant that all cups of an input open toward one edge. The branch is undefined there, and no witness where it is defined exists, because where it is defined its output is the concept's.
- `overlap`: what shows where a landed cup covers a cell that keeps its color
    - `concept`: the cup
    - `$MarksOnTop`: replaces `keep-rest`; a kept cell other than `background` shows over the landed cup. Fits every pair. Witness `mark-in-landing`: breaks no scene claim; stored assignment; `variant`, verdict `concept`; breaks the invariant that every loose mark lies off the lines a cup spans.
- `cup-extent`: how far a cup reaches along its handle
    - `concept`: derived from the frame component: the lines from the open end that span the cup's width
    - `cup_width=stored`: replaces `cup`; stores `cup-width` 3, takes that many lines at the open end of a frame component as the cup and the rest as handle; undefined where a cup is not `cup-width` across. Fits every pair. Witness `cup_width=stored`: breaks `cup`; stored assignment; `variant`, verdict `concept`; breaks the invariant that every cup is 3 × 3.
- `background`: the clearing color
    - `concept`: stored 7
    - `background=DominantColor`: the commonest color of the input alone; undefined where two colors tie. Fits every pair. Witness `background=DominantColor`: breaks no scene claim; stored assignment; `variant`, verdict `concept`; breaks the invariant that 7 is the commonest color of every input.
    - `background=RarestColor`: gives 9. Fails Fit at train0.
    - `background=SharedColor`: gives 0, 7 and 9. Fails Fit at train0.
    - `background=ChangedColor`, `background=UnchangedColor`, `background=OutNewColor`, `background=AnyOutNewColor`, `background=VanishedColor`: read `ex_out`, which is empty on an input alone, so they give no value and are undefined on every input. Fail Fit at train0.
- `frame`: the color of the cups and the handles
    - `concept`: stored 0
    - `frame=RarestColor`: gives 9. Fails Fit at train0.
    - `frame=DominantColor`: gives 7. Fails Fit at train0.
    - `frame=SharedColor`: gives 0, 7 and 9. Fails Fit at train0.
    - `frame=ChangedColor`, `frame=UnchangedColor`, `frame=OutNewColor`, `frame=AnyOutNewColor`, `frame=VanishedColor`: give no value on an input alone. Fail Fit at train0.
- each two of `carried`, `contents-reach`, `contents-order`, `pose`, `landing`, `handle-fate`, `heading`, `overlap`, `cup-extent`, `background`, `frame`, other than `carried` with `contents-reach` or `contents-order`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored slide direction: train0 slides right, train1 up, train2 left and the test down, so no one stored value exists, and the per-cup heading is already the concept.
- A handle placed off the middle of the closed side: the cup is found from the frame component in every branch, so no model reads where the handle meets the cup.

## Tickets filed
- none
