# db93a21d

## Concept
- Fits every train pair and the test pair (`probe.py` runs it).
- No witness has the verdict `other`.
- The rule has a relational form: the halo width is half a square's side, a count of cells, and the probe computes it with no other number.
- The concept is undefined on a square of odd side (`odd-side`), where `$HaloFloor` and `$HaloCeil` are defined.
- At the stored `square_color`, the concept finds no square in a color-permuted input and keeps the input. The witness `square_color=RarestColor` has the verdict `square_color=RarestColor` there.

## Choice points
- `halo-width`: how the halo width follows from the square's measure
    - `concept`: half the measure (`frame_scale` 2)
        - `odd-side`: the halo width of a square whose measure is odd
            - `concept`: undefined
            - `$HaloFloor`: replaces `halo`; the halo width is half the measure, rounded down; undefined on no input the concept is defined on. Fits every pair, and it is a case. Witness `odd-side`, a 3x3 square: breaks `squares` (each square has an even side); stands at the stored assignment; plausibility `borderline`, since every square in the evidence has an even side; verdict `any`.
            - `$HaloCeil`: replaces `halo`; the halo width is half the measure, rounded up. Fits every pair, and it is a case. Witness `odd-side`, as for `$HaloFloor`.
    - `$HaloTable`: replaces `halo`; a stored table from measure to halo width, `halo_table` = {2: 1, 4: 2, 6: 3}; undefined on a square whose measure is not a key. Fits every pair: the test sides 6, 4, 4 and 2 are all train keys. Fails Subsumption: the concept subsumes it, since each table the generator's tasks give holds half the measure at each key. Witness `side-eight`, an 8x8 square: breaks no scene claim; stands at the stored assignment, where the table has no key 8 and is undefined; plausibility `ordinary`; verdict `concept`.
- `halo-measure`: which extent of a square the halo width halves
    - `concept`: the longer extent, which is the side of a square that the grid edge cuts
    - `$HaloByWidth`: replaces `halo`; the extent across `trail_dir`, the square's visible width; undefined where that extent is odd. Fits every pair: the only cut square, train3's at rows 0–1, cols 7–10, is cut on the row axis. It is a case. Witness `cut-at-side`, a 4x4 square that the left edge cuts to 2 columns: breaks no scene claim; stands at the stored assignment; plausibility `ordinary`; verdict `concept`.
    - `$HaloByShorter`: replaces `halo`; the shorter extent. Fails Fit at train3: the square at rows 0–1, cols 7–10 gets a halo 1 wide in place of 2, first at train3 output (0,5).
- `halo-shape`: which cells near a square the halo holds
    - `concept`: every cell of the box out to the halo width, the square excluded
    - `$HaloDiamond`: replaces `halo`; the cells within taxicab distance of the halo width. Fails Fit at train0: the corner cell train0 output (2,5) is `3`.
- `layer-order`: which of a square cell, a halo cell and a trail cell shows where they meet
    - `concept`: square over halo over trail
    - `$HaloOverSquares`: replaces `layers`; halo over square over trail, so a halo paints the cells of another square. Fits every pair: no square lies in another's halo. It is a case. Witness `square-in-halo`: breaks `clear-halo`; stands at the stored assignment; plausibility `borderline`, since no square in the evidence lies in another square's halo; verdict `concept`.
    - `$SquaresUnderAll`: replaces `layers`; halo over trail over square, so a trail paints the cells of a square below it. Fits every pair: no trail crosses a square. It is a case. Witness `square-below`: breaks `own-columns`; stands at the stored assignment; plausibility `borderline`, since no two squares in the evidence share a column; verdict `concept`.
- `trail-stop`: where a trail ends
    - `concept`: at the grid edge, under every halo and square it meets
    - `$TrailStopsAtSquare`: replaces `trail`; a trail ends at the first square cell in its column. Fits every pair. Fails Equivalence: it is equivalent to the concept, so it has no witness. Below the square that stops a trail, that square's own trail fills the same columns, and above it, its halo covers the trail.
    - `$TrailStopsAtHalo`: replaces `trail`; a trail ends at the first cell of another square's halo. Fails Fit at train3: the trail at col 7 runs on below the halo of the square at rows 8–11, cols 2–5, at train3 output (14,7).
