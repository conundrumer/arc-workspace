# ce8d95cc

## Concept
- Fits every train pair and the test pair (`probe.py`). It reads no parameter. Row dedupe and column dedupe commute, so the order of the two rules is not a choice point. No witness has verdict `other`. The same mechanism is in solver e1baa8a4 (consecutive identical grid lines collapse, per axis).

## Choice points
- `squeeze`: which rows and columns the output keeps
    - `concept`: each run of identical adjacent rows, then of columns, is kept once (`dedupe-rows`, `dedupe-columns`)
    - `$GapCollapse`: replaces `dedupe-rows` and `dedupe-columns`. Each run of adjacent rows that hold a `background` cell is kept once, then the same for columns. It reads `background` (`0`) as a parameter. It is defined on every input. Standing: it fits every pair. Its witness is `thick-line`, which breaks `lines-apart` and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. The invariant it breaks: in every input, no two lines of one axis are adjacent.
    - `$Rebuild`: replaces `dedupe-rows` and `dedupe-columns`. The output draws each input line once, in order, with one `background` line before each line, between each two lines and after the last line, and with crossings taken from the input. It reads `background` (`0`) as a parameter. It is defined on every input. Standing: it fits every pair. Its witness is `edge-line`, which breaks `lines-apart` and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. The invariant it breaks: in every input, the first and last rows and columns are background lines.

## Open parameters
- none

## Not formed
- Columns first, then rows: row dedupe and column dedupe commute, so this model is the concept's model.
- Keep each distinct row once, wherever it occurs: it fails every train pair, because the background rows occur in several separate runs and the output keeps each run.
- Downscale by a fixed factor or a fixed tile size: the gaps in one input have unequal widths (train0 rows 2–5 and 7–9), so no factor fits.
- Keep the first row of a run, or another row of it: a run's rows are identical in every model, so the choice changes no output.

## Tickets filed
- none
