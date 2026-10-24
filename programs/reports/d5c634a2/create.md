# d5c634a2

## Departures
- `panel_axis` is not a parameter. `dir_panel` is stored as a `GRID_1x2` of stem directions, `dir_panel(p_tile, d)`, and `concat_2d` places each panel in the output: under Redundant value, the grid's shape already gives the axis, so a separate `panel_axis` would be a second parameter that follows from the first.
- An added parameter, `bg` (`0`), is the color of both the input field and the output field: colors come from Params, and the concept file stores no field color. `derive` found `DominantColor` fits it, so it carries a `@derive DominantColor: variant derived` line, and its witness is `bg=DominantColor`.
- `panel_size` is stored as `(a: Axis, n: number)` rather than `(v, h)`, and the `panel_size` assign of `five-in-a-wide-panel` became `[["AXIS_V",5],["AXIS_H",5]]`: lint rejects the orientation literal that a determination reading a `(v, h)` column needs. 1fad071e `out_dim` is the precedent.
- `$StoredSlotList` is not a constructor. It is the `@store rank` line on the `lex` instance (`lex.rank=stored`): it stores a derived value, and it is not a lookup table, so Develop step 4 holds it as a branch even though `store` printed no line for it. Its witness id became `lex.rank=stored`, and its `slot_list` assign became `lex.rank` facts, with Box positions in the 3×3 panel and one copy per direction.
- Witness ids `$CountTable` → `swapped-count-table` and `$ShapeTable` → `l-in-shape-table`: lint requires the slug form.
- The `count_table` assign is rewritten to Box positions. `shape_table` is split into the parent/child pair `shape_table(id: Ident, p: Position)` and `shape_key(id: Ident, d: Dir)`, following the set-keyed relations pattern, and its assign is rewritten to match. The `(cells, key)` form in `witnesses.json` has no Souffle schema.
- `$PeriodSlots` needs a new parameter, `slot_stride(1, 1)`, because literals are banned and `stride` takes a width and a gap. Its slots are anchored at `order_corner` rather than at the top-left cell, which keeps the model equivariant. The two readings agree at the stored value.
- Pair readings, from the `&` line of `analyze.md`: `$CountTable & $SlotOrderPerDir` reads a per-direction table, `dir_count_table`. The stored-rank branch is keyed by direction, so with `$SlotOrderPerDir` it holds one list per direction.
- The concept recognises a T by its geometry, not from a stored picture. A middle cell has ink arms toward the stem and toward both bar ends, and the T is kept only when its 4-connected component holds no other cell (defect negation). The concept file stores no T picture.
- `$MirroredSlotOrder`, `$Adjacency8` and `$PanelByCount` are not formed: `analyze.md` gives each a failing Fit (train1, train2 and train0) and no witness.
- `witness --file programs/reports/d5c634a2/witnesses.json` fails, and every difference comes from the schema changes above: assigns in the old forms (`count_table` `[0,0]`, `shape_table` cell lists, `slot_list`), the name `$StoredSlotList`, and `five-in-a-wide-panel` undefined under `panel_size` `[[5,5]]` read in the `(a, n)` schema. In `programs/witnesses/d5c634a2.wit.json` the same witness gives the `$PeriodSlots` grid that `witnesses.json` gives, and `witness` reports ok.
- Added witness `per-panel-count-table`, built from the train3 input at a `dir_count_table` whose down entry for 2 marks the top corners. It witnesses `$CountTable & $SlotOrderPerDir`, which resolves the audit's 20 `dir_count_table` facts whose removal changed no output. The audit's open values now pass.

## Judgments
- `bg=DominantColor` (train0 with 0 and 4 swapped) is `variant`, verdict `derived`, `@relaxed t-shapes`: it is a colour-permuted variant, the generator permutes the output field the same way, and only the derived `bg` gives that output.
- `per-panel-count-table` is `ordinary`, verdict `$CountTable & $SlotOrderPerDir`, by analogy with `per-panel-order`. It has no `@witness` line: lint rejects it under `$SlotOrderPerDir`, because there it does not separate that branch from the concept.
- `lex.rank=stored` keeps the plausibility and verdict `analyze.md` gives it: `ordinary stored`.
- The lint hint "determine prediction" on `bg` was right: the test read inputs and outputs together. The fix splits it into `input_lacks` (inputs alone) and `output_lacks` (outputs alone).
- Deletions: 29 change nothing, and each is structure the pairs never instantiate. That covers the undefined tests (`unfit`, the slot tally), the zero-count domains, the non-T component defect (`t_extra`), the per-direction column of `table_entry`, the code of the unwitnessed combination `$ShapeOccurrences & $ShapeTable`, and the universals of the determination. All are kept. One was redundant and was simplified: the edge disjunct of `slot_start`, whose off-panel neighbour already counts as an unmarked line.
- Sweep: `dir_mark` has 8 and `dir_order` 16 single-row changes that fit, and they add rows for directions that have no panel. No reader of the concept takes them, so there is no open parameter, and nothing beyond the stored values is stored.
- Plan: `bg`, `panel_size` and `slot_stride` have determination relations. `order_axis` and `order_corner` are fixed exactly by enumeration with no proposer, so they get no relation. The `slot_stride` determination reads the slot width as the first unmarked line from a corner's edge, and the gap from `divide_gap` over the count of slot starts. It assumes the slots span the panel with equal gaps.
- Keywords: `objects classify count rank lookup`. `lookup` is for the `$CountTable` and `$ShapeTable` cases.
- Performance: `sweep` runs past 240 s, and it stops at its 300 s limit before reaching `slot_stride`, `count_table` and `dir_count_table`. I did not read `src/`.

## Unsettled
- Only 9 of the 80 enumerated cases are witnessed. The remaining combinations, such as `$ShapeOccurrences & $ShapeTable`, `$PeriodSlots & $SlotOrderPerDir` and `$CountTable & $ShapeTable`, fit but are not run by any check: witnesses at joint reassignments would settle whether each stays.
- The sweep did not reach `slot_stride`, `count_table` or `dir_count_table`: rerunning with a larger `--sweep-limit` would settle it. By hand, `(1, 1)` is the only stride that fits at 3×3.
- `count_table` cannot store an empty entry, so `$CountTable` is undefined at count 0. Because of this it does not subsume the stored rank list, which `analyze.md` said it would. A parent table of entry keys would settle whether that model is wanted.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
