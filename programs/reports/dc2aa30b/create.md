# dc2aa30b

## Departures
- Witness file, names: `tile_layout=stored` is now `tiling.divider=stored`. This is the name of the `@store divider` line above `.init tiling`, which records that branch.
- Witness file, groups of `divider_color=SharedColor` and `tiling.divider=stored`: `witnesses.json` gives `concept` and `$TieAnyOrder` as undefined. The solver gives the input unchanged. On an input with no full line of `divider_color`, `DividerTiles` gives one tile, the whole grid. One tile ranked and placed gives an unchanged copy. The concept states the board as a scene claim, not as a test the program runs, so the solver adds no check that makes the output undefined there.
- Witness file, `broken-divider` added: row 3 of the test input has one cell set to 1. The stored layout gives the sorted board. The concept and the derived divider colors give a non-total output. This separates `divider_color=stored & tiling.divider=stored` from `divider_color=SharedColor & tiling.divider=derived`, which no witness of `witnesses.json` separated.
- Witness file, `divider_color=VanishedColor` removed: `derive` wrote it, and the branch has an `@ignore: derive VanishedColor` line (see Judgments).
- `analyze.md` Not formed says that the concept case runs both (`counted_color`, `order_corner`) = (1, bottom-left) and (2, top-right). It also lists no open parameter. The solver stores (1, bottom-left) alone, as the concept file gives. The two assignments give the same output on every input whose tiles hold only 1 and 2.

## Judgments
- `@derive SharedColor` on `divider_color`: variant, verdict `derived`, `@relaxed divider-board`, as `analyze.md` gives.
- `@ignore: derive VanishedColor`: in a run on one input, `ex_out` is empty, so the proposer gives every color of that input, as `SharedColor` does. The two models are equivalent. Both take one non-concept branch, so `VanishedColor` leaves under Equivalence.
- `@store divider` on `tiling`: variant, verdict `stored`, `@relaxed divider-board`, from `analyze.md`'s `tile_layout=stored`.
- `@ignore value: store` on `parse.line_color`: `store` asks for the uniform line color to become a parameter. `params.divider_color` is already that parameter. The derived value is the color of each line, which the divider test compares with that parameter.
- `broken-divider` witness: plausibility `foreign`, because the generator draws every divider line whole. Verdict `tiling.divider=stored`.
- `$TieUndefined` is the concept branch's constructor, a name of my own. The concept case puts a tile in a slot only where its count rank equals the slot rank. Where counts tie, a slot gets no tile and the output is not total.
- `fill_axis` stays in the concept file's form, an `Axis`. `LexOrder` reads the primary axis, so the program derives it with `perp`.
- The `@claim` lines on `tile_box`, `counted`, `by_count` and `slots` follow the rules each instance serves.
- Deletions: `params.divider_color(Col)` in `tiling.divider` stays. The pairs have no full line in a color other than 0, and `divider_color=SharedColor` shows the atom matters. The `lined`/`unlined` atoms in `Determine` also stay. The pairs hold one line color, so the universal over the examples is never tested.
- Determination: `divider_color` is derived in `Determine` as the color of a full line in every example input. `counted_color`, `order_corner` and `fill_axis` are fixed by fit over their enumerable types. Two joint assignments fit: (1, DIAG_BL, AXIS_H) and (2, DIAG_TR, AXIS_H).
- Keywords: `decompose`, `count`, `rank`, `tile-arrangement`.

## Unsettled
- The audit finds no run that shows `divider_color=SharedColor & tiling.divider=derived` defined and different from `divider_color=stored & tiling.divider=stored`. Two attempts failed. A 2 × 2 board of 4 × 4 tiles hit the 20 s run limit, because `$TieAnyOrder` enumerates tie orders over the uneven tiles the stored layout cuts. A 4 × 4 board of 3 × 3 tiles gave the same output under both. To settle it, find an input where both are defined and give different outputs, with few ties under the stored cut.
- The audit's relabelings check timed out after 20 s, so it is open.
- The `@ignore value: store` line moved into `Parse` after the last audit run. No audit has confirmed that the `store` finding on `parse.line_color.value` is cleared.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/dc2aa30b/analyze.md`, the `divider_color=DominantColor`…`counted_color` derive list under Not formed ("`VanishedColor` … each reads `ex_out`, which is empty in a run on one input, so it gives no value"): `VanishedColor` gives every color of the input in such a run. It should be listed as equivalent to `divider_color=SharedColor`.

## Tickets filed
- none
