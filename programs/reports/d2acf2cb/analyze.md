# d2acf2cb

## Concept
- Fits every pair at `marker` = `4` and `recolor` = `0` to `8`, `6` to `7` (the canonical patch swaps train2's input and output, and the patched pair fits).
- No witness has verdict `other`. The concept is undefined where a marked line holds a color that `recolor` has no key for (witness `third-color`), and there the verdict goes to `$KeepUnmapped`.
- `probe.py` runs every branch over the pairs, and `make_witnesses.py` builds `witnesses.json` from edits of train0's input.

## Choice points
- `line-family`: which lines a pair of markers can mark
    - `concept`: rows and columns, both axes in every input
    - `$WithDiagonals`: rows, columns and both diagonal directions; adds to `marker-pairs` the case of a marker facing another across the grid on a diagonal; parameters unchanged; undefined nowhere the concept is defined. Fits every pair. Witness `diagonal-pair`: markers at (0,2) and (6,8) of train0's input; breaks `marker-pairs`; `foreign`, verdict `$WithDiagonals`; breaks the invariant that every marker faces another marker on its own row or column.
    - `$StoredAxis`: lines along one stored `axis` only; replaces `one-axis` with a task-wide axis. Fails Fit: at rows it fails train2 (and test0), at columns it fails train0 (and train1).
- `segment`: which cells of a line are recoded
    - `concept`: the cells strictly between the two markers that sit at the two ends of the line
    - `$Between`: every cell with a marker on each side along its row or column, wherever the markers sit; replaces `marker-pairs` and `recode-between`. Fails Fit at train1: column 0 holds markers at rows 1, 4 and 7, so rows 2, 3, 5 and 6 of that column would be recoded (also train2 row 0, test0 row 0).
    - `$OneEnd`: a line with a marker at either end has each of its non-marker cells recoded; replaces `marker-pairs` and `recode-between`. Fits every pair. Witness `lone-marker`: train0's input with (5,8) set to `0`; breaks `marker-pairs`; `borderline`, verdict `concept`; breaks the invariant that every marker has a partner on the opposite edge.
- `recode`: how a cell of a marked line takes its color
    - `concept`: the stored map `recolor`, keyed by input color
    - `$BackgroundElse`: parameters `bg`, `bg_to`, `other_to`; a cell of `bg` takes `bg_to`, and any other cell takes `other_to`; replaces `recode-between` and `recodable-field`; undefined nowhere. Fits every pair. Witness `third-color`: a `2` at (5,4) of train0's input; breaks `recodable-field`; `borderline`, verdict `$KeepUnmapped`; breaks the invariant that every non-marker cell is `0` or `6`.
- `unmapped`: what a cell of a marked line does when `recolor` has no key for its color
    - `concept`: no output color, so the model is undefined on that input
    - `$KeepUnmapped`: the cell keeps its color; replaces `recodable-field`. Fits every pair. Witness `third-color`, as above.
- `marker`: where the marker color comes from
    - `concept`: stored
    - `marker=RarestColor`: the rarest color of the input, ties included; undefined nowhere. Fits every pair (4 is the rarest color of every input). Witness `marker=RarestColor`: train0's input with every `0` except (0,0) set to `6`; breaks no scene claim; `variant`, verdict `concept`; breaks the invariant that `4` is the rarest color of every input (each input holds at least 25 cells of each of `0` and `6`).
    - `marker=DominantColor`: the commonest color of the input. Fails Fit at train0 (marker `6` marks row 1 and recodes it).
    - `marker=SharedColor`: every color of the input. Fails Fit at train0 (every line is marked).
    - `marker=VanishedColor`: with no train output in the run, every color of the input. Fails Fit at train0, as `marker=SharedColor`.
- `recolor`: where the recolor map comes from
    - `concept`: stored
    - `recolor=ChangedPairs`: read off the cells that change; with no train output in the run it gives no value, so the model is undefined on every input. Fails Fit at train0.
    - `recolor=VanishedNewPairs`: undefined on every input for the same reason. Fails Fit at train0.
- `line-family` & `segment`, `line-family` & `recode`, `line-family` & `unmapped`, `line-family` & `marker`, `line-family` & `recolor`, `segment` & `recode`, `segment` & `unmapped`, `segment` & `marker`, `segment` & `recolor`, `recode` & `marker`, `unmapped` & `marker`, `unmapped` & `recolor`, `marker` & `recolor`: the two branches' changes applied together
- `recode` & `unmapped`: the `unmapped` property exists only with the map that the concept branch of `recode` reads, so `unmapped` stands at the concept
    - `$BackgroundElse` & `$KeepUnmapped`: the `$BackgroundElse` model alone
- `recode` & `recolor`: the `recolor` property exists only with the map that the concept branch of `recode` reads, so `recolor` stands at the concept
    - `$BackgroundElse` & `recolor=ChangedPairs`: the `$BackgroundElse` model alone
    - `$BackgroundElse` & `recolor=VanishedNewPairs`: the `$BackgroundElse` model alone

## Open parameters
- none

## Not formed
- Markers removed or recolored in the output: every pair keeps them.
- A recode that alternates along the line, or depends on a cell's position: every `0` in a marked line becomes `8` and every `6` becomes `7`, wherever it sits.
- A derivation of `recolor`, `fg_to`, `bg_to` or `other_to` from the input alone: no proposer reads one off an input, and the output colors `7` and `8` occur in no input.
- `marker=CountRankAsc` and `marker=CountRankDesc`: they rank every color, and give no single marker color.

## Tickets filed
- none
