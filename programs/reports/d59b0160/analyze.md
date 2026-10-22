# d59b0160

## Concept
- The concept fits every train pair and the test pair: the legend colors are {4, 1, 2}, {9, 5, 6}, {6, 1, 8} and {2, 5, 4}, and exactly the panels holding all of them are erased to `background` (`probe.py`).
- No witness has the verdict `other`.
- The concept is undefined on an input with no divider L at `key_corner`.

## Choice points
- `erase-test`: which panels are erased
    - `concept`: a panel whose colors include every legend color (`erase-full-panel`)
    - `$LegendMultiset`: replaces `erase-full-panel`: a panel is erased when it holds at least as many cells of each legend color as the legend does; undefined where the concept is. Fits every pair. Witness `legend-repeat`: breaks `legend-corner` (distinct legend colors); `borderline`, verdict `concept`; breaks the invariant that the legend's colored cells have distinct colors.
    - `$StoredLegendCount`: replaces `erase-full-panel`: a panel is erased when it holds at least `legend_need` distinct legend colors, `legend_need` stored as 3; undefined where the concept is. Fits every pair. Witness `four-color-legend`: breaks no scene claim; `variant`, verdict `concept`; breaks the invariant that every legend holds 3 colored cells.
    - `$ExactColorSet`: replaces `erase-full-panel`: a panel is erased when its colors other than `panel_fill` are exactly the legend colors. Fails Fit at train0: the panel at rows 6–9, cols 3–10 also holds 9, 5 and 8, and is erased.
    - `$AnyLegendColor`: replaces `erase-full-panel`: a panel is erased when it holds some legend color. Fails Fit at train0: the panel at rows 0–4, cols 7–9 holds 4, and is kept.
    - `$LegendLayoutMatch`: replaces `erase-full-panel`: a panel is erased when the legend's colored cells, in their layout, occur in it. Fails Fit at train0: the panel at rows 1–5, cols 12–14 holds 4, 1, 2 at (2,13), (3,14), (4,13), not in the legend's layout (0,0), (0,2), (2,0), and is erased.
- `panel-adjacency`: which cells join one panel
    - `concept`: 4-adjacency among non-`background` cells (`panels`)
    - `$Adjacency8`: replaces `panels`: 8-adjacency, so panels that touch at a corner are one panel; undefined where the concept is. Fits every pair. Witness `diagonal-touch`: breaks `panels` (separated by `background`); `borderline`, verdict `concept`; breaks the invariant that panels are apart by at least one `background` cell on every side and corner.
- `panel-extent`: which cells an erased panel covers
    - `concept`: the panel's connected cells
    - `$PanelBbox`: replaces `erase-full-panel`: an erased panel's bounding box becomes `background`; undefined where the concept is. Fits every pair. Witness `l-shaped-panel`: breaks `panels` (rectangles); `borderline`, verdict `concept`; breaks the invariant that every panel fills its bounding box.
- `legend-place`: where the legend stands
    - `concept`: the stored corner `key_corner`
    - `$LegendAnyCorner`: replaces `legend-corner`: `key_corner` is derived as the one corner at which a divider L walls off a box; undefined where no corner, or more than one, has such an L. Fits every pair. Witness `legend-other-corner`: breaks `legend-corner` at `key_corner` TL; `variant`, verdict `$LegendAnyCorner`; breaks the invariant that the legend stands at the top-left corner.
- `legend-extent`: how far the legend box reaches
    - `concept`: the box the divider L walls off (`legend-corner`)
    - `$FixedLegendSize`: replaces `legend-corner`: the legend is a stored `legend_size` × `legend_size` box at `key_corner`, `legend_size` stored as 3, with the 1-wide L beyond it skipped; undefined on no input the concept is defined on. Fits every pair. Witness `larger-legend`: breaks no scene claim; `variant`, verdict `concept`; breaks the invariant that the legend box is 3×3.
- `background`: where the background color comes from
    - `concept`: stored, 7
    - `background=DominantColor`: the commonest color of the input. Fails Fit at train2: 0 has 108 cells and 7 has 107.
- `erase-test` & `panel-adjacency`, `erase-test` & `panel-extent`, `erase-test` & `legend-place`, `erase-test` & `legend-extent`, `erase-test` & `background`, `panel-adjacency` & `panel-extent`, `panel-adjacency` & `legend-place`, `panel-adjacency` & `legend-extent`, `panel-adjacency` & `background`, `panel-extent` & `legend-place`, `panel-extent` & `legend-extent`, `panel-extent` & `background`, `legend-place` & `legend-extent`, `legend-place` & `background`, `legend-extent` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Deriving `divider`: no proposer gives one color from one input; SharedColor gives every color of the input, and UnchangedColor and ChangedColor read the outputs, which a run does not have.
- A stored erase color apart from `background`: it equals `background` in every variant task, so it is derived data.
- Reading `panel_fill`: no rule needs it, because a panel is found as a component of non-`background` cells.

## Tickets filed
- none
