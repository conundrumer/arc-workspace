# d5c634a2

## Concept
- The concept fits every pair: the probe `work/task/d5c634a2/probe.py` reproduces each train and test output, with up-T counts 1–4 and down-T counts 1–4 all among the train pairs.
- The pairs fix the corner order: train3 (up count 2) puts the second mark at (2,0), and train0 (up count 3) puts the third at (0,2), so `order_axis` and `order_corner` take one value.
- The concept is undefined where one direction has more T shapes than a panel has corners, and it gives an empty panel for a direction with no T shape.
- No witness of the concept case has the verdict `other`.

## Choice points
- `slot-order`: which cells of its panel a count marks, and in what order
    - `concept`: the panel's corners, in the lexicographic order of `order_axis` from `order_corner`
    - `$PeriodSlots`: replaces `count-as-marks`: the slots are the panel cells at even offsets from its top-left cell on both axes, in the same order, with the concept's parameters; it agrees with the concept at a 3×3 panel, and it is undefined only where a count exceeds the slots. Fits every pair. Witness `five-in-a-wide-panel`, at `panel_size` 5×5; it breaks `fits-the-panel`; plausibility `variant`; verdict `$PeriodSlots`; it breaks the invariant that no direction has more than four T shapes. A stored list can hold the slots' order, so `$StoredSlotList` subsumes it.
    - `$StoredSlotList`: replaces `count-as-marks`: the order is a stored list `slot_list` = (0,0), (2,0), (0,2), (2,2), the value the concept derives; it is undefined where a count exceeds the list. Fits every pair. Witness `$StoredSlotList`, at `slot_list` = (0,0), (2,2), (0,2), (2,0); plausibility `ordinary`; verdict `$StoredSlotList`. A table of the list's prefixes, with an empty entry at 0, gives its output, so `$CountTable` subsumes it.
    - `$CountTable`: replaces `count-as-marks`: a stored table `count_table` from a count to the panel cells it marks, the entries for 1–4 being the concept's prefixes; it is undefined at a count with no entry, 0 and above 4 at the stored table. Fits every pair, since every test count is a train key. Witness `$CountTable`, at `count_table` with the entry for 2 set to (0,0), (2,2); plausibility `ordinary`; verdict `$CountTable`.
- `order-sharing`: whether the two panels fill in one order
    - `concept`: one order, at the same places relative to each panel
    - `$SlotOrderPerDir`: replaces `same-slot-order`: each direction stores its own order, `dir_order` = up → (H, TL), down → (H, TL). Fits every pair. Witness `per-panel-order`, at `dir_order` down → (V, TL); plausibility `ordinary`; verdict `$SlotOrderPerDir`.
    - `$MirroredSlotOrder`: replaces `same-slot-order`: the second panel fills in the first panel's order mirrored across the panel's vertical axis. Fails Fit at train1: its down count 1 marks (0,5), and the pair marks (0,3).
- `component-parse`: what one T shape is in the ink
    - `concept`: a 4-connected ink component equal to a T tetromino
    - `$Adjacency8`: replaces `t-shapes`: the components are 8-connected. Fails Fit at train2: the down-T at rows 3–4 and the up-T at rows 4–5 touch at (3,2)–(4,1) and merge into one component that is no T.
    - `$ShapeOccurrences`: replaces `t-shapes`: each placement of a T picture whose cells all land on ink counts, whatever the component around it; it agrees with the concept wherever every component is a T. Fits every pair. Witness `plus-holds-two-ts`; it breaks `t-shapes`; plausibility `foreign`; verdict `concept`; it breaks the invariant that every 4-connected ink component is a T tetromino.
- `shape-class`: how a T shape is assigned its direction
    - `concept`: the stem direction read from the T's geometry, keying `dir_mark` and `dir_panel`
    - `$ShapeTable`: replaces `stem-directions`: a stored table `shape_table` from a component's picture to its key, up-T → `DIR_T`, down-T → `DIR_B`, the value the concept derives; a component whose picture has no entry is not counted. Fits every pair, since both test keys are train keys. Witness `$ShapeTable`, at `shape_table` with an L tetromino added under `DIR_T`; it breaks `t-shapes`; plausibility `variant`; verdict `$ShapeTable`; it breaks the invariant that every 4-connected ink component is a T tetromino.
- `panel-key`: which panel a direction's marks go to
    - `concept`: the stored `dir_panel`
    - `$PanelByCount`: replaces `panel-per-direction`: the direction with more T shapes takes the first panel, and the model is undefined at equal counts. Fails Fit at train0: up count 3 and down count 4 put the down marks in the first panel.
- `slot-order` & `order-sharing`, `slot-order` & `component-parse`, `slot-order` & `shape-class`, `slot-order` & `panel-key`, `order-sharing` & `component-parse`, `order-sharing` & `shape-class`, `order-sharing` & `panel-key`, `component-parse` & `shape-class`, `component-parse` & `panel-key`, `shape-class` & `panel-key`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A derived output frame or panel size: `ConstOutDim` and `ConstOutDimAxis` read the train outputs, and on an input alone, with `ex_out` empty, they give no value, so the derivation is undefined on every pair; no other proposer gives a frame from the input.
- Derived mark colors: `OutNewColor` reads the train outputs and gives `1` and `3` with no direction, so no derivation gives `dir_mark`.
- A derived `shape_color`: the program reads every non-`0` cell as ink and reads no shape color.
- Marks past a panel's slots, wrapped or spilled into a further panel: no pair, solver header, proposer or lib component gives such a reading, and every model is undefined there.
- Mark color keyed by panel: `dir_mark` and `dir_panel` are both keyed by direction, so keying the color by the panel re-encodes the same model.
- Other corners and primary axes of the order: these are values of `order_corner` and `order_axis`, and the pairs separate them.

## Tickets filed
- 10-708_task_d5c634a2_analyze.md
- 10-709_task_d5c634a2_analyze.md
