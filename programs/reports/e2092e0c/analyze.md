# e2092e0c

## Concept
- The concept case fits every pair: the one exact copy of the top-left 3×3 key outside the fenced corner is at train0 (5,5), train1 (9,6), train2 (8,7) and test0 (10,10), and a 5 ring one cell outside it gives each output.
- Its rules have a relational form: the match is an equality of cells at a translation, and the ring is the box one cell outside the copy less the copy.
- No witness has verdict `other`.

## Choice points
- `match-cells`: which cells of a placement must equal the key's
    - `concept`: all nine, background included
    - `$MatchMarks`: replaces `one-copy` and `ring-copy` with a match on the key's non-background cells alone, the key's background cells free; no new parameter; defined wherever the concept is. Fits every pair. Witness `near-copy`: train0's input with the key's marks and one extra 3 at rows 10–12, cols 10–12; it breaks no scene claim; `borderline`, verdict `concept`; it breaks the invariant that no place outside the fence other than the copy holds the key's marks.
    - `$MatchShape`: replaces `one-copy` and `ring-copy` with a match on which cells are non-background, colors ignored; no new parameter. Fails Fit at train2: placement (10,6) also matches, and its ring changes train2 (9,5), (9,7), (10,5) and other cells.
- `match-transform`: the transforms under which a placement matches the key
    - `concept`: the identity
    - `$MatchTurned`: replaces `one-copy` and `ring-copy` with a match against each D4 image of the key; no new parameter; defined wherever the concept is. Fits every pair. Witness `turned-copy`: train0's input with its copy turned a quarter turn clockwise; it breaks `one-copy`; `variant`, verdict `$MatchTurned`; it breaks the invariant that the copy has the key's orientation.
- `search-region`: the placements that are searched
    - `concept`: those that do not overlap the fenced corner
    - `$SearchWholeGrid`: replaces `one-copy` with every placement except the key's own; no new parameter; defined wherever the concept is. Fits every pair. Witness `mark-color-key`: train0's input with the key and the copy solid 5; it breaks no scene claim; `foreign`, verdict `concept`; it breaks the invariant that no key cell is `mark-color`.
- `copy-count`: what happens when the copies are not exactly one
    - `concept`: every copy gets a ring, and with no copy the input is returned
    - `$OnlyCopy`: adds to `ring-copy` that the model is undefined unless there is exactly one copy; no new parameter. Fits every pair, and fails Subsumption: the concept case's model gives its output wherever it is defined. Witness `two-copies`: train0's input with a second exact copy at rows 10–12, cols 10–12, where `$OnlyCopy` is undefined; it breaks `one-copy`; `borderline`, verdict `concept`; it breaks the invariant that the key occurs once outside the fence.
- `ring-edge`: a ring that reaches past the grid edge
    - `concept`: the ring's cells inside the grid are drawn
    - `$RingInGrid`: adds to `ring-copy` that the model is undefined where the ring leaves the grid; no new parameter. Fits every pair, and fails Subsumption: the concept case's model gives its output wherever it is defined. Witness `copy-at-edge`: the only copy at rows 12–14, cols 5–7, where `$RingInGrid` is undefined; it breaks `one-copy`; `borderline`, verdict `concept`; it breaks the invariant that the copy sits at least one cell from every grid edge.
- `ring-width`: the width of the ring
    - `concept`: one cell
    - `$RingFenceWidth`: replaces `ring-copy` with a ring as wide as the fence, which is counted as the lines of `mark-color` that run around the key from `key-size` outward; undefined where no fence line stands at `key-size`. Fits every pair. Witness `thick-fence`: train0's input with the fence on rows 3–4 and cols 3–4, and the copy at rows 9–11, cols 9–11; it breaks `corner-key`; `variant`, verdict `$RingFenceWidth`; it breaks the invariant that the fence is one line.
- `ring-shape`: the cells that are drawn around the copy
    - `concept`: the whole ring
    - `$StampFence`: replaces `ring-copy` with the fence's L shape, on the copy's two inner sides alone; no new parameter. Fails Fit at train0: (4,4)–(4,7) and (5,4), (6,4) stay 0.
- `ring-cover`: what the ring does to the cells it covers
    - `concept`: every covered cell becomes `mark-color`
    - `$RingOnBackground`: replaces `ring-copy` with a ring that colors only the background cells it covers; no new parameter. Fails Fit at train0: (7,8) and (8,4) keep 8 and 7.
