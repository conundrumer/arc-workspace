# e760a62e

## Concept
- Fits every pair. `work/task/e760a62e/probe.py` reproduces each train and test output. It parses the rooms with the lib's `DividerTiles`, over the full rows and full columns of `divider_color`.
- It has a relational form. A dot is the one cell of a room that is not `background`. Two dots of one color join when their rooms share a room row or a room column, and a bar fills every room on the run between them, both ends included. A room that two bar colors fill takes the color that `cross_color` keys by that color pair. The generator applies the rule as stated, and nothing in it is an approximation.
- The concept case is undefined on these inputs:
    - a room that holds more than one cell that is not `background`
    - a crossing of two bar colors that `cross_color` has no key for
    - a room that three bar colors fill
- No witness has verdict `other`.

## Choice points
- `dot-alignment`: which two dots count as aligned
    - `concept`: dots whose rooms share a room row or a room column
    - `$CellAligned`: replaces `join-aligned-dots`. Two dots join only where they share a grid row or a grid column of cells, and the bar fills every room on its run. No parameter. Defined where the concept is. Fits every pair, because every dot of an input sits at one place in its room. Witness `offset-dots`: the two 3 dots of room row 2 of train0 sit at (9,1) and (8,16). It breaks `dot-offset` and stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant that every dot of an input sits at one place in its room.
- `join-lines`: the line families along which dots join
    - `concept`: room rows and room columns
    - `$DiagonalJoin`: adds that two dots of one color on one diagonal of rooms join too, and their bar fills the rooms on that diagonal. No parameter. Defined where the concept is. Fits every pair, because no two dots of one color share a room diagonal there. Witness `diagonal-dots`: 2 dots in rooms (0,0), (0,2) and (2,2). It breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `bar-extent`: how far a bar runs along its room line
    - `concept`: from the room of one dot to the room of the other
    - `$EdgeToEdge`: replaces `join-aligned-dots`. The bar of two aligned dots fills their whole room line, from grid edge to grid edge. Fails Fit at train0: room (5,1), rows 20–21, cols 4–6, stays 0 in the output.
- `bar-width`: what part of each room a bar fills
    - `concept`: the whole room
    - `$ThinBar`: replaces `join-aligned-dots`. The bar fills only the grid row or column that the two dot cells share, and skips the divider cells. Undefined where two joined dots share no grid line. Fails Fit at train0: (0,4) is 2 in the output, and the bar fills only col 5.
- `which-pairs`: which two same-colored dots on one room line join
    - `concept`: every two
    - `$ExactlyTwo`: replaces `join-aligned-dots`. The dots of one color on a room line join only when that line holds exactly two of them. No parameter. Defined where the concept is. Fits every pair. Witness `three-in-line`: room row 1 of train2 holds 2 dots in rooms (1,0), (1,1) and (1,3). It breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
    - `$NoPassThroughDot`: replaces `join-aligned-dots`. Two dots join only when no room strictly between them holds a dot of any color. No parameter. Defined where the concept is. Fits every pair. Witness `dot-in-other-bar`: a 3 dot at (8,14) in room (1,2) of train2 lies between the two 2 dots of room row 1 and pairs with the 3 dot of room (3,2). It breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `dot-cell`: what the dot cell of a room becomes where a bar fills the room
    - `concept`: the room's fill color, as every other cell of the room
    - `$DotCellKeeps`: replaces `join-aligned-dots`. A dot cell keeps its own color, and the rest of its room takes the fill. No parameter. Defined where the concept is. Fits every pair, because no dot's room is a crossing there. Witness `dot-in-other-bar`, as above: room (1,2) is 6 with 3 kept at (8,14). Plausibility `ordinary`, verdict `concept`.
- `cross-color`: what color a room takes where bars of two colors cross
    - `concept`: the stored `cross_color`, keyed by the two bar colors
    - `$OneCrossColor`: replaces `cross-mix`. One stored color, 6, fills every room that two bar colors fill, whatever the two colors are. Defined on the crossings the concept has no key for. Fits every pair. Witness `third-color`: the 3 dots of train2 are replaced by 4 dots in rooms (0,1) and (2,1), and their bar crosses the 2 bar at room (1,1). It breaks `two-dot-colors` and stands at the stored assignment, where the concept is undefined. Plausibility `borderline`, verdict `$OneCrossColor`. It breaks the invariant that every dot is 2 or 3.
    - `$OverAxis`: replaces `cross-mix`. At a crossing, the bar on a stored `over_axis` keeps its color. Fails Fit at train0 at either axis: room (2,1), rows 8–10, cols 4–6, is 6 in the output, and the branch gives 2 or 3.
