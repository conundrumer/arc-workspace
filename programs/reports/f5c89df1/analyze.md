# f5c89df1

## Concept
- Fits every pair (train0–2, test0): each marker gets a copy of the shape, placed by the shape's offsets from the anchor, on a fresh background field (`work/task/f5c89df1/check_concept.py`, `work/task/f5c89df1/probe.py`).
- No witness has verdict `other`. The rule as the generator applies it is the concept file's `stamp-at-markers` and `erase-source` as written: each cell's offset from the one anchor, laid off from each marker. This is relational (positions, offsets, colors), so no approximation stands in for it.
- The probes found no reading that fits the pairs and differs from the concept on a scene the generator readily draws, except `$Opaque` on overlapping copies (`overlap-hole`), and there `$Opaque` is undefined.

## Choice points
- `copy-extent` (what one stamp paints)
    - `concept`: only the shape's inked cells
    - `$Opaque`: replaces `stamp-at-markers`. Each stamp paints the shape's whole bounding box, with background in its holes. Undefined where one copy's hole lands on another copy's ink. Fits every pair. Witness `overlap-hole` (train2 input with a second marker at (5,6)): stored assignment, breaks no scene claim, `ordinary`, verdict `concept`. `$Opaque` is undefined on it. Wherever `$Opaque` is defined its holes land on no ink, so its output is the concept's. It is subsumed by the concept and fails Subsumption, and no witness exists where it is defined and differs.
- `shape-reach` (which cells form the shape)
    - `concept`: every non-background cell other than the anchor and the markers
    - `$AnchorComponent`: replaces `pattern`. The shape is the 8-connected component, among non-background non-marker cells, that holds the anchor. Under 4-adjacency it fails train1, where (5,4) and (5,8) touch the rest only at corners. Fits every pair. Witness `detached-piece` (train0 input plus an 8 at (1,5)): stored assignment, breaks no scene claim, `variant`, verdict `concept`. It breaks the input invariant that the shape is one 8-connected piece holding its anchor.
- `shape-color` (which colors the shape takes)
    - `concept`: any color other than background, anchor and marker
        - `stamp-color` (the color a stamped cell gets)
            - `concept`: the color of its source cell
            - `$PaintStored`: replaces `stamp-at-markers`. Every stamped cell paints the stored `pattern_color`, which moves from a scene parameter into Parameters. Fits every pair. Witness `second-shape-color` (train0 input with (3,5) drawn in 4): stored assignment, breaks `pattern`, `variant`, verdict `concept`. It breaks the input invariant that the shape is one color.
    - `$ColorShape`: replaces `pattern`. The shape is the cells of the stored `pattern_color`, and cells of other colors are wiped and not stamped. Fits every pair. Witness `second-shape-color`: stored assignment, breaks `pattern`, `variant`, verdict `concept`. It breaks the input invariant that the shape is one color.
- `frame-exit` (a copy reaching past the grid)
    - `concept`: the copy is clipped to the grid
    - `$NoClip`: adds the requirement that every copy lies inside the grid, and is undefined where one does not. Fits every pair. Witness `copy-past-edge` (train2 input with the marker moved to (2,4)): stored assignment, breaks `copies-in-frame`, `variant`, verdict `concept`. It breaks the input invariant that each copy fits the grid. `$NoClip` is undefined there and equals the concept wherever it is defined, so it is subsumed and fails Subsumption.
- `source` (what happens to the original drawing)
    - `concept`: wiped
    - `$KeepSource` (from 2c737e39): replaces `erase-source`. The input stays and the stamps paint over it. Fails train0, where the 3 at (4,5) and the 2s survive.
- `placement` (which point of the shape lands on a marker)
    - `concept`: the anchor cell
    - `$BoxCenter` (from 88a10436): replaces `stamp-at-markers`. The center of the shape's bounding box lands on the marker, and the model is undefined where that box has an even extent. Fails train2, whose shape box spans 4 rows.
- `orientation` (how a copy is turned)
    - `concept`: translated only
    - `$Reflect`: replaces `stamp-at-markers`. The copy is mirrored across each axis on which the marker is displaced from the anchor. Fails train2, whose copy comes out upside down.
