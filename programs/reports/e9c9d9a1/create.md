# e9c9d9a1

## Departures
- `$TableRooms` and `$NoBackgroundLines` are my names for the concept branches of `room-parse` and `divider-test`. The witness file needed no renaming, because `analyze.md` names those branches `concept`.
- The solver has the extra branch `line_color=RarestColor`, a `@derive RarestColor: variant derived` line on `line_color` under `$LineColorLines`: `derive` reported that it fits, and Develop step 4 holds a built-in derivation that fits. Its witness `line_color=RarestColor` is train 0 with 3 and 5 swapped. That witness was written by `derive`.

## Judgments
- `line_color=RarestColor` witness: plausibility `variant`, because a color permutation of the task gives lines of 5. It breaks `full-lines`, which gives the lines as 3. The verdict is `derived`: the generator pairs the input with the table that the 5 lines cut, and `$LineColorLines & line_color=RarestColor` gives that table, as the concept does. `$LineColorLines` at the stored 3 finds no divider and is undefined.
- Hint `negated-use` on `!edge_room(T, P)`: accepted. The test is now `!table.part_idx(T, P, _, 0)` in place of a one-use relation.
- Hint `long-clause` on the Determine `corner_color` clause: accepted, and the body is wrapped.
- Determination: `corner_color` reads the output color of each grid corner cell. `inner_color` reads the output color of the inner room cells of the concept's table. `line_color` reads the color of the full lines with no background cell. `background` reads the input color of the cells that the output recolors. That last clause is a fact other than DominantColor's count, so the plan asked for it. To keep the table derivation in one place, the concept's table (`line`, `open_line`, `clear_line`, `DividerTiles`, `room_cell`, `inner_cell`) went into `Parse`, which the program keys by `DividerTest` and Determine keys by `Example`.
- `deletions` found 5 removals that change nothing. All of them stay:
    - The three atoms of `room_cell` and `parse.room_cell` in the corner fill keep the fill on background cells of a room, which `rest-unchanged` needs. Train inputs hold no non-background cell inside a room, so the pairs do not test this. Witness `third-color-line` holds such a cell under `$LineColorLines`.
    - The `a` column of `broken_line` follows from `l`. It stays so that `broken_line` has the same form as `open_line` and `table.divider`.
- After `deletions`, the only edit to the solver was a comment: the `@claim` under `TableRooms` now lists `corner-rooms inner-rooms`, because `$EnclosedRooms` changes both claims. `deletions` was not run again.
- The `@scene` lines `two-lines-per-axis` and `no-edge-line` stay. `corner-rooms` assumes four distinct, nonempty corner rooms, and these two claims give that.
- Keywords: `decompose` (full lines cut the grid into rooms), `lookup` (`corner_color` is keyed by corner), and `enclose` (inner rooms are closed off from the grid edge).

## Unsettled
- The `separates` text of witness `background=DominantColor` does not say that `line_color=RarestColor` also gives the input unchanged. The groups do give this. Rewriting that text would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
