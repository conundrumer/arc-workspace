# ea32f347

## Concept
- Fits every pair: the bars have pairwise different cell counts in every input (6/5/3, 6/4/2, 6/5/3, 7/5/4, test 6/5/3), and `rank_color` gives 1, 4, 2 to ranks 0, 1, 2 in each. Every rank is a key of some train pair, so `rank_color` has no unseen key.
- No witness has verdict `other`.
- Two witnesses that break scene claims give a verdict against the concept's rule. On `two-bars` (a variant with two bars), the verdict is `$ExtremesAndRest`. On `tied-lengths`, the verdict is the shared output of `$CompetitionRank` and `$ExtremesAndRest`. On both, the concept is defined and gives the rank table's colors in order.
- On `non-background-bars` and `bar_color=RarestColor` (bars drawn in 8), the concept finds no bar and keeps the input. The verdict there is the recoloring that the derived bar cells give.

## Choice points
- `color-from-order`: how a bar's color follows from the length order
    - `concept`: rank counted from the longest bar, color from the stored `rank_color`
    - `$RankFromShortest`: replaces `rank-by-length`: rank counted from the shortest bar; stores `rank_color` rank 0 → `2`, rank 1 → `4`, rank 2 → `1`; undefined where a rank has no entry. Fits every pair. Witness `two-bars`: breaks `straight-bars` (`bar_count` 3); `variant`; verdict `$ExtremesAndRest`; breaks the invariant that every input holds three bars.
    - `$ExtremesAndRest`: replaces `rank-by-length` and `recolor-by-rank`: the longest bars take `longest_color` `1`, the shortest bars take `shortest_color` `2`, every other bar takes `rest_color` `4`; undefined where all bars have one length. Fits every pair. Witness `two-bars`: as above; verdict `$ExtremesAndRest`.
    - `$LengthLookup`: replaces `rank-by-length` and `recolor-by-rank`: a stored table from a bar's cell count to its color. Fails Fit: train1 gives length 4 the color 4 and train3 gives it 2, so no table fits both.
    - `$PositionOrder`: replaces `rank-by-length`: rank by a bar's first cell in row-major order. Fails Fit at train3, under any table.
    - `$PerAxisRank`: replaces `rank-by-length`: horizontal and vertical bars rank separately. Fails Fit at train2: the only vertical bar (length 5) takes rank 0, and the output gives it 4.
- `tie-rank`: the rank of bars that share a length
    - `concept`: dense rank: bars of one length share a rank, and the next length takes the next rank
    - `$CompetitionRank`: replaces `rank-by-length`: a bar's rank is the number of bars longer than it. Fits every pair. Witness `tied-lengths`: breaks `distinct-lengths`; `borderline`; verdict `$CompetitionRank`; breaks the invariant that the bars of an input have pairwise different lengths.
    - `$UndefinedAtTies`: adds to `rank-by-length`: undefined where two bars share a length. Fits every pair. Fails Subsumption: the concept subsumes it. It has no witness on which it is defined, because wherever it is defined it gives the concept's output. `tied-lengths` is the input where it is undefined.
- `length-measure`
    - `concept`: a bar's cell count
    - `$ExtentLength`: replaces `rank-by-length`: a bar's extent along its longer axis. Fits every pair. Witness `bent-bar`: breaks `straight-bars`; `foreign`; verdict `concept`; breaks the invariant that every bar is a one-cell-wide straight run.
- `adjacency`
    - `concept`: bars are 4-connected components
    - `$DiagonalJoin`: replaces `straight-bars`' 4-connectivity: bars are 8-connected components (`Components8`). Fits every pair. Witness `corner-touch`: breaks `straight-bars` (no two bars touch); `borderline`; verdict `concept`; breaks the invariant that no two bars touch, even at a corner.
- `bar-cells`: which cells form bars
    - `concept`: the cells of the stored `bar_color` `5`
    - `bar_color=RarestColor`: derives `bar_color` as the rarest color of the input. Fits every pair. Witness `bar_color=RarestColor`: breaks `straight-bars` (`bar_color` 5); `variant`; verdict `bar_color=RarestColor` (shared with `$NonBackground`); breaks the invariant that the bars are 5.
    - `bar_color=SharedColor`: derives `bar_color` as every color of the input. Fails Fit at train0: it gives `0` and `5`, so the output holds two grids.
    - `bar_color=DominantColor`: derives `bar_color` as the commonest color of the input. Fails Fit at train0: it gives `0`.
    - `$NonBackground`: replaces `straight-bars`' bar color: the bars are the components of the cells that are not the stored `background` `0`, and the program reads `background` in place of `bar_color`. Fits every pair. Witness `non-background-bars`: breaks `straight-bars` (`bar_color` 5); `variant`; verdict `$NonBackground`; breaks the invariant that the bars are 5.
        - `background-source`
            - `concept`: the stored `background` `0`
            - `background=DominantColor`: derives `background` as the commonest color of the input. Fits every pair. Witness `$NonBackground & background=DominantColor`: breaks `background` (`0`); `variant`; verdict `background=DominantColor` (shared with the concept case); breaks the invariant that the field is 0.
- `color-from-order` & `length-measure`, `color-from-order` & `adjacency`, `color-from-order` & `bar-cells`, `tie-rank` & `length-measure`, `tie-rank` & `adjacency`, `tie-rank` & `bar-cells`, `length-measure` & `adjacency`, `length-measure` & `bar-cells`, `adjacency` & `bar-cells`: the two branches' changes applied together
- `color-from-order` & `tie-rank`: the two branches' changes applied together; with `$RankFromShortest`, the rank counts from the shortest bar
    - `$ExtremesAndRest` & `$CompetitionRank`: `$ExtremesAndRest`'s model. It reads no rank, and tied extreme bars already share a role color, so the tie-rank property does not exist with `$ExtremesAndRest` except as `$UndefinedAtTies`.

## Open parameters
- none

## Not formed
- `rank_color` derived: no proposer gives a rank-to-color relation, and the colors 1, 4, 2 are in no input.
- `bar_color` by ChangedColor, VanishedColor, UnchangedColor, OutNewColor, AnyOutNewColor: each reads train outputs, and a `@derive` run reads one input and no output.
- `background` derived under the concept: the concept's program does not read `background`. It is a scene parameter there.
- `bar_count` stored or derived: no rule reads the bar count. A rank with no entry in `rank_color` makes the concept undefined, which bounds the count.

## Tickets filed
- none
