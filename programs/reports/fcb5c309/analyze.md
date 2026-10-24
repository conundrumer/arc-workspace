# fcb5c309

## Concept
- Fits every pair (train0–2, test0); checked by `work/task/fcb5c309/check_concept.py` and `work/task/fcb5c309/probe.py`.
- No witness has verdict `other`. The rule as the generator applies it is the concept file's rule itself: count the dot cells strictly inside each frame, take the frame with the most, crop it border included, and paint the border in the dot color. Each step has a relational form (components, inside test, count, max), so nothing is approximated.
- In every pair the frame with the most dots is also the largest frame by every size measure, and no frame holds two touching dots. So the pairs do not separate `select-most-dots` from size-based selection or from counting clusters. Witnesses `largest-frame`, `border-cell-count`, `interior-area`, `dot-cluster` and `diagonal-cluster` separate them, each `ordinary` with verdict `concept`.
- No interpretation runs into trouble with any train pair.

## Choice points
- `selection`: what picks the frame that is cropped
    - `concept`: the frame with the most dot cells strictly inside its border (`select-most-dots`)
    - `$SelectLargest`: replaces `select-most-dots` with the frame of largest size; no parameters; undefined where two frames tie for the largest. Fits every pair. Witness `largest-frame`: a 7x7 frame holding 1 dot beside a 5x5 frame holding 3. Breaks no scene claim, stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
        - `size-measure`: how a frame's size is measured
            - `concept`: bounding-box area
            - `$SizeByBorderCells`: replaces the measure with the frame's count of border cells; no parameters; undefined where two frames tie. Fits every pair. Witness `border-cell-count`: 6x6 (area 36, 20 border cells, 1 dot) beside 3x11 (area 33, 24 border cells, 3 dots). Breaks no scene claim, stands at the stored assignment. Plausibility `ordinary`, verdict `concept` (the concept's output matches this branch's here).
            - `$SizeByInterior`: replaces the measure with the interior area; no parameters; undefined where two frames tie. Fits every pair. Witness `interior-area`: 6x6 (area 36, interior 16, 3 dots) beside 3x15 (area 45, interior 13, 1 dot). Breaks no scene claim, stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
    - `$SelectDensest`: replaces `select-most-dots` with the frame whose interior has the highest share of dot cells; no parameters. Fails Fit at train2: the 4x5 frame (rows 3–7, cols 10–13) holds 1 dot in 6 interior cells, against 4 in 25 for the 7x7 frame. It also fails test0.
    - `$SelectAnyDots`: replaces `select-most-dots` with the one frame that holds any dot; undefined where more than one does. Fails Fit at train1: both frames hold dots (3 and 1).
- `count-unit`: what is counted inside a frame
    - `concept`: dot cells
    - `$CountDotClusters`: replaces `select-most-dots`'s count with the count of 4-connected groups of dot cells inside the frame; no parameters; undefined where two frames tie. Fits every pair. Witness `dot-cluster`: a 5x5 frame holding three dots in one row (one cluster) beside a 7x7 frame holding two separate dots. Breaks no scene claim, stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
        - `adjacency`: which dot cells join a cluster
            - `concept`: 4-adjacency
            - `$Adjacency8`: joins diagonal neighbors too; no parameters. Fits every pair. Witness `diagonal-cluster`: a 5x5 frame holding three dots on one diagonal beside a 7x7 frame holding two separate dots. Breaks no scene claim, stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `background`: how the background color is known
    - `concept`: stored, `background` = 0
    - `background=DominantColor`: derives `background` as the commonest color of the input, replacing the stored value; undefined where colors tie for commonest. Fits every pair. Witness `background=DominantColor`: a 5x10 grid in which frame cells (28) outnumber 0 cells (19), so the derived background is the frame color, no frame is found, and the branch is undefined. Breaks no scene claim, stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks the input invariant that 0 is the commonest color of every input, since frames cover a minority of each grid of 13x13 or larger.
    - `background=SharedColor`: derives `background` from one input alone, which gives every color of that input; undefined on every input with more than one color. Fails Fit at train0.
    - `background=RarestColor`: derives `background` as the input's rarest color, which is the dot color in every pair. Fails Fit at train0, where it crops a 0-colored outline.
- `selection` & `background`, `count-unit` & `background`, `size-measure` & `background`, `adjacency` & `background`: the two branches' changes applied together
- `selection` & `count-unit`: the two branches' changes applied together (`$SelectDensest & $CountDotClusters` takes the share of clusters)
    - `$SelectLargest` & `$CountDotClusters`: `$SelectLargest`'s model alone. The count-unit property does not exist with `$SelectLargest`. It exists with the concept branch and `$SelectDensest` of `selection`, which together form the dot-based branch the concept takes, so `count-unit` stays at the concept.
    - `$SelectAnyDots` & `$CountDotClusters`: `$SelectAnyDots`'s model alone (a frame holds a cluster exactly when it holds a dot)
- `selection` & `adjacency`: the two branches' changes applied together (`$SelectDensest & $Adjacency8`)
    - `$SelectLargest` & `$Adjacency8`: `$SelectLargest`'s model alone
    - `$SelectAnyDots` & `$Adjacency8`: `$SelectAnyDots`'s model alone
- `size-measure` & `count-unit`, `size-measure` & `adjacency`: the `size-measure` branch's model alone (`$SizeByBorderCells` or `$SizeByInterior`), since neither property of counting exists with `$SelectLargest`

## Open parameters
- none

## Not formed
- A rule for frames tied for the most dots: it breaks `unique-most`, and no pair, solver header, lib component or proposer gives a tiebreak, so any such rule would be invented. The concept is undefined at a tie.
- Counting dots beside a frame on its outside, or within a margin around it: no pair, header, component or proposer reads dots outside a frame's border.
- A stored frame color, dot color or border color: each changes from pair to pair (2/4, 1/3, 3/2, 1/8), so no stored value fits more than one pair. OutNewColor and AnyOutNewColor propose nothing, because every output color appears in its input.
- Changing interior cells (swapping frame and dot colors, or clearing dots): every output keeps each interior cell's input color, so such a rule fails train0.

## Tickets filed
- none
