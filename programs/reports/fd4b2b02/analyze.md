# fd4b2b02

## Concept
- Fits train0–2 and test0 (`work/task/fd4b2b02/check_concept.py`, `work/task/fd4b2b02/probe.py pairs`). The concept case's model takes the bar as the bounding box of the non-background cells, colored by their single color. It is undefined where those cells hold more than one color, and it keeps the input's cells. No witness has verdict `other`. The generator just draws the four chains and clips them at the edge, and the concept's rules state that directly, so nothing in them is an approximation.

## Choice points
- `bar`: what counts as the bar the chains start from
    - `concept`: the bounding box of every non-background cell, as one bar of their one color
    - `$PerBar`: replaces `one-bar`, `keep-bar` and `diagonal-chains`: each 4-connected component of non-background cells is a bar (its bounding box, its one color), and each sends its own four chains. No new parameters. Undefined where a component holds two colors, or where two bars' chains give a cell different colors. Fits every pair. Witness `two-bars`: two 6 bars, the second where the first's down-right chain puts a 6 bar. It breaks `one-bar` and the invariant that every input holds exactly one bar. Stands at the stored assignment, `variant`, verdict `$PerBar`.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: derives `background` as the input's commonest color, replacing the stored value. Undefined where that color has no one value. Fits every pair: it gives 0 on each input. Witness `background=DominantColor`: a 6 bar on a background of 1. It breaks `one-bar` (on the `background` 0) and the invariant that every input's background is 0. Stands at the stored assignment, `variant` (a color permutation moves the background off 0 and leaves 3 and 6 alone), verdict `background=DominantColor`. The concept and `$PerBar` are undefined there.
- `spawn`: which corners a new bar spawns from
    - `concept`: each chain bar spawns only at its corner that faces away from the input bar, along its chain's diagonal direction
    - `$Lattice`: replaces `diagonal-chains`: every bar, chain bars included, spawns a turned, recolored bar at each of its four corners, until the bars leave the grid. No new parameters. Defined wherever the concept is. Fails Fit at train0: it puts 6 at rows 0–2, cols 6–7, where the output is 0. It fails train1 as well (3 at row 3, cols 7–9).
- `next-color`: what gives a chain bar its color
    - `concept`: `partner` of the previous bar's color
    - `$ColorByAxis`: replaces `diagonal-chains` (its color part) and `partner`: a stored map from a bar's long axis to its color. Undefined on a square bar. Fails Fit: train0 needs vertical -> 6 (input 4×2 of 6) and train2 needs vertical -> 3 (input 5×2 of 3). No assignment fits both, so it fails at train2.
- `bar` & `background`, `bar` & `spawn`, `bar` & `next-color`, `background` & `spawn`, `background` & `next-color`, `spawn` & `next-color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `partner` stored as an unordered pair {3, 6} that swaps, in place of a mapping: at this task's values it gives the same output as the mapping on every input. It only narrows Θ to involutions, and no pair or variant task here puts a three-color cycle in a chain.
- `partner` derived: under `@derive` a proposer reads one input with no output. The partner color is absent from every input (test0 holds only 6 and 0), and ChangedPairs and VanishedNewPairs read outputs, so no derivation gives it.
- `background=SharedColor`, `background=RarestColor`: on one input SharedColor gives each of the input's colors, the bar's among them, and RarestColor gives the bar's color. With the bar's color as background, the bar becomes the 0 region, whose color has no `partner` entry, so the case is undefined on every pair and fails Fit.
- A gap between successive bars as a parameter: the claim places bars corner to corner (diagonal adjacency), a relation and not a count, and every pair shows that touch.
- Only whole bars are drawn (the chain stops before a bar that would cross the edge): refuted by train0 rows 0–2, cols 0–1, a 4×2 bar clipped to 3×2.
- A chain reflects off the grid edge: train0 and train1 show nothing past the last clipped bar of each chain.
- The next bar keeps the previous bar's shape: refuted by train0 rows 3–4, cols 2–5 (the 4×2 bar becomes 2×4).
- A square bar: turning it keeps its shape, so no reading of the turn diverges.

## Tickets filed
- none