- `square_color`: which color makes the squares
    - `concept`: stored, 9
    - `square_color=RarestColor`: replaces `squares` and reads the square color as the color with the fewest cells in the input; undefined where two colors tie for the fewest. Fits every pair. It is a case. Witness `square_color=RarestColor`, train0's input with its squares in 4: breaks `squares` at the stored assignment; stands at the stored assignment, where the concept keeps the input and the branch draws the halos and trails; plausibility `variant`, since every input in the evidence draws its squares in 9 and a color permutation gives a variant task; verdict `square_color=RarestColor`.
    - `square_color=SharedColor`: gives 0 and 9. Fails Fit at train0: the 0 cells form no solid square, so the model is undefined.
    - `square_color=DominantColor`: gives 0. Fails Fit at train0, which is undefined for the same reason.
- `frame_color`: the halo's color
    - `concept`: stored, 3
    - `frame_color=OutNewColor`: on a run on an input, `ex_out` is empty and the proposer gives no color. Fails Fit at train0, which is undefined.
- `trail_color`: the trail's color
    - `concept`: stored, 1
    - `trail_color=OutNewColor`: fails Fit at train0, for the same reason as `frame_color=OutNewColor`.
- `halo-width` & `halo-measure`, `halo-width` & `halo-shape`, `halo-width` & `layer-order`, `halo-width` & `trail-stop`, `halo-width` & `square_color`, `halo-width` & `frame_color`, `halo-width` & `trail_color`, `odd-side` & `halo-measure`, `odd-side` & `halo-shape`, `odd-side` & `layer-order`, `odd-side` & `trail-stop`, `odd-side` & `square_color`, `odd-side` & `frame_color`, `odd-side` & `trail_color`, `halo-measure` & `halo-shape`, `halo-measure` & `layer-order`, `halo-measure` & `trail-stop`, `halo-measure` & `square_color`, `halo-measure` & `frame_color`, `halo-measure` & `trail_color`, `halo-shape` & `layer-order`, `halo-shape` & `trail-stop`, `halo-shape` & `square_color`, `halo-shape` & `frame_color`, `halo-shape` & `trail_color`, `layer-order` & `square_color`, `layer-order` & `frame_color`, `layer-order` & `trail_color`, `trail-stop` & `square_color`, `trail-stop` & `frame_color`, `trail-stop` & `trail_color`, `square_color` & `frame_color`, `square_color` & `trail_color`, `frame_color` & `trail_color`: the two branches' changes applied together
- `layer-order` & `trail-stop`: the two branches' changes applied together, except in the cases below
    - `$SquaresUnderAll` & `$TrailStopsAtSquare`: the trail stops above each square it meets, so it paints no square cell. The model is `$HaloOverSquares` & `$TrailStopsAtSquare`, which is equivalent to `$HaloOverSquares`.
    - `$SquaresUnderAll` & `$TrailStopsAtHalo`: the trail stops at the halo around each square it meets, so it paints no square cell. The model is `$HaloOverSquares` & `$TrailStopsAtHalo`.
    - `$HaloOverSquares` & `$TrailStopsAtSquare`: equivalent to `$HaloOverSquares`, for the reason `$TrailStopsAtSquare` is equivalent to the concept.

## Open parameters
- none

## Not formed
- The trail starts below the halo, in place of below the square: the halo covers the cells between, and every branch draws the halo over the trail, so the two readings give one output on every input.
- A trail direction read off each square's place, such as away from its nearest edge: train0's square at rows 7–8, cols 1–2 lies nearest the left and bottom edges, and its trail runs down.
- One stored halo width for every square: train1's output holds halos 1 and 2 wide.
- A derivation of `frame_scale`: no proposer reads an object's size. The dimension proposers measure whole grids, and with `ex_out` empty they give no value.
- A derivation of `trail_dir`: no proposer gives a direction.

## Tickets filed
- none
