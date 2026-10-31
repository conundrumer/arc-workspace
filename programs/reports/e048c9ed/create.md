# e048c9ed

## Departures
- `$DerivedLengthColor` has no constructor and no case. Its rule, the mark's color is (n − 1)² mod 10, reads a color as a number, and colors have identity and no other properties. `mark-per-bar` is the stored `length_color` lookup.
- `background=DominantColor` is a `@derive DominantColor: variant derived` line on `bg`, with `@relaxed background`, and has no constructor. The witness `bg=DominantColor` that `derive` recorded (train 0 with 0 and 2 swapped) replaces the `background=DominantColor` witness of `witnesses.json`, and every group names it `bg=DominantColor`.
- The concept branches take the names `$SingleCell` (marker) and `$AlongAxis` (bar axis).
- The header has no `bars-short-of-marker` scene line: no `@claim` or `@relaxed` denotes it, no rule text depends on it, and no branch replaces it (Style, Header).

## Judgments
- Undefinedness outside the scene is encoded in `undefined(ch)`, which drops all of a case's `out` facts. A case is undefined where it has no marker, where a bar is not straight along an axis the case allows, or where the marker spans two lines across a bar. For `$MarkerOnEdge`, it is also undefined where the marker spans two lines across the edge. This follows the undefinedness that `analyze.md` gives each branch. `deletions` reports these clauses as changing no pair. The witnesses `turned-scene`, `two-cell-marker` and `bg=DominantColor` need them, so they stay.
- A bar with no `length_color` key gets no fact at its mark cell, so the grid is not total and the case is undefined there. This is the stored table's undefinedness on a length that is no key.
- Hint `common-subexpr` (marker object cells in `target` and `undefined`): accepted. The relation `marker_cell(m, p)` now holds the marker's cells per branch, and the hint does not fire.
- Finding `parse unshared with determine`: resolved, because `Determine` reads `Parse<Example>` for `length_color`.
- `sweep` reports 15 single-row changes of `length_color` that give every train output. These add rows at keys no pair has. No reader of the concept takes them, so `length_color` is not an open parameter, and the stored set stays.
- `determination-plan` lists `bar_axis`, `bg` and `marker_edge` as covered by enumeration with one fitting joint assignment. The concept stores each of them, so no determination relation was added for them.
- `deletions`: the bound enumerator `axis_elem(A)` in `bent` stays, as the tool says. `!parse.bent` in the `$AlongAxis` `bar_line` clause and the atoms of the `$MarkerOnEdge` edge-clash clause change no pair, and witnesses `turned-scene` and `bg=DominantColor` need them.
- Keywords: `objects markers count lookup cross`. `cross` covers the mark at the cell where the bar's row crosses the marker's column.
- Of the 8 cases (2 markers × 2 bar axes × `bg` stored or derived), 4 are witnessed. `witness` and `audit` report no unseparated pair and no unwitnessed-case finding.

## Unsettled
- Not formed item "a marker that is the single cell of a stored or derived color": the item gives two models (stored `marker_color`, or `RarestColor`), so it was not formed as one branch. A witness with two single cells, one of them gray, on the top row would settle whether either one meets Subsumption.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
