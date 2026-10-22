# ac6f9922

## Concept
- Fits every pair (train0–2, test0). Each claim has a relational form: the background is the color of the grid edge, the lattice is the commonest other color, a window is a region of non-lattice cells that the lattice closes off from the grid edge (`Closed`), and windows group into rows and columns by their exact extents. The concept has no parameters: the background, the lattice color and the window grid are derived from each input.
- No witness has the verdict `other`, so the concept case has no witness of its own.
- The probe `probe.py` runs the concept and each fitting branch on the pairs, and `make_witnesses.py` runs them on the witnesses.

## Choice points
- `background`: how the background color is found
    - `concept`: the color of the grid edge, which is one color
    - `$CommonestBackground`: the background is the commonest color of the input; it replaces how `framed-lattice` finds the background; undefined where two colors tie for commonest. Fits every pair. Witness `edge-lattice`: a 2×2 lattice whose outer bars lie on the grid edge, with windows that outnumber its bars. It breaks `framed-lattice`, at the stored assignment. Plausibility `variant`, verdict `$CommonestBackground`. Invariant broken: the background shows along every grid edge, and the lattice touches no edge.
- `cell-unit`: what one output cell stands for
    - `concept`: a window, a region the lattice closes off
        - `window-region`: which cells make up a window
            - `concept`: every non-lattice cell of a region the lattice closes off, marks included
            - `$BgRegionWindows`: a window is a connected region of background cells closed off from the grid edge, and its marks are the non-lattice cells inside its bounding box; it replaces `window-grid`'s windows. Fits every pair. Witness `split-window`: marks that span the full width of the two top windows, so each window's background splits into two strips. It breaks `one-mark` (the mark touches the window's edges), at the stored assignment. Plausibility `borderline`, verdict `concept`. Invariant broken: a ring of background separates each mark from the lattice.
        - `window-grouping`: how windows group into rows and columns
            - `concept`: windows with the same top and bottom rows form one row, and windows with the same left and right columns form one column
            - `$WindowBands`: windows whose row extents overlap merge into one band, and the same holds for columns; it replaces `window-grid`'s rows and columns. Fits every pair. Witness `staggered-window`: one window a row shorter than the window beside it. It breaks `window-grid`, at the stored assignment. Plausibility `borderline`, verdict `$WindowBands`. Invariant broken: the windows in one row share their top and bottom rows.
    - `$DividerTiles`: an output cell stands for a tile that the lattice's full lines cut within the lattice's bounding box, and the tile takes its one non-background, non-lattice color, or the background; it replaces `window-grid` and `window-picture`; undefined where a tile holds two mark colors. Fits every pair. Witness `missing-window`: the bottom-right window of the 2×2 lattice is filled with the lattice color. It breaks `window-grid`, at the stored assignment. Plausibility `borderline`, verdict `$DividerTiles`. Invariant broken: every place of the window grid holds a window.
    - `$MarkBands`: an output cell stands for a mark, and the marks group into bands by their own extents (the 0a1d4ef5 reading); it replaces `window-grid` and `window-picture`. Fails Fit at train1: its one mark gives a 1×1 output, and the output is 2×2.
- `empty-color`: the color of an empty window's cell
    - `concept`: the background, which is also the color that fills each window
    - `$WindowFill`: a window may be filled with any non-lattice color, and an empty window gives its own fill, which is the one color its cells take where they touch the lattice; it replaces `window-grid`'s windows of the background color and `mark-color`'s empty case; undefined where a window's cells take two colors along the lattice. Fits every pair. Witness `window-fill`: train1 with each window filled with 6 while the field outside stays 4. It breaks `window-grid`, at the stored assignment. Plausibility `borderline`, verdict `$WindowFill`. Invariant broken: the windows have the color of the field outside the lattice.
    - `$StoredEmpty`: a stored color for an empty window; it replaces `mark-color`'s empty case. Fails Fit at train1: train0's empty cells are 8, train1's are 4.
    - `$LatticeEmpty`: an empty window gives the lattice color; it replaces `mark-color`'s empty case. Fails Fit at train0: the empty cells are 8, and the lattice is 1.
- `extent`: the output's extent
    - `concept`: one row per row of windows and one column per column of windows
    - `$StoredExtent`: a stored output extent; it replaces `window-picture`'s extent. Fails Fit at train2: train0 and train1 give 2×2, and train2 gives 2×3.
- `background` & `cell-unit`, `background` & `empty-color`, `background` & `extent`, `background` & `window-region`, `background` & `window-grouping`, `cell-unit` & `empty-color`, `cell-unit` & `extent`, `empty-color` & `extent`, `empty-color` & `window-region`, `empty-color` & `window-grouping`, `extent` & `window-region`, `extent` & `window-grouping`, `window-region` & `window-grouping`: the two branches' changes applied together

## Open parameters
none

## Not formed
- An orientation for the output picture (a D4 transform of the window grid): the task distinguishes no orientation, and every pair keeps the windows' layout as it is (train0 puts 2 top right and 3 bottom left, in both input and output).
- A rule for a window with two mark colors, or with a mark of the lattice color: no pair, sibling solver header or variant task gives a reading for such a window. Every reading formed is undefined there.

## Tickets filed
none
