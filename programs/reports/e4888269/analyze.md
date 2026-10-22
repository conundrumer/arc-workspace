# e4888269

## Concept
- Fits every pair at `order_dir` = `DIR_T` and `source_dir` = `DIR_L`; the evidence fixes both (`DIR_B` and `DIR_R` each fail train0).
- No witness has verdict `other`.
- The rule as the generator applies it is the concept file's rule: the entries apply one after another, so `sequential-replace` has a relational form and no approximation stands in for it.

## Choice points
- `legend-adjacency`
    - `concept`: the legend is a 4-connected group of non-background cells
    - `$Legend8Adj`: replaces `legend`; the legend is the one 8-connected group of non-background cells that holds more than one color; undefined where a non-background cell touches the legend at a corner. Fits every pair. Witness `diagonal-mark`: train0 input with a `3` at (4,2), diagonal to the legend cell (3,1); breaks no scene claim of the concept; `borderline`, breaking the invariant that every non-background cell outside the legend is at least one cell away from it in all eight directions; verdict `concept`. Fails Subsumption: where it is defined, its output is the concept's.
- `legend-locate`
    - `concept`: the legend is the one group that holds more than one color
    - `$LegendByShape`: replaces `legend`; the legend is the one 4-connected group that is a solid two-wide block of two or more entries; undefined where there is none or more than one. Fails Fit at test0: the `6` block at rows 1–3, cols 6–7 and the `4` block at rows 2–3, cols 15–16 are two-wide blocks too.
- `recolor-scope`
    - `concept`: every cell outside the legend
    - `$KeepDivider`: adds a rule that a cell on a row or column that the input fills with one non-background color keeps its color. Fits every pair. Witness `divider-source`: train0 input with the legend cell (1,0) set to `2`, so that the entry `2 → 5` has the divider's color as its source; breaks no scene claim of the concept; `borderline`, breaking the invariant that no legend source is the color of the divider or of a frame line (train divider `2`, test1 divider `4` and test0 frame `3` occur in the legend as targets only); verdict `$KeepDivider`.
    - `$FieldPanelOnly`: replaces `rest-kept`; only the cells of the panel that a divider line cuts off from the legend recolor; undefined where no full line divides the grid. Fails Fit at test0, which has no divider.
    - `$RecolorLegend`: replaces `legend-kept`; the legend's own cells recolor too. Fails Fit at train0: the legend cell (0,0) `1` becomes `7`.
- `entry-combination`
    - `concept`: the entries apply in sequence, each to the colors the earlier ones leave
    - `$ParallelLookup`: replaces `sequential-replace`; each cell takes the target of the first entry whose source is its input color. Fails Fit at train0: (7,18) `1` gives `4`, and the output has `7`.
    - `$ChainToEnd`: replaces `sequential-replace`; each cell follows the entries from its color, by the first entry of each source, until it reaches a color that no entry has as source. Fails Fit at train1: (7,18) `1` gives `7`, and the output has `6`.
- `order-dir-source`
    - `concept`: `order_dir` is stored
    - `$OrderFromNearEdge`: derives `order_dir` as the end of the legend nearer the grid edge along the legend's axis. Fails Fit at test0: the legend at rows 18–24 of 30 reads from the bottom.
- `source-dir-source`
    - `concept`: `source_dir` is stored
    - `$SourceFromNearEdge`: derives `source_dir` as the side of the legend nearer the grid edge across its axis. Fails Fit at test1: the legend at cols 10–11 of 13 takes its source from col 11.
- `legend-adjacency` & `legend-locate`, `legend-adjacency` & `recolor-scope`, `legend-adjacency` & `entry-combination`, `legend-adjacency` & `order-dir-source`, `legend-adjacency` & `source-dir-source`, `legend-locate` & `recolor-scope`, `legend-locate` & `entry-combination`, `legend-locate` & `order-dir-source`, `legend-locate` & `source-dir-source`, `recolor-scope` & `entry-combination`, `recolor-scope` & `order-dir-source`, `recolor-scope` & `source-dir-source`, `entry-combination` & `order-dir-source`, `entry-combination` & `source-dir-source`, `order-dir-source` & `source-dir-source`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Background cells kept from recoloring: a legend cell is non-background, so no entry has the background as its source, and the model is equivalent to the concept.
- Only non-background cells recolor: equivalent to the concept for the same reason.
- The last entry of a source wins in one lookup: every train source occurs once, so it gives `$ParallelLookup`'s output on every train pair and fails Fit at train0 the same way.
- A chain through the entries in any order: it gives `$ChainToEnd`'s output at train1 (7,18), `7`, and fails Fit there.
- `order_dir` = `DIR_B` and `source_dir` = `DIR_R`: values of stored parameters, which train0 rules out.

## Tickets filed
- none