- `anchor-print` (what a copy prints at its marker)
    - `concept`: nothing, so the marker cell is background unless another copy inks it
    - `$StampAnchor`: replaces `stamp-at-markers`. Each copy also prints `anchor_color` on its marker. Fails train0, where (3,4) would be 3.
- `marker-cells` (which cells are markers)
    - `concept`: the cells of the stored `marker_color`
    - `$LoneMarker` (from 88a10436): replaces `markers`. The markers are the ink cells with no 4-neighboring ink. Fails train0, whose 2s touch the 8s.
- `background`
    - `concept`: stored `background`
    - `background=DominantColor`: replaces `background` with the commonest color of the input, and is undefined at a tie. Fits every pair. Witness `background=DominantColor` (3×4 grid `8 8 8 0 / 8 3 2 0 / 8 8 8 0`): stored assignment, breaks no scene claim, `borderline`, verdict `concept`. It breaks the input invariants that every input is 13×13 and that 0 is its commonest color.
- `anchor_color`
    - `concept`: stored `anchor_color`
    - `anchor_color=RarestColor`: replaces `anchor_color` with each color of fewest cells in the input. Fails train2, where 2 and 3 tie at one cell each, so the input has two anchors.
- `copy-extent` & `shape-reach`, `copy-extent` & `shape-color`, `copy-extent` & `frame-exit`, `copy-extent` & `source`, `copy-extent` & `placement`, `copy-extent` & `orientation`, `copy-extent` & `anchor-print`, `copy-extent` & `marker-cells`, `copy-extent` & `background`, `copy-extent` & `anchor_color`, `shape-reach` & `shape-color`, `shape-reach` & `frame-exit`, `shape-reach` & `source`, `shape-reach` & `placement`, `shape-reach` & `orientation`, `shape-reach` & `anchor-print`, `shape-reach` & `marker-cells`, `shape-reach` & `background`, `shape-reach` & `anchor_color`, `shape-color` & `frame-exit`, `shape-color` & `source`, `shape-color` & `placement`, `shape-color` & `orientation`, `shape-color` & `anchor-print`, `shape-color` & `marker-cells`, `shape-color` & `background`, `shape-color` & `anchor_color`, `frame-exit` & `source`, `frame-exit` & `placement`, `frame-exit` & `orientation`, `frame-exit` & `anchor-print`, `frame-exit` & `marker-cells`, `frame-exit` & `background`, `frame-exit` & `anchor_color`, `source` & `placement`, `source` & `orientation`, `source` & `anchor-print`, `source` & `marker-cells`, `source` & `background`, `source` & `anchor_color`, `placement` & `orientation`, `placement` & `anchor-print`, `placement` & `marker-cells`, `placement` & `background`, `placement` & `anchor_color`, `orientation` & `anchor-print`, `orientation` & `marker-cells`, `orientation` & `background`, `orientation` & `anchor_color`, `anchor-print` & `marker-cells`, `anchor-print` & `background`, `anchor-print` & `anchor_color`, `marker-cells` & `background`, `marker-cells` & `anchor_color`, `background` & `anchor_color`, `copy-extent` & `stamp-color`, `shape-reach` & `stamp-color`, `frame-exit` & `stamp-color`, `source` & `stamp-color`, `placement` & `stamp-color`, `orientation` & `stamp-color`, `anchor-print` & `stamp-color`, `marker-cells` & `stamp-color`, `background` & `stamp-color`, `anchor_color` & `stamp-color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Deriving `marker_color`: no input-only proposer gives 2. RarestColor gives 3 on train0, DominantColor gives 0, and SharedColor gives every color of an input. VanishedColor and ChangedColor give {2, 3} but read outputs, which a `@derive` branch does not.
- Deriving `background` or `anchor_color` by another proposer: SharedColor gives every color of an input, and DominantColor gives 0, which is not the anchor color.
- Keeping the original shape but wiping the anchor and markers: train1's output is 0 at the shape cell (3,6) and train2's at the shape row (7,2)–(7,6), so the pairs separate it, as they do `$KeepSource`. In train0 the copies happen to cover the original plus.
- Several anchors, or copies resolving a color conflict: every input has exactly one anchor (`one-anchor`), and overlapping copies carry the one shape color, so no reading of a conflict arises outside `$Opaque` and multicolor shapes.

## Tickets filed
- none