- `divider-color`: where the divider color comes from
    - `concept`: the stored `divider_color`
    - `$DerivedDivider`: replaces the stored `divider_color`. Clauses derive it as the one color that fills some full row and some full column of the input. Undefined where no color, or more than one color, does that. Fits every pair. Witness `other-divider-color`: train0 with its dividers in 5. It breaks `divider-tiling` and stands at the stored assignment, where the concept is undefined. Plausibility `variant`, verdict `$DerivedDivider`. It breaks the invariant that the dividers are 8.
- `background-color`: where the background comes from
    - `concept`: the stored `background`
    - `$DerivedBackground`: replaces the stored `background`. Clauses derive it as the commonest color among the cells off the divider lines. Undefined on a tie. Fits every pair. Witness `other-background`: train0 with its background in 1. It breaks `background-rooms` and stands at the stored assignment, where the concept is undefined. Plausibility `variant`, verdict `$DerivedBackground`. It breaks the invariant that the background is 0.
- `cut-rooms`: whether the cut-short strips at the bottom and right edges are rooms
    - `concept`: they are rooms. A dot there joins, and bars fill them.
    - `$CutRoomsInert`: replaces `divider-tiling`. A room narrower than the other rooms of its axis is no room: a dot there joins nothing and stays, and no bar fills it. No parameter. Defined where the concept is. Fits every pair, because no dot lies in a cut-short room there. Witness `dot-in-cut-room`: a 3 dot added to train0 at (9,21), in room (2,5). It breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `dot-alignment` & `join-lines`, `dot-alignment` & `bar-extent`, `dot-alignment` & `bar-width`, `dot-alignment` & `which-pairs`, `dot-alignment` & `dot-cell`, `dot-alignment` & `cross-color`, `dot-alignment` & `divider-color`, `dot-alignment` & `background-color`, `dot-alignment` & `cut-rooms`, `join-lines` & `bar-extent`, `join-lines` & `bar-width`, `join-lines` & `which-pairs`, `join-lines` & `dot-cell`, `join-lines` & `cross-color`, `join-lines` & `divider-color`, `join-lines` & `background-color`, `join-lines` & `cut-rooms`, `bar-extent` & `bar-width`, `bar-extent` & `which-pairs`, `bar-extent` & `dot-cell`, `bar-extent` & `cross-color`, `bar-extent` & `divider-color`, `bar-extent` & `background-color`, `bar-extent` & `cut-rooms`, `bar-width` & `which-pairs`, `bar-width` & `dot-cell`, `bar-width` & `cross-color`, `bar-width` & `divider-color`, `bar-width` & `background-color`, `bar-width` & `cut-rooms`, `which-pairs` & `dot-cell`, `which-pairs` & `cross-color`, `which-pairs` & `divider-color`, `which-pairs` & `background-color`, `which-pairs` & `cut-rooms`, `dot-cell` & `cross-color`, `dot-cell` & `divider-color`, `dot-cell` & `background-color`, `dot-cell` & `cut-rooms`, `cross-color` & `divider-color`, `cross-color` & `background-color`, `cross-color` & `cut-rooms`, `divider-color` & `background-color`, `divider-color` & `cut-rooms`, `background-color` & `cut-rooms`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Joining only consecutive dots of a line, or only its two extreme dots: the rooms those bars fill, taken together, are the run from the line's first dot to its last. This is the rooms the concept fills, so the model is the concept's.
- `cross_color` derived: 6 is in no input, so no proposer that reads one input gives it. `OutNewColor` and `AnyOutNewColor` read `ex_out`, which is empty in a run on one input.
- `cross_color` as arithmetic on the two bar colors (2 + 3, 2 × 3): colors have identity only, so this has no relational form.
- `divider_color` or `background` derived by a proposer. On one input alone:
    - `SharedColor` gives every color of the input.
    - `DominantColor` gives 0 on train0 and 8 on train1.
    - `RarestColor` gives a dot color.
    - the proposers that compare inputs with outputs read `ex_out`, which is empty.
    - No proposer gives 8 or 0 on every pair. The clause derivations are `$DerivedDivider` and `$DerivedBackground`.
- A stored room size or room count: rooms are 3, 2, 5 and 4 cells wide across the pairs, and the room counts differ too. These values are task data that the tiling gives, and no stored value fits every pair.
- Stored dot colors: the program finds a dot as the room cell that is not `background`, so it reads no dot color apart from the key of `cross_color`.
- A dot with no partner of its color on its room lines: every model leaves it as it is, so it separates no two models.

## Tickets filed
- none
