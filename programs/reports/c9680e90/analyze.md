# c9680e90

## Concept
- The concept fits every pair: `work/task/c9680e90/probe.py` reproduces train0–train2 and test0. No witness has the verdict `other`.
- The concept loses two witnesses. On `bent-tail` (`foreign`), `$PathTail` is the verdict. On `recolored-divider` (`variant`), `$DividerDerived` is the verdict.
- Undefined where the input has no full line of `divider-color` on `divider-axis`, or more than one, and where two moves paint different colors on one cell or move a mark off the grid.

## Choice points
- `tail-extent`: which cells the head crawls along
    - `concept`: the straight run of `tail-color` cells that starts at a 4-neighbor of the head
    - `$PathTail`: replaces `straight-tail` and `crawl-to-tail-end`. The tail is the 4-connected component of `tail-color` cells that touches the head. The head moves to the component cell that is farthest from it along the component, and the whole component becomes `background`. It has the concept's parameters and is undefined where the concept is. It fits every pair. Witness `bent-tail` breaks `straight-tail`; plausibility `foreign`; verdict `$PathTail`. The invariant it breaks: every tail is one straight run.
        - `tail-adjacency`: how tail cells connect into the component
            - `concept`: 4-adjacency
            - `$Tail8`: 8-adjacency, and the component touches an 8-neighbor of the head. It fails Fit at train2: the component {(7,2), (8,1)} takes head (6,2) to (8,1).
    - `$LineTail`: replaces `straight-tail` and `crawl-to-tail-end`. Every `tail-color` cell in line with the head in a direction counts, with gaps allowed. The head moves to the farthest one, and all of them become `background`. It fails Fit at train0: head (6,8) jumps to (6,5).
    - `$Dir8Tail`: replaces `straight-tail`. Runs start along the four diagonals as well (Dir8 in place of Dir), and a head with runs in several directions is drawn at the end of each run. It fits every pair. Witness `diagonal-tail-cell` breaks no scene claim; plausibility `ordinary`; verdict `concept`.
- `twin-match`: which mark moves with a head
    - `concept`: the mark at the mirror image of the head's cell across the divider
    - `$ColumnTwin`: replaces `twin-follows`. Every mark in a head's column moves to the mirror image of that head's new cell. It fits every pair. Witness `column-lonely-mark` breaks `mirror-twins`; plausibility `foreign`; verdict `concept`. The invariant it breaks: the marks are exactly the mirror images of the heads.
        - `mark-destination`: where a moving mark goes
            - `concept`: the mirror image of its head's new cell
            - `$ReflectedStep`: the mark's own cell, moved by its head's step reflected across the divider. It fails Fit at test0: column 7 has two heads, so marks (0,7) and (2,7) each take both steps and draw four marks.
    - `$MirrorRedraw`: replaces `twin-follows`. Every mark becomes `background`, and a mark is drawn at the mirror image of each head's new cell. It fits every pair. Witness `lonely-mark` breaks `mirror-twins`; plausibility `foreign`; verdict `concept`. The invariant it breaks: the marks are exactly the mirror images of the heads.
- `mirror-line`: the line the twins mirror across
    - `concept`: the divider line
    - `$CenterMirror`: replaces the mirror in `twin-follows` with the mirror across the grid's center line on `divider-axis`. It reads no divider and no `divider-color`, and it is defined where no divider line exists. It fits every pair. Witness `off-center-divider` breaks `center-divider`; plausibility `foreign`; verdict `concept`. The invariant it breaks: the divider is the center line of the grid.
- `divider-location`: how the program finds the divider
    - `concept`: the one full line of the stored `divider-color` on the stored `divider-axis`
    - `$DividerDerived`: derives the divider as the one full line of a single color other than `background`, on either axis, in place of the stored `divider-color` and `divider-axis`. It fits every pair. Witness `recolored-divider` breaks `center-divider`, because no line of `divider-color` exists; plausibility `variant`; verdict `$DividerDerived`.
- `background`
    - `concept`: stored, 7
    - `background=DominantColor`: the commonest color of the input. The branch is undefined on a tie. It fits every pair. Witness `background=DominantColor` breaks no scene claim; plausibility `foreign`; verdict `concept`. The invariant it breaks: each half has at least 3 rows, so `background` is the commonest color of each input.
    - `background=CountRankDesc`: the color at rank 0, which is the same derivation as `background=DominantColor`. It fails Equivalence with `background=DominantColor`. It fits every pair. Witness `background=CountRankDesc` is the same input, with the same plausibility and verdict.
    - `background=SharedColor`: every color of the input. It fails Fit at train0.
