# d8c310e9

## Concept
- The concept case fits every pair (probe `work/task/d8c310e9/probe.py`): the smallest column period of the segment is 3, 4, 6 on the train pairs and 4 on the test.
- The rule `period` has a relational form: it compares each column of the segment with the column p further along `dir`.
- No witness with verdict `other`: where the segment admits a period shorter than the tile the generator drew, the shown cells hold no trace of the longer tile, and a person takes the shortest one too.

## Choice points
- `background`
    - `concept`: `bg` is stored, 0
    - `bg=DominantColor`: `bg` is derived on each input as its commonest color, each tied color giving its own output; replaces the stored `bg` read by `background`; defined on every input. Fits every pair. Witness `bg=DominantColor`: breaks no scene claim; stands at the stored assignment; `variant`, verdict `concept`; breaks the invariant that 0 is the commonest color of each input (55 to 64 of the 75 cells).
- `direction`
    - `concept`: `dir` is stored, right
    - `$DirFromScene`: `dir` is derived on each input as each direction d such that the ink starts at the edge opposite d, stops short of the edge toward d, and is periodic along d with a period less than its extent; replaces the stored `dir` read by `segment-at-edge`, `period` and `extend`; undefined on an input where no direction meets that. Fits every pair (it gives right on each). Witness `mirrored-scene` (train0's input mirrored left to right): breaks `segment-at-edge`; stands at the stored assignment; `variant`, verdict `$DirFromScene`; breaks the invariant that the ink starts at the left edge.
- `period`
    - `concept`: one period for the whole segment, the smallest period of its columns
    - `$PerLine`: replaces `period` and `extend`: each row along `dir` repeats on its own, by the smallest period of its run from the start edge to its last non-`bg` cell, and a row with no ink stays `bg`; defined on every input. Fits every pair. Witness `short-row-run` (train1's input cut after col 5): breaks no scene claim; stands at the stored assignment; `ordinary`, verdict `concept`.
    - `$GroundPeriod`: replaces `period`: the period is the smallest period of the ground line's run across the segment, and every column repeats by it; the `ground` edge (bottom) becomes a parameter that the program reads; defined on every input. Fits every pair. Witness `ground-faster`: breaks no scene claim; stands at the stored assignment; `ordinary`, verdict `concept`.
    - `$FirstRecur`: replaces `period`: the period is the distance from the first column of the segment to the next column equal to it; defined on every input. Fails Fit at train1, where col 1 equals col 0 and the period comes out 1.
- `background` & `direction`, `background` & `period`, `direction` & `period`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored period: the train pairs need periods 3, 4 and 6, so no stored value fits.
- A period from the next cell of the ground line's first color: col 1 of train1 is 3 again, so it gives period 1 and fails train1, as `$FirstRecur` does.
- A phase counted back from the segment's end: on every input it gives the same cells as repeating from the start edge, since the segment is periodic by the smallest period.
- A derived `ground` edge: only `$GroundPeriod` reads it, and on every input the ink's one full line along `dir` lies on the bottom edge, so no input separates a derived edge from the stored one under that branch while `segment-on-ground` holds.

## Tickets filed
- none
