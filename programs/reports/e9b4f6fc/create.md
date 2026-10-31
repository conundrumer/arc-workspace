# e9b4f6fc

## Departures
- The header has no `@scene keys-cover-drawing` line: no `@claim` or `@relaxed` line refers to that claim, no rule text depends on it, and no branch replaces it. Style (Header) leaves out a scene claim like that.
- `$StoredColorMap` has no constructor: `analyze.md` gives it no witness, because it fails Fit at train3 and has an unseen key in the test.
- The concept branches take constructor names of my own: `$KeyNewSide`, `$SideAdjacent`, `$OnlyLargeObject`, `$RecolorOnce`. `record --all` rewrote the names in the witness file to those cases.

## Judgments
- "More than two cells" is stated as three distinct cells of one object. A two-cell key is an object that does not have three such cells. This needs no stored size literal, and no size count outside `$PictureLargest`.
- `$PictureLargest` uses `Tally` and `ArgExtremes`. It requires the largest object to have more than two cells and to have no tie. This gives the undefined inputs that `analyze.md` states.
- In `$RecolorTransitive`, "stopping at a repeated color" is read as the color at the greatest fewest-hop distance from the cell's color along the key edges. That color is `GraphDistance` with `ArgExtremes.high`. On a chain, it is the end of the chain. On a cycle, it is the last color before a repeat.
- The `$KeyOldInPicture` case is undefined through `key_clash`, where the picture holds both colors of a key. For `$RecolorOnce`, two keys that give one old color two new colors make conflicting `out` facts, so that case is undefined there, as `analyze.md` says.
- Hint `common-subexpr` (`key_clash` against `key`): I accepted it. `key_clash` now reads `key` and adds `picture_color(New)`. I dropped the negation `!picture_color(New)` from `key`, because `key_clash` blocks those cases anyway.
- Hint `head-repeat` on `repaint(C, C, ...)`: I accepted it. I removed `repaint`, and the `$RecolorOnce` `out` clause is now a disjunction (a key's new color, or the cell's own color).
- `@derive DominantColor` on `background`: `derive` listed it as fitting. It records the `background=DominantColor` witness (`variant`, verdict `derived`, `@relaxed background`). `store` printed no line to add.
- Determine: the plan asked for a determination relation for `background` from DominantColor, so `Determine.background` keeps the color that is commonest in every input (`Mode`). `new_side` stays determined by the pairs over its enumerated type (1 of 4 values fits), and no proposer gives it.
- Deletions that change nothing on the pairs, all kept:
  - `two_large`, `largest_tie`, `key_clash` and their negations, `large` and `largest.high` in the `$PictureLargest` picture: these state undefined inputs that only the witnesses reach (`two-pictures`, `chained-keys`).
  - `domino.d` and `params.new_side(D)`: these state the concept's key orientation.
  - `obj(P, Id, A)` in `domino`: it puts the first cell in the object.
  - `not_commonest`: it is the "every input" part of the DominantColor determination.
- I removed `size.domain`, because every object has members.
- Witness checks: `witness` reports ok against the witness file and against `witnesses.json`. The audit reports ok in every check. The pairs pass at 6 witnessed cases.
- I ran `deletions` twice: two simplifications came after its first run, so I ran it again after the last code edit.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
