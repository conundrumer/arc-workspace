# c909285e

## Departures
- `$PatternBreak` has no constructor and no case, and the witness file lists it in no group: `analyze.md` gives that it fails Relational form. Recovering the plaid from a grid with an unknown set of overwritten cells means finding the fewest cells whose change makes the grid a product of row kinds and column kinds, and no set of clauses states that minimum. The `separates` text of `pattern-color-outline` no longer names it.
- `$SquareBox` is not in the solver: it was written as a `BoxShape` field of `Choice`, and then left under Subsumption. Wherever it is defined, its output is the concept's, and `witness` reported no run that shows it defined and differing. With `BoxShape` down to one branch, `Choice` is the box-source type alone. The witness `wide-outline` then separated nothing, so it left the witness file.
- `$InteriorOnly` has no constructor: it fails Fit at train0, and `analyze.md` gives it no witness.
- The `outline-with-tick` line under `$InteriorColor` has the verdict `$OneBodyColor`, and `analyze.md` gives `$InteriorColor`: the style rule gives a later branch the plausibility and verdict of the witness's first `@witness` line. Both models give the same grid on that witness.
- The witness file holds three witnesses that `witnesses.json` lacks: `small-outline`, `corner-tick` and `edge-outline`. `witness` reported pairs of cases that no run separated, and each of these witnesses resolves one or more of them (see Judgments).

## Judgments
- Concept constructor names: `Outline` for the concept branch of `box-source`, and `CornerContact` for the concept branch of `adjacency` under `$OneBodyColor`.
- "The one color" is a `Unanimous<Choice, Color>` over the colors each case proposes. Two proposed colors clash, so the case is undefined, as `analyze.md` gives for each source. The box is the `Bbox` of that color's cells. For `$Outline` this is the outline's box, because the color's cells are exactly the outline.
- `$Outline` keeps a color when `Outlines` finds a box for it and no cell of that color is off that box's border ring. The border test is `!inside(P, B) ; interior(P, B)`.
- `small-outline` (5 by 5 outline between the lines of 5, so 5 is one body under both adjacencies): plausibility `ordinary`, verdict `concept`. It breaks no scene claim, and the outline size already varies between pairs. It separates `$OneBodyColor & $EdgeContact` (undefined) from `$InteriorColor`.
- `corner-tick` (a cell of the outline color touches the outline's outer corner diagonally): plausibility `borderline`, verdict `other`, with the 7 by 7 crop of the square as the judged output. It breaks `one-outline`. It shows `$OneBodyColor & $CornerContact` defined and differing from `$EdgeContact`. No `@witness` line records it, so `record` stores its groups.
- `edge-outline` (the outline touches the top and left grid edges): plausibility `variant`, verdict `concept`. It breaks no scene claim. The outline is off the edge in every pair, which suggests the generator may keep it there. It shows both `$OneBodyColor` cases defined and differing from `$InteriorColor` (undefined).
- Hints: the lint `claim` findings on `box` and `color_size` were correct, and both instances now have `@claim` lines. The `common-subexpr` hint on `stray` was correct, and the two clauses are now one disjunction.
- Deletions: the clause `color_size.domain` was removed, because every key it gave already has members. The `interior(P, B)` disjunct was kept, because the pairs have no interior cell of the outline color and `outline-with-tick` has one. The `stray` columns were kept, so that a color is tested against each box it draws.
- `derive` reports no fitting derivation, and `store` reports no constant derived value. The parameterization is empty. There is no Determine comp, and the plan lists no actions.
- The Not formed item (restore the plaid under the outline) states one model, and that model fails Fit: every pair copies the box's cells as they are. It was not formed.
- Keywords: `crop color-class border bbox select rank`. `rank` is for `$RarestColor`.
- Performance: every run finishes in 2 s or less.

## Unsettled
- The verdict of `corner-tick`, `other` (crop the square) against `$OneBodyColor` (crop the box that holds the extra cell): a variant task whose outline has a stray cell of its own color would settle it.
- The plausibility of `edge-outline`: a variant task whose outline touches the grid edge would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
