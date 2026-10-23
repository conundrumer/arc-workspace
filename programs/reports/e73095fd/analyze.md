# e73095fd

## Concept
- The concept case fits every pair; `work/task/e73095fd/probe.py` gives each train output exactly and the test output.
- Its rule approximates the rule as the generator applies it: the inside of each box the generator drew turns `fill`. The concept finds a box as a `background` component that is a rectangle, whose ring of cells is `wire` where it lies on the grid, and whose ring corners on the grid are true corners (no `wire` past a corner on either axis).
- No witness has the verdict `other`.
- The verdicts of `band-between-lines` and `grid-corner-box` agree with `$CornerShown`, which leaves a band with no corner on the grid and fills a box with one. The concept fills both.

## Choice points
- `clip-extent`: how much of a box that the grid edge cuts must lie on the grid
    - `concept`: any part; the grid edge stands in for every side and corner off the grid (`clipped-box`)
    - `$CornerShown`: replaces `clipped-box`; a box shows at least one ring corner on the grid; no parameter; defined on every input; fits every pair; witness `band-between-lines`, breaks no scene claim, plausibility `borderline`, verdict `$CornerShown`; the invariant it breaks: every box in every input shows at least two corners, and so a whole side, on the grid
    - `$SideShown`: replaces `clipped-box`; a box shows at least two ring corners on the grid, and so one whole side; no parameter; defined on every input; fits every pair; witness `grid-corner-box`, breaks no scene claim, plausibility `borderline`, verdict `concept`; the invariant it breaks: a grid edge cuts each box on at most one side
    - `$WholeBoxOnly`: replaces `clipped-box`; a box lies whole on the grid, its inside touching no grid edge; no parameter; defined on every input; fails Fit at train0, where it leaves `train0 input (2,0)` and `rows 1–3, col 18`
- `corner-test`: what a box's ring corners on the grid must be
    - `concept`: every one is a true corner, where no line continues a side (`box-outline`)
    - `$SomeTrueCorner`: replaces `box-outline`; where ring corners show, at least one is a true corner, so a line may continue a side past a corner; no parameter; defined on every input; fits every pair; witness `side-continues-past-corner`, breaks `box-outline`, plausibility `borderline`, verdict `$SomeTrueCorner`; the invariant it breaks: in every input a line meets a box only part way along a side
    - `$NoCornerTest`: replaces `box-outline`; no test on the ring corners; no parameter; defined on every input; fails Fit at train0, where it fills `train0 input rows 0–1, cols 14–16`
- `inside-content`: what a box's inside may hold
    - `concept`: only `background`, so the inside is one `background` component (`box-outline`)
    - `$OutlineBox`: replaces `box-outline`; a box is the rectangle its `wire` ring bounds, its inside may be crossed by `wire` lines that run straight from side to side, and every `background` cell inside turns `fill`; no parameter; defined on every input; fits every pair; witness `line-through-box`, breaks `box-outline`, plausibility `borderline`, verdict `$OutlineBox`; the invariant it breaks: no line enters a box's inside in any input
- `linked`: which boxes fill
    - `concept`: every box (`fill-box-inside`)
    - `$LinkedBox`: replaces `fill-box-inside`; only a box that some line meets fills; no parameter; defined on every input; fits every pair; witness `box-with-no-line`, breaks no scene claim, plausibility `variant`, verdict `concept`; the invariant it breaks: a line meets every box in every input
- `background`: the background color
    - `concept`: stored, 0
    - `background=DominantColor`: replaces the stored `background` in `wire-network` by the commonest color of the input; defined on every input, and a tie gives each tied color; fits every pair; witness `background=DominantColor`, breaks no scene claim, plausibility `borderline`, verdict `concept`; the invariant it breaks: `background` is the commonest color of every input
    - `background=SharedColor`: gives both 0 and 5 on every input; fails Fit at train0, where it gives more than one output
    - `background=RarestColor`: gives 5 on every input; fails Fit at train0, where no box is found and the input stays
- `wire`: the color of lines and box outlines
    - `concept`: stored, 5
    - `wire=RarestColor`: replaces the stored `wire` in `wire-network` by the rarest color of the input; defined on every input, and a tie gives each tied color; fits every pair; witness `wire=RarestColor`, breaks no scene claim, plausibility `borderline`, verdict `concept`; the invariant it breaks: `wire` is the rarest color of every input
    - `wire=SharedColor`: gives both 0 and 5 on every input; fails Fit at train0, where it gives more than one output
    - `wire=DominantColor`: gives 0 on every input; fails Fit at train0, where no ring is `wire` and the input stays
- `fill`: the color a box's inside takes
    - `concept`: stored, 4
    - `fill=OutNewColor`: replaces the stored `fill` in `fill-box-inside` by a color in every train output and no input; the derivation runs on each input with `ex_out` empty and gives no color, so the branch is undefined on every input; fails Fit at train0
    - `fill=AnyOutNewColor`: replaces the stored `fill` by a color in some train output and no input; undefined on every input for the same reason; fails Fit at train0
- `clip-extent` & `corner-test`, `clip-extent` & `inside-content`, `clip-extent` & `linked`, `clip-extent` & `background`, `clip-extent` & `wire`, `clip-extent` & `fill`, `corner-test` & `inside-content`, `corner-test` & `linked`, `corner-test` & `background`, `corner-test` & `wire`, `corner-test` & `fill`, `inside-content` & `linked`, `inside-content` & `background`, `inside-content` & `wire`, `inside-content` & `fill`, `linked` & `background`, `linked` & `wire`, `linked` & `fill`, `background` & `wire`, `background` & `fill`, `wire` & `fill`: the two branches' changes applied together

## Open parameters
none

## Not formed
- the inside of a box as a `background` region closed off from the grid edge (`Closed`): it leaves the boxes that the grid edge cuts, as `$WholeBoxOnly` does, and fails Fit at train0 for the same cells
- boxes as complete rectangle outlines (`Outlines`): it finds no box that the grid edge cuts, and fails Fit at train0 as `$WholeBoxOnly` does
- a true corner as a ring corner with exactly two `wire` neighbours, which form an L: on the grid it is the same test as the concept's, so its model is the concept's
- `background`, `wire` or `fill` derived by `VanishedColor`, `ChangedColor` or `UnchangedColor`: each reads `ex_out`, which a run on an input leaves empty, so each gives no value and is undefined on every pair, as `fill=OutNewColor` is; `ChangedPairs` and `VanishedNewPairs` read train outputs in the same way
- the size, dimension and tile proposers: the task has no parameter of those types

## Tickets filed
none
