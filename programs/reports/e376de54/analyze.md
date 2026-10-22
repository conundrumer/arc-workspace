# e376de54

## Concept
- The concept fits every train pair and the test pair (`work/task/e376de54/probe.py`). The middle line by position has lengths 6, 7, 4 and 4 in train0, train1, train2 and test0.
- No witness has the verdict `other`. The rule `match-middle` is stated as the generator applies it, and it has a relational form: the middle line is the segment with as many segments before it as after it along the common start line.

## Choice points
- `reference-length`: which length every line takes
    - `concept`: the length of the middle line by position along the common start line
    - `$SecondLongest`: replaces `middle-line` and `match-middle`: every line takes the second-largest distinct length among the lines; it is undefined on inputs whose lines all have one length. It fits every pair. Witness `second-longest-length`: it breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$MedianLength`: replaces `middle-line` and `match-middle`: every line takes the median of the line lengths; it is undefined on inputs with an even line count. It fails Fit at train0, where the median is 4 and the output has 6.
    - `$ModeLength`: replaces `middle-line` and `match-middle`: every line takes the commonest line length; it is undefined where two lengths tie as commonest. It fails Fit at train0, where the lengths 3, 2, 6, 9, 4 have no commonest one.
    - `$StoredColorRef`: replaces `middle-line` and `match-middle`: every line takes the length of the one line of color `ref_color` (9); it is undefined on inputs with no line, or more than one line, of that color. It fails Fit at train2, which has no line of color 9.
- `past-edge`: what a line does when its new length would carry it past the grid edge
    - `concept`: the line stops at the grid edge
    - `$RefusePastEdge`: adds to `match-middle`: the model is undefined on inputs where a line set to the middle line's length would pass the grid edge. It fits every pair. Witness `extension-past-edge`: it breaks no scene claim, plausibility `borderline`, verdict `concept`. It breaks the invariant of the inputs that every line, set to the middle line's length from its start, stays inside the grid. Its model is defined only where the concept is defined, and gives the concept's output there, so it fails Subsumption.
- `bg`: where the field color comes from
    - `concept`: the stored value 7
    - `bg=DominantColor`: replaces the stored `bg` in `field` and `keep-field`: `bg` is the commonest color of the input; it is undefined where two colors tie as commonest. It fits every pair. Witness `bg=DominantColor`: it breaks the scene claim `field` at `bg` = 7, plausibility `variant`, verdict `bg=DominantColor`. It breaks the invariant of the inputs that the field color is 7.
    - `bg=SharedColor`: replaces the stored `bg`: `bg` is each color present in the input. It fails Fit at train0, where it gives the four values 1, 2, 7 and 9.
    - `bg=RarestColor`: replaces the stored `bg`: `bg` is the least common color of the input. It fails Fit at train0, where it gives 2.
- `reference-length` & `past-edge`, `reference-length` & `bg`, `past-edge` & `bg`: the two branches' changes applied together

## Open parameters
none

## Not formed
- The mean line length: a mean counts nothing the task has, so it has no relational form; on train0 it is 24/5, which is no length.
- Each color class as one line: train0 has two lines of color 2 and two of color 1, so the reading fails train0.
- Trim and extend at the common start, with the free end kept: the outputs keep every start, so the reading fails every pair.
- The start at the end nearer the grid edge: in train1 the line of color 3 ends at col 14, one cell from the right edge, and its output keeps the left end at col 3, so the reading fails train1.
- A middle line for an even line count: every input has an odd count, and no pair, solver header, lib component or proposer gives a reading of which inner line acts.
- The `bg` proposers that read `ex_out` (`OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs`, `VanishedNewPairs`): a run on one input has `ex_out` empty, so they give no single `bg` value there.

## Tickets filed
none
