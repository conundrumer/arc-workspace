# ba9d41b8

## Concept
- The concept case fits every pair (train0, train1, train2, test0) at `background` 0, `anchor` top-left, `hole_parity` 0. Only top-left fits as `anchor`: train0 (an 8x10 rectangle) rules out top-right and bottom-left, and the color-3 rectangle of train2 (7x8) rules out bottom-right. Of the 16 stored 2x2 motifs, only the checkerboard fits.
- In the concept case's model, an object is a 4-connected set of cells of one color other than `background`, and its inside is its cells strictly inside its bounding box. On a solid rectangle, this inside and the outline in `outline-kept` are the rectangle's inside and outline.
- No witness has the verdict `other`.

## Choice points
- `object-colors`
    - `concept`: one object is a 4-connected set of cells of one color
    - `$AnyColorObjects`: replaces the object reading under `solid-rectangles`: one object is a 4-connected set of cells of any colors other than `background`. It reads no new parameter and is defined on every input. It fits every pair. Witness `touching-colors`: two 5x5 rectangles of colors 3 and 4 touch side by side. It breaks `solid-rectangles` (no two touch) and the invariant that a background cell separates any two rectangles. It stands at the stored assignment. Plausibility `borderline`, verdict `concept`.
- `object-adjacency`
    - `concept`: cells join by 4-adjacency
    - `$Diagonal8Objects`: replaces the object reading under `solid-rectangles`: cells join by 8-adjacency (Components8). It reads no new parameter and is defined on every input. It fits every pair. Witness `corner-touch`: two 5x5 rectangles of color 2 meet at one corner. It breaks `solid-rectangles` (no two touch) and the invariant that no two rectangles meet, even at a corner. It stands at the stored assignment. Plausibility `borderline`, verdict `concept`.
- `inside`
    - `concept`: an object's cells strictly inside its bounding box
    - `$RimInside`: replaces `outline-kept` and the inside in `checker-holes`: the outline is the object's rim (Rim, with off-frame counting as outside), and the inside is its cells at depth 1 or more. It reads no new parameter and is defined on every input. It fits every pair. Witness `l-shape`: an L of color 2. It breaks `solid-rectangles` (each object is a filled rectangle) and the invariant that every object fills its bounding box. It stands at the stored assignment. Plausibility `borderline`, verdict `$RimInside`.
- `parity-origin`
    - `concept`: the distance sum is counted from the object's `anchor` corner
    - `$GridFrame`: replaces `checker-holes`: the distance sum is counted from the grid's `anchor` corner. Its `anchor` is stored as top-right, and it is distinct from the concept's `anchor` (top-left) because no value fits both cases here. It is defined on every input. It fits every pair: in every pair, each rectangle's top-left corner lies at an even distance sum from the grid's top-right corner, so the two origins give the same holes. Witness `grid-offset`: a 5x5 rectangle at (1,1) in a 10x10 grid, an odd distance sum from (0,9). It breaks no scene claim. It stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
- `hole-pattern`
    - `concept`: a cell is a hole when its distance sum has the parity `hole_parity`
    - `$StoredTile`: replaces `checker-holes` and `hole_parity`: a stored 2x2 motif `tile` (the hole cells of the motif) repeats from the `parity-origin` corner, and an inside cell is a hole when its cell of the motif is one. It is defined on every input. It fits every pair at the checkerboard motif. At the stored assignment its model gives the concept's output on every input. Witness `striped-tile`: a 6x6 rectangle of color 2. It stands at `tile` reassigned to the motif's top row, `[[0,0],[0,1]]`. It breaks no scene claim. Plausibility `ordinary`, verdict `$StoredTile`.
    - `$LineDashes`: replaces `checker-holes`: along each inside row, holes and kept cells alternate in runs of stored lengths from the row's first inside cell, with one phase for every row. It fails Fit at train0: at train0 output (5,5) the first inside cell of row 5 is a hole, and at (6,5) the first inside cell of row 6 keeps its color.
- `punched-objects`
    - `concept`: every object is punched
    - `$ColorSelect`: adds a lookup table of the colors whose objects are punched, under `checker-holes`. It fails Fit at test0: the keys 7 and 6 occur in no train pair.
- `background`
    - `concept`: `background` is stored as 0
    - `background=DominantColor`: derives `background` as the commonest color of the input. It is undefined on no input, and on a tie it gives each tied color. It fits every pair. Witness `background=DominantColor`: a 6x6 rectangle of color 2 in a 7x7 grid. It breaks no scene claim, and it breaks the invariant that `background` is the commonest color of each input. It stands at the stored assignment. Plausibility `variant`, verdict `concept`.
    - `background=SharedColor`: derives `background` as each color of the input. It fails Fit at train0: the input alone gives 0 and 2, and the model gives two grids.
    - `background=RarestColor`: derives `background` as the rarest color of the input. It fails Fit at train0: the input alone gives 2.
- `object-colors` & `object-adjacency`, `object-colors` & `inside`, `object-colors` & `parity-origin`, `object-colors` & `hole-pattern`, `object-colors` & `punched-objects`, `object-colors` & `background`, `object-adjacency` & `inside`, `object-adjacency` & `parity-origin`, `object-adjacency` & `hole-pattern`, `object-adjacency` & `punched-objects`, `object-adjacency` & `background`, `inside` & `parity-origin`, `inside` & `hole-pattern`, `inside` & `punched-objects`, `inside` & `background`, `parity-origin` & `hole-pattern`, `parity-origin` & `punched-objects`, `parity-origin` & `background`, `hole-pattern` & `punched-objects`, `hole-pattern` & `background`, `punched-objects` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Hole color as a parameter of its own: the holes show the field, so the hole color follows from `background` in every variant task (Redundant value).
- A derived `anchor` (for example the rectangle's corner nearest the grid's top-left): no proposer derives a corner. A program that fixes the corner fixes task data that a D4 element changes.
- A checkerboard counted from the inside's first cell: the inside's top-left cell is one step from the rectangle's corner on each axis, so the parity is the same, and the model is the concept's.
- A period other than 2, or a size threshold for which objects are punched: no pair shows another period or an object left unchanged. `$StoredTile` is the stored-motif reading of the pattern.

## Tickets filed
- 10-454_task_ba9d41b8_analyze.md
