# c3202e5a

## Departures
- The concept case's `crop-mono-tile` keeps only a one-color tile that also holds background cells, and the header rule says so. The `solid-tile` verdict is now `concept`, and its `separates` text is rewritten: that witness is a `$NoBackground` witness with no `@reassigned` line, no open values and no approximation, and its Analyze verdict was `other` (the sparse one-color tile). Before the fix, the concept was undefined there because the solid tile also has one color. After the fix, the concept gives the judged output.
- `solid-two-color-tile` stands under `$NoBackground` and not under `$FewestColors`: `$FewestColors` and the concept give the same grid on it, so it is no witness of `$FewestColors`. The Analyze report itself says it separates `$FewestColors` from `$NoBackground`, which is undefined there.
- The Analyze witness `background=DominantColor` is removed. It duplicates `bg=DominantColor`, which `derive` recorded on the same input. That entry takes the Analyze `separates` text, and every name `background=DominantColor` becomes `bg=DominantColor`, because the program names the parameter `bg`.
- `$EqualTiles` is not in the solver, and `uneven-lattice` is removed. `$EqualTiles` fails Subsumption: where the lines are evenly spaced, its tiles are the tiles between the lines, so no input shows it defined and differing from `$Lines`, and `witness` reported none. Without that branch, `uneven-lattice` separates nothing.

## Judgments
- `$IgnoreDividerInk` is formed only with `$MostOfOneColor`. `impl_choice` excludes its pairs with `$OneColor`, `$FewestColors` and `$NoBackground`, which fail Fit at train1 according to the Analyze report.
- `$NoBackground` reads no mark and no `bg`, so its one case takes `$CountDividerInk`, and `bg` stands under the marker of the other three selections (lint `shared-read`).
- Hint `negated-use` on the `divider_color` helper: accepted, and `!line_color.value(_, Col)` is inlined.
- "The one tile" is stated with `Unanimous<Choice, Position>` over each case's kept tiles. The case is undefined where it keeps no tile or several tiles. That covers "undefined where several tiles do" for the concept and the ties of the ranked selections. "Marks of one color" is stated with `Unanimous` over the marks, so no literal 1 is needed.
- `@derive DominantColor: borderline concept` on `bg`: this follows the Analyze verdict. The derivation breaks no scene claim, so it has no `@relaxed` line.
- `store` printed no line to add. `fewest.low[s]` and `fewest_all.low[s]` have no witness, so they have no `@store` branch.
- Determination: the plan asked for a relation for `bg`, which `DominantColor` covers. `Determine.bg` keeps the color that every train output holds, which is a fact of the outputs alone.
- Deletions: `tile_box.cell` in `out` is removed, because `crop` already tests that the cell is in the tile's box. These atoms are kept, though the pairs never use them: `impl_choice` in `pick.item` (it excludes the combinations that are not cases), the divider-color negation, `has_bg`, and `mark_colors.domain` (an empty tile counts zero for `$FewestColors`, as `empty-tile` shows).
- Keywords `count` and `rank`: the concept selects by a count of colors, and `$FewestColors` and `$MostOfOneColor` select by an extremum over counts.

## Open
- The concept fix that requires a background cell rests on a `foreign` witness, so no input the generator produces tests it: a review of the `solid-tile` verdict would settle whether the fix should stay.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
none
