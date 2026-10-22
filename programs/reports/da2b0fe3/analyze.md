# da2b0fe3

## Concept
- The concept fits every train and test pair (`work/task/da2b0fe3/probe.py`). Its rules have a relational form: the gap lines are the rows and columns of the figure's bounding box that hold no figure cell. No witness has verdict `other`.
- Each pair shows one gap line, on the row axis in train0, train1 and test0, and on the column axis in train2 and test1. The two parts are not of equal size (train1: three rows above the gap and two below; train2: three columns left of the gap and two right), so the line is not the center of the figure.

## Choice points
- `line-place`: which lines are drawn
    - `concept`: every row and column that crosses the figure's bounding box and holds no figure cell (`gap-lines`)
    - `$GapCenter`: replaces `gap-lines`; in each run of adjacent gap lines only the center line is drawn, and the model is undefined where a run has an even width. It fits every pair. Witness `wide-gap` breaks `one-gap-line`, at the stored assignment; plausibility `borderline`, verdict `any`; the invariant it breaks is that the gap is one line wide. On it, concept fills the three gap rows and `$GapCenter` fills row 4 only. It is not subsumed and stands as a case.
    - `$BboxCenter`: replaces `gap-lines`; the line drawn is the center line of the figure's bounding box on the gap's axis, and the model is undefined where that extent is even. It fails Fit at train1 (the bounding box covers rows 1–6 and has no center row).
    - `$MirrorAxis`: replaces `gap-lines`; the line drawn is the figure's mirror axis, and the model is undefined where the figure has no mirror axis on a line. It fails Fit at train1 (the figure is not symmetric about any row).
- `line-extent`: how far a drawn line runs
    - `concept`: across the whole grid (`full-span`)
    - `$BboxExtent`: replaces `full-span`; the line runs only across the figure's bounding box. It fails Fit at train0 (the output fills row 4 at cols 0–1 and 6–9).
- `gap-count`: the inputs on which the model is defined
    - `concept`: any number of gap lines, on either axis or both
    - `$SingleGap`: adds `one-gap-line` as a rule; the model is undefined unless exactly one gap line exists. It fits every pair. Witness `two-axis-gaps` breaks `one-gap-line`, at the stored assignment; plausibility `variant`, verdict `concept`; the invariant it breaks is that the gap lies on one axis only. On it, concept draws row 3 and col 3, and `$SingleGap` is undefined. Where `$SingleGap` is defined, its output is the concept's, so it fails Subsumption.
- `figure-parse`: how the figure is read
    - `concept`: as one set of cells
    - `$TwoParts`: replaces `one-figure` with a figure of exactly two 4-connected parts, and `gap-lines` with the lines between the two parts' bounding boxes; the model is undefined unless the figure has exactly two parts with a band of lines between them. It fits every pair. Witness `split-half` breaks no scene claim, at the stored assignment; plausibility `variant`, verdict `concept`; the invariant it breaks is that each side of the gap is one 4-connected piece. On it, concept draws row 3, and `$TwoParts` is undefined. A connected part has a cell in every row and column of its bounding box. So with two parts, the empty lines of the figure's bounding box are exactly the lines between the parts, and where `$TwoParts` is defined its output is the concept's. It fails Subsumption.
- `line-place` & `line-extent`, `line-place` & `figure-parse`, `line-extent` & `gap-count`, `line-extent` & `figure-parse`, `gap-count` & `figure-parse`: the two branches' changes applied together
- `line-place` & `gap-count`: `$BboxCenter` & `$SingleGap` and `$MirrorAxis` & `$SingleGap` apply the two branches' changes together
    - `$GapCenter` & `$SingleGap`: the model of `$SingleGap` alone, since a single gap line is the center of its own run; the property of `line-place` that `$GapCenter` changes does not exist with `$SingleGap`

## Open parameters
- none

## Not formed
- `line_color` derived from the input: the value 3 is in no input, and every output draws 3 whatever the figure's color, so no derivation from the input gives it.
- A drawn line that keeps or stops at other content on its path: under `one-figure`, no non-background cell lies on a gap line, and no pair, solver header or lib component points to such a rule.
- `$TwoParts` with 8-adjacency: the adjacency type changes only where `$TwoParts` is defined, and its output there is still the concept's, so it gives no output the concept does not give.

## Tickets filed
- none
