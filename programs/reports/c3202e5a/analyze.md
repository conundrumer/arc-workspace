# c3202e5a

## Concept
- The concept fits every pair. On each input, exactly one tile holds marks of one color, and the crop of that tile is the output.
- No witness has verdict `other` without a branch below listing it. The generator applies the rule as the concept file states it: it keeps the one tile whose marks are of a single color.
- Divider-colored cells inside a tile count as marks. In train1 and train2, a second tile holds marks of one color besides the divider color (train1 rows 6–10, cols 12–16: 3 and 4; train2 rows 0–2, cols 20–22: 5 and 6; train2 rows 4–6, cols 0–2: 1 and 5), and only that reading keeps one candidate tile.
- Probes: `work/task/c3202e5a/probe_select.py` and `work/task/c3202e5a/models.py` (`models.py fit` runs each branch's model on the pairs; `models.py` writes `witnesses.json`).

## Choice points
- `tile-selection`
    - `concept`: the one tile whose marks have exactly one color; undefined where no tile or several tiles do.
    - `$FewestColors`: replaces the selection in `crop-mono-tile` with the tile with the fewest mark colors, a tile with no marks counting zero; undefined on a tie for fewest. Fits every pair. Witness `empty-tile`: it breaks `one-mono-tile`, plausibility `borderline`, verdict `concept`, and it breaks the invariant that every tile but one holds marks of two or more colors. Witness `solid-two-color-tile` separates it from `$NoBackground`: this branch is defined there and `$NoBackground` is not. Its plausibility is `borderline`, verdict `concept`, and it breaks the invariant that every tile holds background cells.
    - `$MostOfOneColor`: replaces the selection in `crop-mono-tile` with the tile holding the most cells of one mark color; undefined on a tie. Fits every pair. Witness `sparse-mono-tile`: it breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$NoBackground`: replaces the selection in `crop-mono-tile` with the tile with the fewest distinct colors over all its cells, background counted as a color, so the selection reads no `background`; undefined on a tie. Fits every pair. Witness `empty-tile` (as for `$FewestColors`). Witness `solid-tile` separates it from `$FewestColors`: this branch is defined there and `$FewestColors` is not. It breaks `one-mono-tile`, plausibility `foreign`, verdict `other` (the sparse one-color tile), and it breaks the invariant that exactly one tile holds marks of one color.
    - `$MostMarks`: the tile with the most marks. Fails Fit at train0, where it keeps rows 18–22, cols 6–10.
    - `$FewestMarks`: the tile with the fewest marks. Fails Fit at train0, where it keeps rows 0–4, cols 6–10.
- `divider-ink`
    - `concept`: divider-colored cells inside a tile count as marks.
    - `$IgnoreDividerInk`: adds the claim that divider-colored cells inside a tile are not marks. Fails Fit at train1, where rows 6–10, cols 12–16 and rows 18–22, cols 6–10 both hold marks of one color.
- `tiling-spacing`
    - `concept`: the tiles are the spans between the full divider lines, at any spacing.
    - `$EqualTiles`: replaces the read of `divider-tiling` with equal square tiles, cut at the count the lines give; undefined where the lines are unevenly spaced. Fits every pair. Witness `uneven-tiling` (this branch undefined): it breaks `divider-tiling`, plausibility `variant`, verdict `concept`, and it breaks the invariant that the lines are evenly spaced. No witness exists on which it is defined and differs: where it is defined, its output is the concept's, so it fails Subsumption.
        - `tile-extent`
            - `concept`: the tile size and count derive from the divider lines.
            - `tile_size=stored`: fails Fit at train2, with tile size 3 against 5 in train0.
            - `tile_count=stored`: fails Fit at train2, with 6 tiles per axis against 4 in train0.
- `divider-color`
    - `concept`: derived on each input as the color of its full one-color lines.
    - `divider_color=stored`: fails Fit at train1, with divider color 3 against 8 in train0.
- `background`
    - `concept`: stored, 0.
    - `background=DominantColor`: the commonest color of the input. Fits every pair. Witness `background=DominantColor`: it breaks no scene claim, plausibility `borderline`, verdict `concept`, and it breaks the invariant that 0 is the commonest color of every input.
    - `background=RarestColor`: fails Fit at train1, where colors 1, 5, 8 and 9 tie for rarest.
    - `background=SharedColor`: fails Fit at train0, where it gives every color of the input, so no single background.
- `output-frame`
    - `concept`: the tile alone.
    - `$FramedTile`: the tile with the divider ring around it, as in 38007db0's header. Fails Fit at train0, where the output is 5×5 and the framed tile is 7×7.
- `tile-selection` & `divider-ink`, `tile-selection` & `tiling-spacing`, `tile-selection` & `divider-color`, `tile-selection` & `background`, `tile-selection` & `output-frame`, `divider-ink` & `tiling-spacing`, `divider-ink` & `divider-color`, `divider-ink` & `background`, `divider-ink` & `output-frame`, `tiling-spacing` & `divider-color`, `tiling-spacing` & `background`, `tiling-spacing` & `output-frame`, `divider-color` & `background`, `divider-color` & `output-frame`, `background` & `output-frame`: the two branches' changes applied together
    - `$MostOfOneColor & $IgnoreDividerInk` fits every pair. Witness `divider-ink-heavy` separates it from `$MostOfOneColor`: it breaks no scene claim, plausibility `ordinary`, verdict `concept`. Witness `sparse-mono-tile` separates it from the concept.
    - `$FewestColors & $IgnoreDividerInk` and `$NoBackground & $IgnoreDividerInk` fail Fit at train1, with the same two one-color tiles as `$IgnoreDividerInk`.

## Open parameters
none

## Not formed
none

## Tickets filed
none
