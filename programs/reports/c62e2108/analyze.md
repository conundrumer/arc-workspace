# c62e2108

## Concept
- Fits every pair (`work/task/c62e2108/probe.py`, reading `concept`).
- No witness has the verdict `other`.
- The concept case is undefined where two squares' copies write different colors to one cell (`crossing-strips`). The verdict there is `$Overlay`.

## Choice points
- `copy-layering`
    - `concept`: each copy writes every cell of its box, and its hollow cells are written as `background` (`copies-overwrite`). The model is undefined where two copies write different colors to one cell.
    - `$Overlay`: replaces `copies-overwrite`. A copy writes only its shape's cells, and the cells of a marker that a square repeats toward turn `background`. The model is undefined where two copies write different shape colors to one cell. It fits every pair. Witness `crossing-strips`: it breaks no scene claim. Plausibility `borderline`, verdict `$Overlay`. Invariant broken: no two squares' strips cross.
- `reach`
    - `concept`: the copies run to the grid edge, and the last copy is cut off there.
    - `$ToMarker`: replaces the end of `repeat-toward-marker`. The copies run to the marker's line, that line included, and are cut off there. It fits every pair. Witness `interior-marker`: it breaks `edge-markers`. Plausibility `borderline`, verdict `$ToMarker`. Invariant broken: every marker lies on a grid edge.
- `tile-source`
    - `concept`: the tile is the square's own box, copied from the input, and the stride is the box's extent plus `gap`.
    - `$StoredTile`: replaces the copied tile in `repeat-toward-marker` with a parameter `tile`, a stored 4×4 hollow-square mask drawn in the square's color. The stride is 4 plus `gap`. It fits every pair. Witness `small-square`: at the stored `side` 4, it breaks `squares`. Plausibility `variant`, verdict `concept`. Invariant broken: every square has side 4.
- `repeat-form`
    - `concept`: each copy is a translate of the square.
    - `$Mirror`: replaces the translation in `repeat-toward-marker`. Every other copy is reflected across the edge it shares with the copy before it. It fits every pair. Witness `asymmetric-shape`: it breaks `squares` (hollow middle). Plausibility `variant`, verdict `concept`. Invariant broken: every shape is a hollow square, so it is mirror-symmetric.
- `adjacency`
    - `concept`: a square is a 4-connected object of a color other than `background` and `marker`.
    - `$Adj8`: replaces how `squares` finds an object. An object is 8-connected. It fits every pair. Witness `diagonal-blocks`: it breaks `squares`. Plausibility `borderline`, verdict `$Adj8`. Invariant broken: every object is a hollow square outline.
- `marker-owner`
    - `concept`: each square lined up with a marker repeats toward it.
    - `$NearestOnly`: replaces which squares repeat in `repeat-toward-marker`. Of the squares lined up with a marker, only the one nearest to it repeats. It fits every pair. Witness `two-in-line`: it breaks `edge-markers` (exactly one square) and `clear-strip`. Plausibility `borderline`, verdict `$NearestOnly`. Invariant broken: each marker lines up with one square.
- `unmatched-marker`
    - `concept`: a marker that lines up with no square keeps its color (`keep-rest`).
    - `$EraseMarkers`: adds a rule. Every marker cell that no copy covers turns `background`. It fits every pair. Witness `stray-marker`: it breaks `edge-markers`. Plausibility `foreign`, verdict `$EraseMarkers`. Invariant broken: every marker lines up with a square.
- `marker`
    - `concept`: stored, 1.
    - `marker=RarestColor`: the marker is the input's rarest color. Where colors tie, it gives one output for each tied color. It fits every pair. Witness `marker=RarestColor`: it breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `marker=DominantColor`: it gives 0, and it fails Fit at train0.
    - `marker=SharedColor`, `marker=VanishedColor`: on one input alone, each gives every color of that input. Each fails Fit at train0.
    - `marker=ChangedColor`, `marker=UnchangedColor`, `marker=OutNewColor`: each reads `ex_out`, so on one input alone each gives no value. The model is undefined on every input, and each fails Fit at train0.
- `background`
    - `concept`: stored, 0.
    - `background=DominantColor`: the background is the input's commonest color. It fits every pair. Witness `background=DominantColor`: it breaks no scene claim. Plausibility `borderline`, verdict `concept`. Invariant broken: the background holds most cells of each input.
    - `background=RarestColor`: it gives 1, and it fails Fit at train0.
    - `background=SharedColor`, `background=VanishedColor`: each gives every input color, and each fails Fit at train0.
    - `background=ChangedColor`, `background=UnchangedColor`, `background=OutNewColor`: on one input alone, each gives no value, and each fails Fit at train0.
- `gap`
    - `concept`: stored, 0.
    - `gap=<each number proposer>` (`ConstInDim`, `ConstInDimAxis`, `TileCount`, `TileDim`, `Period`, `SepTileCount`, `SepTileCountAxis`, `SepTileDim`, `SepThickness`, `ScaleRatio`, `DimDiff`, `DivisorRatio`, `ConstOutDim`): on train0's input alone, each gives no value or only positive values. Each fails Fit at train0, whose copies abut.
- `copy-layering` & `reach`, `copy-layering` & `tile-source`, `copy-layering` & `repeat-form`, `copy-layering` & `adjacency`, `copy-layering` & `marker-owner`, `copy-layering` & `unmatched-marker`, `copy-layering` & `marker`, `copy-layering` & `background`, `copy-layering` & `gap`, `reach` & `tile-source`, `reach` & `repeat-form`, `reach` & `adjacency`, `reach` & `marker-owner`, `reach` & `unmatched-marker`, `reach` & `marker`, `reach` & `background`, `reach` & `gap`, `tile-source` & `repeat-form`, `tile-source` & `adjacency`, `tile-source` & `marker-owner`, `tile-source` & `unmatched-marker`, `tile-source` & `marker`, `tile-source` & `background`, `tile-source` & `gap`, `repeat-form` & `adjacency`, `repeat-form` & `marker-owner`, `repeat-form` & `unmatched-marker`, `repeat-form` & `marker`, `repeat-form` & `background`, `repeat-form` & `gap`, `adjacency` & `marker-owner`, `adjacency` & `unmatched-marker`, `adjacency` & `marker`, `adjacency` & `background`, `adjacency` & `gap`, `marker-owner` & `unmatched-marker`, `marker-owner` & `marker`, `marker-owner` & `background`, `marker-owner` & `gap`, `unmatched-marker` & `marker`, `unmatched-marker` & `background`, `unmatched-marker` & `gap`, `marker` & `background`, `marker` & `gap`, `background` & `gap`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The square repeats away from its marker: the pairs separate it. In train0, the square repeats toward its markers.
- Copies share an edge (stride `side` − 1): the pairs separate it. In train0 row 3, the copies abut with no shared column.
- Only whole copies are drawn: the pairs separate it. In train0, the right strip ends in a copy that col 16 cuts off.
- A marker sends every square on its side toward it: the pairs separate it. In train1, the bottom marker at cols 2–5 repeats only the square in those columns.
- Copies take a color other than the square's: the pairs separate it. Every output's copies carry their square's color.

## Tickets filed
- 10-514_task_c62e2108_analyze.md
