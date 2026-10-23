# e734a0e8

## Concept
- The concept fits every pair: train0, train1 and test0 each give the expected output (probe `work/task/e734a0e8/probe.py`).
- The program reads a tile as marked when it holds a `divider_color` cell and no cell of a color other than `background_color` and `divider_color`. The source is the one tile that holds such another color. A marked tile takes every cell of the source at the same place in the tile, so the marker cell is covered.
- The concept rule is the rule as the generator applies it. It approximates nothing.
- No witness has the verdict `other`.
- The witness `divider-cell-in-source` goes against the concept, with the verdict `$OverlayDrawing` (see that branch).

## Choice points
- `background-color`
    - `concept`: `background_color` stored as `7`
    - `background_color=DominantColor`: replaces the stored `background_color` of `blank-tiles` and `one-source` with the commonest color of the input alone. It is undefined where two colors tie for the commonest. It fits every pair.
        - witness `background_color=DominantColor`: train1 with the background `8` in place of `7`. That input breaks `blank-tiles` and `one-source` at the stored `background_color` `7`. The branch stamps the copies. The concept finds a source in every tile and is undefined. Plausibility `variant`, verdict `background_color=DominantColor`. Invariant broken: every input has the background `7`.
- `divider-color`
    - `concept`: `divider_color` stored as `0`
    - `$DividerFromLines`: replaces the stored `divider_color` of `divider-tiling` with the one color, other than `background_color`, that fills a full row or a full column of the input. It is undefined where no such line exists, or where the lines have more than one color. It fits every pair.
        - witness `$DividerFromLines`: train1 with the divider lines and markers `5` in place of `0`. That input breaks `divider-tiling` at the stored `0`. The branch stamps the copies. The concept finds no line, takes the whole grid as one source tile with no marked tile, and returns the input. Plausibility `variant`, verdict `$DividerFromLines`. Invariant broken: every input has `0` dividers.
- `marker-color`
    - `concept`: the marker cell has `divider_color`
    - `$MarkerColor`: adds the parameter `marker_color`, stored as `0`. It replaces `center-markers` (the marker cell has `marker_color`) and `one-source` (the source holds a color other than `background_color`, `divider_color` and `marker_color`). It is undefined where the concept is undefined. It fits every pair.
        - witness `marker-color`: train1 with the markers `5` and the dividers `0`. That input breaks `center-markers` and `one-source`. The witness stands at `marker_color` = `5`. The branch stamps the copies. The concept takes each tile with a `5` for a source and is undefined. Plausibility `variant`, verdict `$MarkerColor`. Invariant broken: in every input, the marker cells have the divider color.
- `marker-place`
    - `concept`: a `divider_color` cell anywhere in a tile marks the tile, and the copy covers the whole tile
    - `$MarkerAtCenter`: replaces the marked tile of `stamp-marked` with a tile whose center cell has `divider_color`. It is undefined where a tile has an even side. It fits every pair.
        - witness `off-center-marker`: train1 with the marker of the tile at rows 4–6, cols 4–6 moved from (5,5) to (4,4). That input breaks `center-markers`. The branch leaves that tile as it is. Plausibility `borderline`, verdict `concept`. Invariant broken: every marker is at its tile's center.
    - `$MarkerAnchors`: replaces the placement of `stamp-marked`. The copy shifts so that the source tile's center lands on the marker cell, and the copy is clipped to the marked tile. It is undefined where a marked tile holds more than one marker cell, or where the source tile has an even side. It fits every pair.
        - witness `off-center-marker`: the same witness. The branch gives `2` at (4,4) and (5,4), and keeps the rest of that tile. Plausibility `borderline`, verdict `concept`. Invariant broken: every marker is at its tile's center.
- `copy-content`
    - `concept`: every cell of the source tile is copied
    - `$OverlayDrawing`: replaces `stamp-marked`. Each marked tile takes the source's cells, and each `divider_color` cell of the source arrives as `background_color`. It is undefined where the concept is undefined. It fits every pair.
        - witness `divider-cell-in-source`: train1 with a `0` at (1,0) in the source tile. That input breaks `source-unmarked`. The concept copies that `0` to (5,4), (9,4) and (9,8). The branch keeps `7` there. Plausibility `borderline`, verdict `$OverlayDrawing`: the generator's dots mark tiles and are not part of the drawing. Invariant broken: no source tile holds a `0` cell.
- `source-choice`
    - `concept`: the one tile that holds a color other than `background_color` and `divider_color`
    - `$SourceByCount`: replaces `one-source`. Of the tiles that hold such a color, the source is the one with the most cells of such colors. It is undefined where two of those tiles tie. It fits every pair.
        - witness `second-drawn-tile`: train1 with the marker of the tile at rows 8–10, cols 8–10 replaced by a `3` at (9,8). That input breaks `one-source`. The branch copies the `2` drawing into the two marked tiles. The concept finds two sources and is undefined. Plausibility `borderline`, verdict `$SourceByCount`. Invariant broken: every input has one drawn tile.
- `tile-size`
    - `concept`: the tiles are the spans between the divider lines
    - `$TileDimStored`: adds the parameter `tile_dim`, the side of every tile. It replaces `divider-tiling` with tiles of that stored side, and is undefined where a tile has another side. It fails Fit: at `5` it fails train1, and at `3` it fails train0 and test0.
- `background-color` & `divider-color`, `background-color` & `marker-color`, `background-color` & `marker-place`, `background-color` & `copy-content`, `background-color` & `source-choice`, `background-color` & `tile-size`, `divider-color` & `marker-color`, `divider-color` & `marker-place`, `divider-color` & `copy-content`, `divider-color` & `source-choice`, `divider-color` & `tile-size`, `marker-color` & `marker-place`, `marker-color` & `copy-content`, `marker-color` & `source-choice`, `marker-color` & `tile-size`, `marker-place` & `copy-content`, `marker-place` & `source-choice`, `marker-place` & `tile-size`, `copy-content` & `source-choice`, `copy-content` & `tile-size`, `source-choice` & `tile-size`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Stamp every blank tile: in train0 the unmarked blank tiles stay blank, for example rows 0–4, cols 0–4. A reading that stamps them fails train0 and has no case.
- Stored tile count: train0 has 4 tiles per axis, and train1 and test0 have 3. A stored count fails Fit, as `$TileDimStored` does, and it is not a separate branch.
- Stored drawing color: the drawing is `9` in train0, `2` in train1 and `4` in test0. The program reads that color from the source tile and stores no value for it.

## Tickets filed
- none
