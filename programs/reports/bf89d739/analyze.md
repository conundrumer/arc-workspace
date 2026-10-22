# bf89d739

## Concept
- The concept fits every train and test pair (`probe_models.py`). In its model, each two dots that share a row or a column with no dot between them form a trunk. A dot off a trunk's line gets a branch only where its level is strictly between that trunk's two dots. Trunk and branch paint background cells only.
- No witness has the verdict `other`. On `dot-beyond-pair` the verdict is `$TrunkSpansAll`, and on `dot-of-another-color` and `dot_color=RarestColor` it is `$DotsOfOneColor`. Those branches list these witnesses.
- `two-aligned-pairs` breaks `one-aligned-pair`: two aligned pairs cross. Plausibility `borderline`: every input has exactly one aligned pair. Verdict `concept`: both trunks are drawn as a cross.

## Choice points
- `connection`: what joins the dots
    - `concept`: one straight trunk between the aligned pair, and a perpendicular branch from every other dot
    - `$FewestCellTree`: replaces `trunk` and `branch`: the connected set with the fewest cells that holds every dot takes `line_color`. Fails Fit at train3: the train output's tree has 27 cells, and a tree of 26 cells holds every dot (`probe_steiner.py`). At train0 two trees of 20 cells hold every dot.
    - `$FewestCellTrunk`: replaces `trunk` and `one-aligned-pair`: one straight trunk, on the row or column that needs the fewest cells, covers every dot's level, and every other dot branches perpendicular onto it. Fails Fit at train0: row 6 and column 8 each give a tree of 20 cells, so the output holds two grids.
- `beyond-span`: what a dot gets when its level is not strictly between the pair's two dots
    - `concept`: no branch
    - `$TrunkSpansAll`: replaces `trunk` and `within-span`: each trunk runs from the least to the greatest level among its pair and every dot off its line, and every dot off the line branches onto it. Defined on every input. Fits every pair. Witness `dot-beyond-pair` breaks `within-span`, plausibility `borderline` (the invariant it breaks: in every input the aligned pair are the two extreme dots along their line), verdict `$TrunkSpansAll`.
    - `$BranchToLine`: replaces `branch` and `within-span`: every dot off a trunk's line branches to that line, past the trunk's end where its level is beyond the pair. Defined on every input. Fits every pair. Witness `dot-beyond-pair` breaks `within-span`, plausibility `borderline` (the same invariant), verdict `$TrunkSpansAll`.
- `trunk-count`: how many aligned pairs the model takes
    - `concept`: every aligned pair is a trunk
    - `$OnePairOnly`: replaces `one-aligned-pair` with a condition: undefined on an input where the count of aligned pairs is not one. Fits every pair. It is subsumed by the concept's model. Witness `two-aligned-pairs`, on which it is undefined, breaks `one-aligned-pair`, plausibility `borderline` (every input has exactly one aligned pair), verdict `concept`. No witness exists on which it is defined and differs from the concept.
- `dot-reading`: which cells are dots
    - `concept`: every cell that is not `background`
    - `$DotsOfOneColor`: replaces `scattered-dots`: only cells of `dot_color` are dots, and `dot_color` (stored, 2) moves to Parameters. Defined on every input. Fits every pair. Witness `dot-of-another-color` breaks `scattered-dots`, plausibility `foreign` (the invariant it breaks: every non-background cell is 2), verdict `$DotsOfOneColor`.
        - `dot_color`: the source of the dot color
            - `concept`: stored, 2
            - `dot_color=RarestColor`: the rarest color of each input. Defined on every input. Fits every pair. Witness `dot_color=RarestColor` breaks `scattered-dots`, plausibility `foreign` (every non-background cell is 2), verdict `$DotsOfOneColor`.
- `background`: the source of the background color
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest color of each input. Defined on every input. Fits every pair. Witness `background=DominantColor` breaks `scattered-dots` (a field of 5), plausibility `variant` (the invariant it breaks: every field is 0), verdict `background=DominantColor`.
    - `background=RarestColor`: gives 2, so every 0 cell is read as a dot and nothing is drawn. Fails Fit at train0.
    - `background=SharedColor`: gives both 0 and 2 on every input. Fails Fit at train0.
- `line_color`: the source of the line color
    - `concept`: stored, 3
    - `line_color=OutNewColor`: with `ex_out` empty, the derivation gives no value on any input, so the model is undefined on every pair. Fails Fit at train0.
- `beyond-span` & `trunk-count`, `beyond-span` & `dot-reading`, `beyond-span` & `background`, `beyond-span` & `line_color`, `trunk-count` & `dot-reading`, `trunk-count` & `background`, `trunk-count` & `line_color`, `dot-reading` & `background`, `dot-reading` & `line_color`, `background` & `line_color`, `connection` & `dot-reading`, `connection` & `background`, `connection` & `line_color`, `dot_color` & `connection`, `dot_color` & `beyond-span`, `dot_color` & `trunk-count`, `dot_color` & `background`, `dot_color` & `line_color`: the two branches' changes applied together
- `connection` & `beyond-span`, `connection` & `trunk-count`: the `connection` branch's model alone. Neither `$FewestCellTree` nor `$FewestCellTrunk` has a pair of dots that bounds a trunk, so `beyond-span` and `trunk-count` exist only with the concept branch of `connection`, which is the concept.

## Open parameters
- none

## Not formed
- `line_color` from `AnyOutNewColor`, `ChangedColor`, `ChangedPairs` or `VanishedNewPairs`: like `OutNewColor`, each reads `ex_out`, which is empty in a run on one input. Each gives no value, so the model fails Fit at train0 in the same way.
- A trunk axis stored as a parameter: the trunk lies on a row in train0, train2 and test0, and on a column in train1 and train3. No stored axis fits every pair.

## Tickets filed
- none
