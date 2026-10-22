# ba97ae07

## Concept
- Fits every pair (`check_concept.py`): the crossing of the full-column band and the full-row band takes the color of the band that was underneath, and every other cell keeps its color. The band on top in the input is vertical in train0, train3 and test0, and horizontal in train1 and train2, so the output puts the other band on top in each case.
- The concept file's rule is the rule as the generator applies it, so no witness with verdict `other` stands against the concept case.
- The concept case reads each crossing cell by its own row and column, so off the scene it returns the input where it finds no crossing (the `background=DominantColor` witness).

## Choice points
- `background`: how the program gets the background color that sets the bands apart
    - `concept`: stored, 0
    - `background=DominantColor`: replaces `background` with the commonest color of the input. It is undefined where the input has no single commonest color. Fits every pair, since 0 is the commonest color of each input. Witness `background=DominantColor`: a 6-column grid with a vertical band 3 columns wide, where the band color 4 has 33 cells and 0 has 27. It breaks no scene claim, plausibility `ordinary`, verdict `concept`. The concept puts the horizontal band 5 on top. DominantColor reads 4 as background, finds no horizontal band, and returns the input.
    - `background=RarestColor`: replaces `background` with the rarest color of the input. Fails Fit at train0, where the rarest color is the band color 8 and the model returns the input.
    - `background=SharedColor`: replaces `background` with every color of the one input. Fails Fit at train0, where no cell is a band cell and the model returns the input.
    - `background=UnchangedColor`: replaces `background` with the colors that every pair keeps in place. It gives no value on one input with `ex_out` empty, so it is undefined on every input and fails Fit at train0.
- `band-on-top`: which band the output puts over the crossing
    - `concept`: the band that was underneath in the input (`swap-on-top`)
    - `$AxisOnTop`: replaces `swap-on-top` with the band on a stored axis. Fails Fit: the axis is horizontal in train0 and vertical in train1, and no one value fits both.
    - `$ThickerOnTop`: replaces `swap-on-top` with the band of more lines. It is undefined where the two bands have the same width. Fails Fit at train2, where both bands are 1 wide.
    - `$LargerOnTop`: replaces `swap-on-top` with the band whose color has more cells in the input. It is undefined where the two counts are equal. Fails Fit at train2, where both colors have 7 cells.
    - `$ColorOrderOnTop`: replaces `swap-on-top` with a stored order over colors, read from the train pairs as 3 over 8, 6 over 1, 1 over 7 and 2 over 3. It is undefined on a pair of colors the order does not hold. Fails Fit at test0, whose colors 4 and 5 are an unseen key.
- `background` & `band-on-top`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Several bands, or bands that cross more than once: the concept's rule reads each crossing cell by its own row and column, so it gives the same output as a model that swaps at each crossing, and no other model comes from it.
- A crossing that holds a third color, neither band's: no pair or solver header gives a rule for which band that crossing takes, so no model comes from it.
- Background from `ChangedColor`, `OutNewColor`, `AnyOutNewColor` and `VanishedColor`: each reads `ex_out`, so on one input it gives no value, the same as `background=UnchangedColor`, and in determination it proposes no color that is 0 on every pair.

## Tickets filed
- `10-446_task_ba97ae07_analyze.md`