- `mark-color`: the ring's color
    - `concept`: stored, 5
    - `$RingFenceColor`: replaces `mark-color` in `ring-copy` with the one color of the fence cells at `key-size` in `key-corner`; undefined where those cells have more than one color. Fits every pair. Witness `fence-recolored`: train0's input with the fence in 4; it breaks `corner-key`; `variant`, verdict `$RingFenceColor`; it breaks the invariant that the fence is 5.
    - `mark-color=DominantColor`: derives the color as the commonest color of the input. Fails Fit at train0: it gives 0, so the ring is not drawn.
    - `mark-color=RarestColor`: derives the color as the least common color of the input. Fails Fit at train0: it gives 8 and 3, so the output holds a ring of each.
    - `mark-color=SharedColor`: derives the color as each color in the input. Fails Fit at train0: the output holds one grid for each of the input's colors.
- `key-size`: the key's side
    - `concept`: stored, 3
    - `$KeySizeFromFence`: replaces `key-size` with the least k at which row k, cols 0..k, and col k, rows 0..k, all hold `mark-color` in the frame of `key-corner`; undefined where there is no such k. Fits every pair. Witness `bigger-key`: a 4×4 key fenced at row 4 and col 4, with its copy at rows 9–12, cols 9–12; it breaks `corner-key`; `variant`, verdict `$KeySizeFromFence`; it breaks the invariant that the key is 3×3.
    - `key-size=TileDim`: derives the size from the tile sizes that fit the grid extent 15. Fails Fit at train0: it gives several sizes, 7, 5 and 3 among them, so the output holds several grids.
- `key-corner`: the corner that holds the key
    - `concept`: stored, top-left
    - `$KeyCornerFromFence`: replaces `key-corner` with the one corner whose frame has the fence of `mark-color` at `key-size`; undefined where no corner, or more than one, has it. Fits every pair. Witness `turned-grid`: train0's input turned a half turn, which puts the key in the bottom-right corner; it breaks `corner-key`; `variant`, verdict `$KeyCornerFromFence`; it breaks the invariant that the key is at the top left.
- `match-cells` & `match-transform`, `match-cells` & `search-region`, `match-cells` & `copy-count`, `match-cells` & `ring-edge`, `match-cells` & `ring-width`, `match-cells` & `ring-shape`, `match-cells` & `ring-cover`, `match-cells` & `mark-color`, `match-cells` & `key-size`, `match-cells` & `key-corner`, `match-transform` & `search-region`, `match-transform` & `copy-count`, `match-transform` & `ring-edge`, `match-transform` & `ring-width`, `match-transform` & `ring-shape`, `match-transform` & `ring-cover`, `match-transform` & `mark-color`, `match-transform` & `key-size`, `match-transform` & `key-corner`, `search-region` & `copy-count`, `search-region` & `ring-edge`, `search-region` & `ring-width`, `search-region` & `ring-shape`, `search-region` & `ring-cover`, `search-region` & `mark-color`, `search-region` & `key-size`, `search-region` & `key-corner`, `copy-count` & `ring-edge`, `copy-count` & `ring-width`, `copy-count` & `ring-shape`, `copy-count` & `ring-cover`, `copy-count` & `mark-color`, `copy-count` & `key-size`, `copy-count` & `key-corner`, `ring-edge` & `ring-width`, `ring-edge` & `ring-shape`, `ring-edge` & `ring-cover`, `ring-edge` & `mark-color`, `ring-edge` & `key-size`, `ring-edge` & `key-corner`, `ring-width` & `ring-shape`, `ring-width` & `ring-cover`, `ring-width` & `mark-color`, `ring-width` & `key-size`, `ring-width` & `key-corner`, `ring-shape` & `ring-cover`, `ring-shape` & `mark-color`, `ring-shape` & `key-size`, `ring-shape` & `key-corner`, `ring-cover` & `mark-color`, `ring-cover` & `key-size`, `ring-cover` & `key-corner`, `key-size` & `key-corner`: the two branches' changes applied together
- `mark-color` & `key-size`: the fence is found by its shape alone, as the least k at which row k, cols 0..k, and col k, rows 0..k, all hold one color, and that color is the ring's
    - `mark-color=DominantColor` & `$KeySizeFromFence`, `mark-color=RarestColor` & `$KeySizeFromFence`, `mark-color=SharedColor` & `$KeySizeFromFence`, `mark-color=DominantColor` & `key-size=TileDim`, `mark-color=RarestColor` & `key-size=TileDim`, `mark-color=SharedColor` & `key-size=TileDim`, `$RingFenceColor` & `key-size=TileDim`: the two branches' changes applied together
- `mark-color` & `key-corner`: the key's corner is the one corner whose cells at `key-size` form an L of one color, and that color is the ring's; undefined where no corner, or more than one, has it
    - `mark-color=DominantColor` & `$KeyCornerFromFence`, `mark-color=RarestColor` & `$KeyCornerFromFence`, `mark-color=SharedColor` & `$KeyCornerFromFence`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- none

## Tickets filed
- none
