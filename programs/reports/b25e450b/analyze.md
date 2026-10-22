# b25e450b

## Concept
- Fits every pair (`check_concept.py`, `probe.py fit`). Each block of `block-color` is a solid rectangle that touches exactly one edge, so it slides to the opposite edge, and the band of its rows or columns takes `trail-color`. A landing takes priority over every track.
- The concept is undefined on an input where a block touches no edge or more than one edge (`floating-block`).
- No witness has the verdict `other`.

## Choice points
- `unit`: what moves
    - `concept`: a connected block of block cells moves as one piece
        - `connectivity`: how block cells join
            - `concept`: 4-adjacency
            - `$EightConnected`: replaces `edge-blocks` and `blocks-apart` with 8-connected blocks, so blocks that touch at a corner move as one. Undefined where a merged block touches two edges or none. Fits every pair. Witness `corner-touch`, which breaks `blocks-apart` and `edge-blocks` (one block is an L); `borderline`; verdict `concept`; it breaks the invariant that no two blocks touch, even at a corner.
        - `landing-shape`: where the block's cells land
            - `concept`: translated to the opposite edge
            - `$Mirror`: replaces `cross-to-opposite`: the block lands at the opposite edge flipped along the axis of travel. Fits every pair. Witness `shaped-block`, which breaks `edge-blocks`; `borderline`; verdict `concept`; it breaks the invariant that every block is a solid rectangle.
            - `$PointReflect`: replaces `cross-to-opposite`: the block lands at its half-turn image about the grid center. Fails Fit at train0: the block at the bottom edge in cols 1–2 lands in cols 7–8, where the output has it in cols 1–2.
    - `$PerLine`: replaces `edge-blocks`, `cross-to-opposite` and `wipe-track`: in each row and each column, a run of block cells that touches exactly one end of the line moves to the other end, and the whole line takes `trail-color`. Runs that touch no end are not moved. Defined on every input. Fits every pair. Witness `shaped-block`, which breaks `edge-blocks`; `borderline`; verdict `concept`; it breaks the invariant that every block is a solid rectangle.
- `direction-source`: what sets a block's axis and heading
    - `concept`: the one edge the block touches
    - `$AwayFromNearestEdge`: replaces `edge-blocks` and `cross-to-opposite`: the block moves to the edge opposite its nearest edge. Undefined where a block has two nearest edges. Fits every pair. Witness `floating-block`, which breaks `edge-blocks`; `borderline`; verdict `$AwayFromNearestEdge & $SweptOnly`; it breaks the invariant that every block touches an edge.
- `track-extent`: which cells take `trail-color`
    - `concept`: the whole band of the block's rows or columns, from edge to edge
    - `$VacateOnly`: replaces `wipe-track`: only the cells the block leaves. Fails Fit at train0, which is the first failing pair (train1 also fails, at row 3, col 3: input 5, output 7).
    - `$SweptOnly`: replaces `wipe-track`: only the cells between the block's place and its landing. Fits every pair. Its model alone is equivalent to the concept's model, because under the concept every block starts at one edge and lands at the opposite edge. So it has no witness alone, and it fails Equivalence. The case `$AwayFromNearestEdge & $SweptOnly` fits every pair. Witness `floating-block`, as for `$AwayFromNearestEdge`; verdict `$AwayFromNearestEdge & $SweptOnly`.
- `stop-rule`: where the slide ends
    - `concept`: at the opposite edge
    - `$StopAtBlock`: adds a claim: a block stops before it would enter another block's original cells. Fails Fit at train0: the block in rows 7–9, cols 1–2 stops at rows 4–6 below the block in rows 1–3, and the output has it in rows 0–2.
- `overlap-order`: which layer shows where a track meets a landing
    - `concept`: the landing (`block-on-top`)
    - `$TrackOnTop`: replaces `block-on-top`. Fails Fit at train0: row 1, cols 5–6 are 0 in the output, inside the track of the block in rows 1–3.
