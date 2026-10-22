# c8cbb738

## Concept
- The concept fits every pair, and the probe `probe.py` reproduces each train output and the test output.
- Each rule has a relational form: the shared center is the midpoint of each figure's bounding box, which `Bbox` gives, and the output side is the largest extent of those boxes. No rule is approximated.
- The concept is undefined where a figure's extent and the output side differ in parity, and where two figures land on one output cell. No input in the evidence shows either.
- No witness has verdict `other`.

## Choice points
- `output-frame`
    - `concept`: the output is a square whose side is the largest height or width of any figure's bounding box.
    - `$UnionFrame`: replaces `output-is-largest-box`. The output's height is the largest figure height and its width the largest figure width, so the output is the bounding box of the centered figures. It has no parameters, and it is undefined where the concept is. It fits every pair. Witness `no-square-figure`: it breaks `largest-figure-is-square`, and it stands at the stored assignment. Plausibility `variant`, verdict `$UnionFrame`. It breaks the invariant that one figure in each input is a square whose side is at least every other figure's height and width.
    - `$SquareFigureFrame`: replaces `output-is-largest-box`. The output is the bounding box of the largest figure whose bounding box is a square, and marks that fall outside it are dropped. It has no parameters. It is undefined where no figure's bounding box is a square, and where the concept is undefined. It fits every pair. Witness `rectangle-outgrows-square`: it breaks `largest-figure-is-square`, and it stands at the stored assignment. Plausibility `borderline`, verdict `$UnionFrame`. It breaks the invariant that the square figure is at least as wide and as tall as every other figure.
- `background`
    - `concept`: the background is the most common color of the input.
    - `$CornerBackground`: replaces how `plain-background` finds the background color. The background is the color of the top-left cell. It has no parameters, and it is undefined where the concept is. It fits every pair. Witness `mark-on-corner`: it breaks no scene claim, and it stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
    - `$StoredBackground`: replaces how `plain-background` finds the background color. A stored parameter gives the background color. It fails Fit at train1, whose background is 1, while train0's background is 3.
- `output-frame` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Two figures of one color: the concept reads each color class as one figure. A branch that splits a color class into four-mark figures is not formed, for these reasons. No pair shows a color with more than four marks, and the split of a set of marks into mirror-symmetric quadruples is not unique (the corners and edge midpoints of a 3x3 box split in more than one way).
- A filter that keeps only color classes of `marks-per-figure` cells: every color class in the evidence has four cells, and no pair shows a mark that a filter would drop. The pairs give no source for that reading.
- Layer order where two figures land on one output cell: no pair shows an overlap, and the pairs show no order among figures to rank by. Every model formed here is undefined there.
- Rounding where a figure's extent and the output side differ in parity: no pair shows it. A rounding direction is not a claim the pairs make, and every model formed here is undefined there.
- Alignment by the centroid of each figure: a mean has no relational form. Also, on mirror-symmetric figures it is the bounding-box center.

## Tickets filed
- none
