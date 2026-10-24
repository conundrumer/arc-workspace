# f3cdc58f

## Concept
- The concept fits every pair: each color's cell count is the length of its bar. The bars stand on the bottom edge, at cols 0–3 in `bar_order` 1, 2, 3, 4, in a frame the size of the input. `work/task/f3cdc58f/check_concept.py` reproduces train0–2 and test0.
- Every rule has a relational form: a count of cells per color, and a rank in a stored order. The concept has no witness with verdict `other`.
- Two branches fit every pair. Each is separated from the concept only on an input that breaks an invariant of the inputs: a missing color for `$PackBars`, and a size other than 10×10 for `$StoredFrame`.

## Choice points
- `count-unit`: what a bar's length counts
    - `concept`: the cells of its color
    - `$CountObjects`: replaces `bar-height`: a bar's length is the count of 4-connected components of its color. Parameters as the concept's, undefined nowhere. Fails Fit at train0: the 4s at (1,8), (2,8) form one component, so the bar is 5 long, and the output's is 6. It also fails train1 (3s at (0,7), (0,8)) and test0.
    - `$CountObjects8`: replaces `bar-height`: the count of 8-connected components of its color. Parameters as the concept's, undefined nowhere. Fails Fit at train0: 4 components of color 4 against a bar of 6.
- `bar-order`: which slot each bar takes
    - `concept`: the slot of the color's rank in the stored `bar_order`
    - `$SortByCount`: replaces `bar-position` and drops `bar_order`: the bars stand in ascending count from `start_side`, and bars of equal count tie. Undefined nowhere. Fails Fit at train0: the counts 8, 4, 2, 6 put the bars in the order 3, 2, 4, 1, and the output has 1, 2, 3, 4.
- `empty-slot`: what a color with no cell does to the slots
    - `concept`: it keeps its slot, which stays `background`
    - `$PackBars`: replaces `bar-position`: a color's bar stands at its rank among the `bar_order` colors the input holds. Parameters as the concept's, undefined nowhere. Fits every pair. Witness `absent-color`: train2's input with its 2s cleared. It stands at the stored assignment, breaks no scene claim, and is `variant` with verdict `concept`. It breaks the invariant that every input holds each of 1–4 at least twice.
- `output-frame`: the output's size
    - `concept`: the input's size
    - `$StoredFrame`: replaces the size in `bar-per-color`: a stored output size of 10×10, the value ConstOutDimAxis gives. Undefined nowhere. Fits every pair. Witness `$StoredFrame`: train2's input without rows 0–1, an 8×10 grid. It stands at the stored assignment, breaks no scene claim, and is `variant` with verdict `concept`. It breaks the invariant that every input is 10×10.
    - `$CropToChart`: replaces the size in `bar-per-color`: the output is as long as the longest bar on the base axis, and as wide as the count of `bar_order` colors on the other axis. Undefined nowhere. Fails Fit at train0: it gives 8×4, and the output is 10×10.
- `count-unit` & `bar-order`, `count-unit` & `empty-slot`, `count-unit` & `output-frame`, `bar-order` & `empty-slot`, `bar-order` & `output-frame`, `empty-slot` & `output-frame`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A color's slot read from its color number (col = color − 1): colors have identity and no other properties, so this derivation is not equivariant under color permutations. Its order is also the stored `bar_order` of this task.
- `bar_order` derived by a proposer: CountRankAsc and CountRankDesc give no rank that is the same in every example, because the counts differ from input to input. No other proposer gives an order over colors.
- `base_side` or `start_side` derived from the input: no input distinguishes one edge, so the orientation has no source to derive it from.
- A bar longer than the grid, clipped or undefined: the `counts-fit-height` scene claim excludes it, and no pair or reading gives a claim about it.
- A bar for a color outside `palette`: the `scattered-marks` scene claim excludes such colors. A slot for them needs an order over colors that `bar_order` does not hold, and only color numbers would give one.

## Tickets filed
- none