- `track-paint`: what a track does to its cells
    - `concept`: every track cell takes `trail-color`
    - `$RecolorTrack`: replaces `wipe-track` and makes `field-colors` a parameter. In the track, only the cells of the other field color and the block's own cells take `trail-color`, and cells of other colors keep their color. Fits every pair. Witness `stray-color`, which breaks `speckled-field`; `borderline`; verdict `concept`; it breaks the invariant that every non-block cell is 5 or 7.
- `block-cells`: which cells are block cells
    - `concept`: cells of `block-color`
        - `block-color`: where the block color comes from
            - `concept`: stored, 0
            - `block-color=RarestColor`: the rarest color of the input. Fails Fit at test0: 5 (54 cells) is rarer than 0 (55 cells).
    - `$NonFieldColor`: replaces `edge-blocks` and `block-on-top`, and makes `field-colors` a parameter in place of `block-color`. Block cells are the cells of neither field color, and each one lands in its own color. Undefined where landings of two colors meet. Fits every pair. Witness `second-hole-color`, which breaks `speckled-field`; `borderline`; verdict `$NonFieldColor`; it breaks the invariant that every input holds only 0, 5 and 7.
- `trail-color`: where the trail color comes from
    - `concept`: stored, 7
    - `trail-color=DominantColor`: the commonest color of the input. Fails Fit at train2: 5 (70 cells) is commoner than 7 (52 cells).
- `unit` & `direction-source`, `unit` & `track-extent`, `unit` & `stop-rule`, `unit` & `overlap-order`, `unit` & `track-paint`, `unit` & `block-cells`, `unit` & `block-color`, `unit` & `trail-color`, `connectivity` & `landing-shape`, `connectivity` & `direction-source`, `connectivity` & `track-extent`, `connectivity` & `stop-rule`, `connectivity` & `overlap-order`, `connectivity` & `track-paint`, `connectivity` & `block-cells`, `connectivity` & `block-color`, `connectivity` & `trail-color`, `landing-shape` & `direction-source`, `landing-shape` & `overlap-order`, `landing-shape` & `track-paint`, `landing-shape` & `block-cells`, `landing-shape` & `block-color`, `landing-shape` & `trail-color`, `direction-source` & `track-extent`, `direction-source` & `stop-rule`, `direction-source` & `overlap-order`, `direction-source` & `track-paint`, `direction-source` & `block-cells`, `direction-source` & `block-color`, `direction-source` & `trail-color`, `track-extent` & `stop-rule`, `track-extent` & `overlap-order`, `track-extent` & `track-paint`, `track-extent` & `block-cells`, `track-extent` & `block-color`, `track-extent` & `trail-color`, `stop-rule` & `overlap-order`, `stop-rule` & `track-paint`, `stop-rule` & `block-cells`, `stop-rule` & `block-color`, `stop-rule` & `trail-color`, `overlap-order` & `track-paint`, `overlap-order` & `block-cells`, `overlap-order` & `block-color`, `overlap-order` & `trail-color`, `track-paint` & `block-cells`, `track-paint` & `block-color`, `track-paint` & `trail-color`, `block-cells` & `trail-color`, `block-color` & `trail-color`: the two branches' changes applied together
- `landing-shape` & `stop-rule`: the two branches' changes applied together
    - `$PointReflect` & `$StopAtBlock`: the model of `$PointReflect` alone, because a half turn is not a slide and has no place to stop
- `landing-shape` & `track-extent`: the two branches' changes applied together
    - `$PointReflect` & `$SweptOnly`: the model of `$PointReflect` alone, because a half turn sweeps no path, so the band stays the track

## Open parameters
- none

## Not formed
- A block that touches two edges (a corner block or a block that spans the grid): no pair has one, and each place it could go adds a rule that no pair supports. The concept is undefined there, and `$PerLine` moves its runs along both axes.
- Blocks that slide one after another and stop on a block that has already landed: this needs an order among the blocks, and nothing in the pairs gives one.
- Other color proposers for `block-color` and `trail-color` (`SharedColor`, `OutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor` and the rest): on one input with `ex_out` empty, they give no value or more than one value.
- A derivation of `field-colors`: it is a scene parameter under the concept. The `$RecolorTrack` and `$NonFieldColor` cases read it, but no proposer gives a set of two colors.

## Tickets filed
- none
