# e3721c99

## Concept
- Fits every pair: each `shape_color` shape takes the color of the key with as many holes, and a shape whose hole count no key has is erased, as train0 (22,6) with 4 holes and train1 (23,12) with 2 holes show.
- No witness has the verdict `other`. Every rule in the concept file is relational: components, closed regions and an equality of counts, with no approximation.
- A hole of an object is counted in the cells outside that object alone. A pocket that the object closes off only with the divider, a key or another shape is not a hole (`pocket-against-divider`).
- The divider is the one `divider_color` object that touches the grid edge. A key of `divider_color` stays a key (train0 key at rows 1–3, cols 9–13; test1 key at rows 19–27, cols 1–3).

## Choice points
- `shape-connectivity`
    - `concept`: a shape is a 4-connected set of `shape_color` cells
    - `$Shape8`: replaces `shapes`; a shape is an 8-connected set, so shapes that touch at a corner are one shape; no further parameters; defined wherever the concept is. Fits every pair. Witness `shapes-touch-at-corner`: a shape with one hole and a solid shape touch at one corner; the concept gives 3 and 4, and `$Shape8` gives 3 to both. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks the invariant that every two shapes are apart by at least one `background` cell, diagonals included (the 4- and 8-connected components of `shape_color` are the same in every input).
- `hole-connectivity`
    - `concept`: a hole is closed against walks of cardinal steps
    - `$Hole8`: replaces `hole`; a walk also takes diagonal steps, so a hole with a diagonal gap to the outside is not a hole, and two holes that touch at a corner are one hole. Fails Fit at test1: the shape at rows 15–24, cols 19–27 has 3 holes under the concept and 2 under `$Hole8`, and `$Hole8` gives it 7 where the output has 2.
- `hole-enclosure`
    - `concept`: a hole of an object is closed off by that object alone
    - `$HoleByAllContent`: replaces `hole`; a hole is a closed region of `background` cells in the whole grid that touches the shape, so the divider, keys and other shapes can close it off. Fits every pair. Witness `pocket-against-divider`: a U-shaped shape opens onto the divider; the concept counts no hole and gives 4, and `$HoleByAllContent` counts one hole and gives 3. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks the invariant that no shape cell is next to a cell of a color other than `background` and `shape_color`, diagonals included.
- `key-match`
    - `concept`: a shape takes the key whose hole count equals its own
    - `$MatchByRank`: replaces `recolor-by-holes`; the distinct hole counts of the shapes, in order, take the keys in order of their hole counts. Fails Fit at test0: the keys have 2, 4 and 5 holes, and `$MatchByRank` gives the shapes with 0 holes the key with 2.
- `unmatched-shape`
    - `concept`: a shape whose hole count no key has is erased
    - `$KeepUnmatched`: replaces `erase-unmatched`; that shape keeps `shape_color`. Fails Fit at train0: the shape at rows 22–29, cols 2–9 with 4 holes is erased in the output.
- `divider-exclusion`
    - `concept`: the `divider_color` object that touches the grid edge is not a key
    - `$ExcludeDividerColor`: replaces `divider`; no `divider_color` object is a key. Fails Fit at train0: the key of color 1 with 2 holes is dropped, and the shapes with 2 holes are erased where the output gives them 1.
    - `$DividerByEdge`: replaces `divider`; every object that touches the grid edge is the divider and not a key, whatever its color, and `divider_color` is not read. Fits every pair. Witness `key-at-grid-edge`: the key with no hole stands against the grid edge; the concept gives the solid shape 4, and `$DividerByEdge` drops that key and erases the shape. It breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant that every key stands one cell in from the grid edge.
    - `$DividerKept`: drops the `divider` claim; the divider is a key too. Undefined at train0: the divider and the key of color 4 both have 0 holes, so two keys share a hole count. It fails Fit at train0.
- `background`
    - `concept`: `background` stored, 0
    - `background=DominantColor`: `background` derived as the commonest color of the input; undefined where two colors tie for commonest. Fits every pair: 0 is the commonest color of each input. Witness `background=DominantColor`: one shape with 3 holes covers more cells than the background; the concept gives it 2, and with `background` derived as 5 the zero cells become keys whose hole counts clash, so the branch is undefined there. No witness exists on which the branch is defined and differs: where 5 is the commonest color, every key's hole cell becomes a key with 0 holes. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks the invariant that `background` is the commonest color of every input.
- `shape-connectivity` & `hole-connectivity`, `shape-connectivity` & `hole-enclosure`, `shape-connectivity` & `key-match`, `shape-connectivity` & `unmatched-shape`, `shape-connectivity` & `divider-exclusion`, `shape-connectivity` & `background`, `hole-connectivity` & `hole-enclosure`, `hole-connectivity` & `key-match`, `hole-connectivity` & `unmatched-shape`, `hole-connectivity` & `divider-exclusion`, `hole-connectivity` & `background`, `hole-enclosure` & `key-match`, `hole-enclosure` & `unmatched-shape`, `hole-enclosure` & `divider-exclusion`, `hole-enclosure` & `background`, `key-match` & `unmatched-shape`, `key-match` & `divider-exclusion`, `key-match` & `background`, `unmatched-shape` & `divider-exclusion`, `unmatched-shape` & `background`, `divider-exclusion` & `background`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Match by the number of hole cells: the shape at train1 rows 19–24, cols 20–24 has one hole of 5 cells and takes color 3, the key with one hole of one cell.
- Match by key size, width or position: the shapes vary in size and place, and no such property of a shape gives its key on train0.
- `shape_color` or `divider_color` derived: no proposer in `programs/proposers.dl` gives 5 or 1 from one input alone, with `ex_out` empty.
- `background` derived by `SharedColor`: on one input it gives every color present, so the branch has no single background.
- A divider found as the longest line or the largest `divider_color` object: it picks the same object as the concept on every input where the divider runs to the grid edge, which the `divider` claim states.

## Tickets filed
- 10-914_task_e3721c99_analyze.md
