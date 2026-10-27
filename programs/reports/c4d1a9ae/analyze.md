# c4d1a9ae

## Concept
- Fits train0, train1 and test0 at `source-dir` R, with the background derived per input as the commonest color (4, 0, 5).
- The concept file's rules state the rule exactly, with no approximation, and no witness has the verdict `other`.
- The concept is undefined where the commonest color ties, where a column run between full background columns holds other than one ink color, and where fewer than two panels stand.

## Choice points
- `panel-region`
    - `concept`: each panel is a maximal run of columns, along the axis of `source-dir`, that are not full background lines, and it fills over the run's whole extent across that axis.
    - `$ColorSpan`: replaces `separator-columns` and `one-color-panel`: each ink color is a panel, whose region is the full lines from the first to the last line its cells reach along the axis of `source-dir`, and the panels are ordered by that span; no parameter; undefined where two colors' spans overlap or fewer than two ink colors stand. Fits every pair. Witness `two-color-panel`: breaks `one-color-panel`; stands at the stored assignment; plausibility `borderline`; verdict `$ColorSpan`; the invariant it breaks: in every input, the columns between two full background columns hold one ink color.
    - `$ColorBbox`: replaces `separator-columns` and `one-color-panel`: each ink color is a panel whose region is the bounding box of its cells; undefined where two colors' boxes overlap. Fails Fit at train1: row 0 holds no ink in cols 0–2 or col 4, and the output fills train1 output (0,0)–(0,2) with 3 and (0,4) with 9.
    - `$EqualDivide`: replaces `separator-columns`: the grid divides along the axis of `source-dir` into n equal panels with gaps one line wide, n being the number of ink colors; undefined where the extent does not divide so, or a tile holds other than one ink color. Fails Fit at train1: panel A spans cols 0–2 and panel B col 4, and the division gives cols 0–1, 3–4, 6–7, so train1 input (3,2) and (7,2) of ink 4 sit in a gap and train1 output col 2 is filled with 3.
- `fill-color`
    - `concept`: a panel's background cells take the ink color of the panel next to it toward `source-dir`, and the last panel takes the first panel's.
    - `$StoredMap`: replaces `fill-from-next` and `wrap`: a stored table maps each panel's ink color to its fill color (2→6, 6→5, 5→2, 4→3, 3→9, 9→4); reads only the axis of `source-dir`; undefined where a panel's ink color is not a key. Fails Fit at test0: ink 8 is an unseen key, and ink 6 maps to 5 where test0 output fills with 9.
- `background`
    - `concept`: the background is the commonest color of the input.
    - `$BgSeparatorColor`: replaces `background`: the background is the one color of the full single-color lines across the axis of `source-dir` that have a line holding another color on each side; undefined where those lines hold more than one color or none stand. Fits every pair. Witness `dense-panel`: breaks `background`; stands at the stored assignment; plausibility `borderline`; verdict `$BgSeparatorColor`; the invariant it breaks: in every input the background outnumbers each ink color by more than 2 to 1 (train0 45 to 15, train1 56 to 10, test0 43 to 15).
    - `$BgLineColor`: replaces `background`: the background is the one color of every full single-color line across the axis of `source-dir`; undefined where those lines hold more than one color. Fails Fit at train0: col 7 is a full line of 5 beside cols 2 and 5 of 4.
    - `$BgStored`: replaces `background`: the background is a stored color. Fails Fit at train0 or train1, whichever its value misses, since their backgrounds are 4 and 0.
- `panel-region` & `fill-color`, `panel-region` & `background`, `fill-color` & `background`: the two branches' changes applied together

## Not formed
- Order of panels by color value or by cell count in place of position: train0 refutes it, since its inks in position order are 2, 6, 5 and panel 2 fills with 6, where an order by value gives 5.
- A last panel that takes its own neighbor's color in place of the wrap: train0 cols 6–7 fill with 2, the first panel's ink, and not 6.
- Separator lines that fill too: every pair keeps them in the background color.
- Another wrap at four or more panels, such as the last panel taking the panel two back: it agrees with the cyclic wrap at three panels, and no reading of the concept gives it.
- Panels as connected objects: train1 col 4 holds five unconnected cells of 3, and an object's fill region would be its bounding box, as `$ColorBbox` states, which fails train1.
- A derived `source-dir`: no proposer in `programs/proposers.dl` gives a direction.

## Tickets filed
- 10-511_task_c4d1a9ae_analyze.md
- 10-512_task_c4d1a9ae_analyze.md
