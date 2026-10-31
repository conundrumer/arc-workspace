# f3cdc58f

## Departures
- The solver has no `$StoredFrame` case. The witness file drops the `$StoredFrame` witness, and `absent-color` lists `concept` alone in its first group: `$StoredFrame` stores a value the program derives (the output frame), and so it is not a constructor. Develop step 4 holds it as a `@store` branch. But `store` prints no line to add for `frame` ("no witness: no D4 image or color swap of a train input changes the value"), so `frame` is marked `@workaround`, as Develop says. With no case for that name, the `$StoredFrame` witness separates nothing and leaves. `witness --file programs/reports/f3cdc58f/witnesses.json` reports that `$StoredFrame` denotes no case, and this is the only difference it shows.

## Judgments
- The concept branch of `empty-slot` is named `$KeepSlot`.
- `bg=DominantColor` is `variant derived` with `@relaxed scattered-marks`. The `derive` witness is train0 with 0 and 5 swapped. A color swap of the background is a routine variant, and in that variant the output's field follows the input's field. The witness input is not on color 0, so it breaks `scattered-marks`.
- `$PackBars` `absent-color` keeps the plausibility and verdict that `analyze.md` gives: `variant concept`.
- `slot` is a `store` line that is "stored already" as `bar_order`. `held.elem` and `held.rank` have no `store` witness. No branch comes from them.
- Not formed: `analyze.md` lists the slot read from the color number (col = color − 1). That reading needs arithmetic on a color, which the program bans, and no lib relation states it. It is also not equivariant under color permutations. So no branch is formed for it. The other Not formed items state no model that meets the case conditions.
- `determination-plan` still lists `base_side`, `start_side` (type enumeration, pairs-exact) and `bg` (DominantColor exact) after `bar_order` was determined. The concept derives none of them from a fact, and the type enumeration and the proposer already cover them. So the only determination relation is `bar_order`. It reads each output bar's color at its distance from `start_side`.
- The sweep reports that 11 single-row changes of `bar_order` give the train outputs under `concept`, and 13 under `$PackBars`. These changes add rows for colors that no input holds, which no reader of the concept would take. `bar_order` is not an open parameter.
- `deletions` reports that the atom `color_count.tally(Col, _)` in `held.score` changes nothing on the pairs. The atom stays: every pair holds each of the 1–4 colors. The atom keeps an absent color out of the `$PackBars` ranking. `Order` documents the `elem` filter for the `before` form only, not for the score form.
- Keywords `color-class count rank`: the cells of each color form one unit, the bar length is a count, and a stored order places the bars.
- No lint hint appeared. No performance issue appeared: every run took under 30 s.

## Unsettled
- `$StoredFrame` (output frame stored as 10x10): this needs a `store` that can propose a stored output frame, or a witness that the runner accepts for `frame`, for example an input that is not 10x10.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
