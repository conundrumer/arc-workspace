# e734a0e8

## Departures
- The witness id `$DividerFromLines` is `lines-5` in the solver and in `programs/witnesses/e734a0e8.wit.json`: the `witness` check rejects an id that is not a slug. Its input, groups and verdict are unchanged.
- `$DividerFromLines` uses its derived color in every claim that reads `divider_color`, not in `divider-tiling` alone, as `analyze.md` words it. The marker color under `$DividerMarker` and the plain colors of `one-source` both read that derived color: the reason is that the witness `lines-5` expects the branch to stamp copies where the markers are `5`. If only the lines used the derived color, the `5` markers would count as drawn tiles, and the branch would be undefined there.
- The background branch is the `@derive DominantColor` line on `background_color`, and no constructor: `derive` lists `DominantColor` as fitting, and the branch derives a parameter by a built-in derivation.
- `$TileDimStored` has no constructor: `analyze.md` gives it no witness, and it fails Fit (`5` fails train1, `3` fails train0 and test0).

## Judgments
- The concept case is undefined where the count of source tiles is not one. `rival` drops every candidate where two tiles are candidates, and every `out` clause reads `defined`, which needs a source. This gives the undefined concept output that `analyze.md` states on `background_color=DominantColor`, `marker-color` and `second-drawn-tile`.
- A whole-tile copy gives no fact at a marked-tile cell that has no counterpart in the source. So under `$AnyCell` and `$MarkerAtCenter`, unequal tiles give no total grid, which follows `stamp-marked` read literally. Under `$MarkerAnchors`, a marked-tile cell that the clipped copy misses keeps its input color, as the witness `off-center-marker` gives.
- `$MarkerAtCenter` is undefined where any tile has no center cell (`centerless`). `$MarkerAnchors` is undefined where a marked tile holds two marker cells (`multi_marker`) or the source has no center cell. Both follow `analyze.md`.
- `store` hints: `line_hue.item` and `line_hue.value` take `@ignore ... store`. A stored line color under `$DividerFromLines` is a stored divider color, which is equivalent to `$StoredDivider`, and the case with more non-concept branches fails Equivalence. `parse.full_line` and `plain` take `@ignore: store`, because each one repeats parameters the program already stores.
- Determination: `background_color` is the commonest color of every input (`Mode`), `divider_color` is a color that fills a full line in every input, and `marker_color` is the non-background input color that every pair overwrites. The line parse moved into `Parse<Key>`, so the program and `Determine` share it.
- `deletions`: one atom was cut (`source(Ch, P_src)` in `tile_copy`, which `source_color` implies). Each other deletion it lists is a guard that the pairs never use: `rival`, `centerless`, `multi_marker`, `!drawn`, the overlay disjunct, the anchor clip, the `$SourceByCount` tally, and the test-input `ex_out` atoms of `Determine`. The witnesses use these guards, or the principles require them.
- Keywords: `decompose` (divider lines cut the tiles), `markers` (dots pick the tiles), `stamp` (the source tile stamps at the marked tiles).
- The solver runs in about 1 s on the pairs, with 8 witnessed cases out of 96. There is no performance issue.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
