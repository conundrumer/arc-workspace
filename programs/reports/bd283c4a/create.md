# bd283c4a

## Departures
- none

## Judgments
- `$TieFirstCell` is added as a branch at the tie point under Develop step 3. It forms the Not formed item "a tie-break by position" as one model: colors of equal count stand in the order their first cells come in the input's raster order, the raster order of `raster-fill`. It fits every pair, has a relational form, and is not subsumed by the concept, because on `tied-counts` it gives one grid and the concept gives two. Witness `tied-counts`, `borderline` `concept`, `@relaxed distinct-counts`.
- `$TieUndefined` leaves under Subsumption. No run shows it defined and differing from the concept, and the concept gives the same output wherever `$TieUndefined` is defined, as the Analyze report states. The `tied-counts` witness drops its `$TieUndefined` group, and its `separates` text now names `$TieFirstCell`.
- The Not formed item "ranking from the lowest count first" is not formed. Its model at a corner is the concept's model at the opposite corner on the same axis, so it fails Equivalence.
- The Not formed items "start_corner or fill_axis derived from the input" and "counting objects" are not formed. `derive` reports that no built-in derivation fits, and an object count does not fill a total grid on train0.
- `$SnakeFill` and `color_rank=stored` get no constructor. Both fail Fit at test0, and the Analyze report gives neither a witness.
- `out_dim=stored` is held as the `@store` branch on `out_dim`, with `variant concept` from the Analyze witness. `store` printed the line for it.
- Ties are enumerated with `TiebreakResolutions<Unit, Color, Color>`. The slots are colors, and a slot's rank is its rank in `ranked`, which is count first and then first cell in the raster order. A color may take the slot of any color of equal count. So the first-cell order only names the places, and every order of the tied colors is one resolution. A dense set of slot numbers is needed, and no lib relation gives one without an order on the colors.
- Each color's run in the raster order is the range from the count of input cells of colors ranked before it (`preceding`) up to that count plus its own cells (`through`). This uses comparisons only, with no arithmetic.
- `fill_axis` is stored as the concept gives it, the axis a line runs along. `LexOrder` reads the axis the lines step along, so `step_axis` derives it through `perp`, as the Relative orientation style rule gives.
- The input's raster order (`scan`) is a separate `LexOrder` from the output frame's (`raster`). Under `out_dim=stored` the two frames can differ.
- `deletions`: `size.domain` was removed, because every color has a cell. The `scan`, `first`, and tie `ranked.before` clauses change nothing on the pairs only because no pair has a tie. They stay for `$TieFirstCell` and for the slot ranks.
- Determination: the sweep and the plan give one value for each of `start_corner` and `fill_axis`. No proposer derives either value, so the solver has no Determine comp. Each value is the one value of its type at which the model fits every train pair.
- No hint appeared other than `single-consumer` on `out_dim`, and that hint stopped once the `@store` line was added. No performance issue was found.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