- `divider-color`
    - `concept`: stored, 9
    - `divider-color=CountRankDesc`: the color at rank 1. It fits every pair. Witness `divider-color=CountRankDesc` (12 tail cells against 11 divider cells) breaks no scene claim; plausibility `ordinary`; verdict `concept`. The branch is undefined on that witness. No witness exists on which the branch is defined and differs from the concept:
        - Only the divider color, a `background` line, or a tail line could form a full line.
        - A tail line cannot fill a row, because the row also holds the tail's head.
        - `background` is at rank 1 only when the halves are one row high, and there the row of a half holds a head or its twin.
    - `divider-color=UnchangedColor`: reads `ex_out`, so on one input it gives no color. It fails Fit at train0.
    - `divider-color=SharedColor`: every color of the input. It fails Fit at train0.
- `tail-color`
    - `concept`: stored, 6
    - `tail-color=VanishedColor`: with `ex_out` empty, every color of the input. It fails Fit at train0.
    - `tail-color=ChangedColor`: reads `ex_out`, so it gives no color. It fails Fit at train0.
    - `tail-color=SharedColor`: every color of the input. It fails Fit at train0.
- `head-color`
    - `concept`: stored, 2
    - `head-color=RarestColor`: {2, 5}, and in train1 {2, 5, 6}. It fails Fit at train0.
    - `head-color=CountRankAsc`: the colors at rank 0, the same sets. It fails Fit at train0.
    - `head-color=ChangedColor`: no color. It fails Fit at train0.
    - `head-color=SharedColor`: every color of the input. It fails Fit at train0.
- `mark-color`
    - `concept`: stored, 5
    - `mark-color=RarestColor`: {2, 5}, and in train1 {2, 5, 6}. It fails Fit at train0.
    - `mark-color=CountRankAsc`: the same sets. It fails Fit at train0.
    - `mark-color=ChangedColor`: no color. It fails Fit at train0.
    - `mark-color=SharedColor`: every color of the input. It fails Fit at train0.
- `tail-extent` & `twin-match`, `tail-extent` & `mark-destination`, `tail-extent` & `mirror-line`, `tail-extent` & `divider-location`, `tail-extent` & `background`, `tail-extent` & `divider-color`, `tail-extent` & `tail-color`, `tail-extent` & `head-color`, `tail-extent` & `mark-color`, `tail-adjacency` & `twin-match`, `tail-adjacency` & `mark-destination`, `tail-adjacency` & `mirror-line`, `tail-adjacency` & `divider-location`, `tail-adjacency` & `background`, `tail-adjacency` & `divider-color`, `tail-adjacency` & `tail-color`, `tail-adjacency` & `head-color`, `tail-adjacency` & `mark-color`, `twin-match` & `mirror-line`, `twin-match` & `divider-location`, `twin-match` & `background`, `twin-match` & `divider-color`, `twin-match` & `tail-color`, `twin-match` & `head-color`, `twin-match` & `mark-color`, `mark-destination` & `mirror-line`, `mark-destination` & `divider-location`, `mark-destination` & `background`, `mark-destination` & `divider-color`, `mark-destination` & `tail-color`, `mark-destination` & `head-color`, `mark-destination` & `mark-color`, `mirror-line` & `background`, `mirror-line` & `tail-color`, `mirror-line` & `head-color`, `mirror-line` & `mark-color`, `divider-location` & `background`, `divider-location` & `tail-color`, `divider-location` & `head-color`, `divider-location` & `mark-color`, `background` & `divider-color`, `background` & `tail-color`, `background` & `head-color`, `background` & `mark-color`, `divider-color` & `tail-color`, `divider-color` & `head-color`, `divider-color` & `mark-color`, `tail-color` & `head-color`, `tail-color` & `mark-color`, `head-color` & `mark-color`: the two branches' changes applied together
- `mirror-line` & `divider-location`, `mirror-line` & `divider-color`: the model of `$CenterMirror` alone. `$CenterMirror` reads no divider, so the properties of `divider-location` and `divider-color` exist only with the concept branch of `mirror-line`. Both points stand at the concept.
- `divider-location` & `divider-color`: the model of `$DividerDerived` alone. `$DividerDerived` reads no `divider-color`, so the property of `divider-color` exists only with the concept branch of `divider-location`. The point stands at the concept.

## Open parameters
- none

## Not formed
- The head stops one cell past the tail's end, or one cell short of it: the pairs separate it. Train0 head (5,5) ends at (7,5), the last tail cell.
- The mark moves by its head's step without the reflection: the pairs separate it. Train0 mark (3,5) would land on the divider at (5,5), and the output has it at (1,5).
- The twins are a translation across the divider, not a mirror: the pairs separate it. Train0 head (5,5) has its twin at (3,5), and a translation by the half's height puts the twin at (0,5).
- `$ReflectedStep` under the concept branch of `twin-match`: there each mark is the mirror image of its head, so the reflected step lands on the mirror image of the head's new cell. That gives the concept's model.

## Tickets filed
- 10-568_task_c9680e90_analyze.md
- 10-569_task_c9680e90_analyze.md
