# aee291af

## Concept
- Fits every pair (probe.py): a box is a maximal square with a 1-wide border of `frame_color`, an interior of `frame_color` and `mark_color` cells, and at least one mark; the output is the box whose pattern no other box shows.
- The rule has a relational form. The generator applies it as stated, so it is not an approximation.
- No witness has the verdict `other`.
- The concept case's model is subsumed by `$RarestPattern`'s. The Subsumption condition does not apply to the concept case.

## Choice points
- `box-finding`
    - `concept`: a box is a maximal square with an all-`frame_color` border and an interior of `frame_color` and `mark_color` cells, holding a mark.
    - `$MarkBbox`: replaces `boxes`. A box is the bounding box of the marks of one 8-connected component of non-background cells, grown by 1 on each side. Parameters `frame_color`, `mark_color`, and `background` for the components. Undefined where a grown box reaches past the grid edge. Fits every pair. Witness `odd-pattern-off-interior-edge`: train0 input with (11,10) set to `8`, so the odd box's interior bottom row has no marks. It breaks `boxes`, stands at the stored assignment, and is `variant` with verdict `concept`. Invariant broken: in every box, the marks reach every side of the interior. `$MarkBbox` outputs the 3x4 crop `8 8 8 8 / 8 2 2 8 / 8 8 8 8`, and the concept outputs the whole 4x4 box.
    - `$ComponentBbox`: replaces `boxes`. A box is the bounding box of a 4-connected component of non-background cells that holds a mark. Fails Fit on train0: stray cells that touch boxes widen the boxes' bounding boxes, and more than one widened box is unique.
- `odd-selection`
    - `concept`: the box whose pattern occurs once, and is undefined unless exactly one box has such a pattern.
    - `$RarestPattern`: replaces `odd-box` and `one-odd`. The output is the pattern with the lowest count, and the model is undefined when the lowest count is tied. Fits every pair. Witness `odd-pattern-twice`: test0 input with the box at rows 10–14, cols 0–4 given the odd pattern, so three boxes show one pattern and two boxes show another. The concept is undefined there, and `$RarestPattern` outputs the pattern shown twice. It breaks `one-odd`, stands at the stored assignment, and is `borderline` with verdict `$RarestPattern`. Invariant broken: in every input, all boxes but one share a pattern.
    - `$OffMode`: replaces `odd-box` and `one-odd`. The output is the one pattern that differs from the unique commonest pattern. The model is undefined when the commonest pattern is tied or when more than one other pattern occurs. Fits every pair. Witness `odd-pattern-twice` (as for `$RarestPattern`): `$OffMode` gives the same output as `$RarestPattern`, at `borderline` with verdict `$RarestPattern`, and breaks the same claim and invariant. Fails Subsumption. Wherever `$OffMode` is defined, the one other pattern has a lower count than the unique commonest pattern, so it is the unique rarest pattern and `$RarestPattern` gives it too.
    - `$CongruentPattern`: replaces `odd-box`. Patterns are compared up to D4. Fails Fit on train0: the odd pattern `2 2 / 8 2` is the left-right mirror of the common pattern `2 2 / 2 8`, so no box is unique.
- `mark_color`
    - `concept`: stored, `2`.
    - `mark_color=RarestColor`: replaces the stored `mark_color` with the input's rarest color. Undefined where the rarest color is tied. Fits every pair. Witness `mark_color=RarestColor`: a 21x27 input with three 9x9 boxes whose interiors are almost all marks, plus one solid 3x3 block of `8`. The rarest color is `8`, so the only box found is that block, and the branch outputs a 3x3 grid of `8`. The concept outputs the box whose pattern is unique. The witness breaks `field`, stands at the stored assignment, and is `borderline` with verdict `concept`. Invariant broken: in every input, `mark_color` is the rarest color, and cells of `frame_color` outside boxes are single stray cells.
- `box-finding` & `odd-selection`, `box-finding` & `mark_color`, `odd-selection` & `mark_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored box size: the box size is 4 in train0 and train1, and 5 in train2 and test0, so the box size is derived from the input.
- A derived `frame_color`: no proposer gives it one value. `SharedColor` gives every color of each input, `DominantColor` gives the background, and `RarestColor` gives the mark color.
- Selection by mark count: every box in train0 holds 3 marks, so mark count cannot pick the odd box.
- Output of the interior alone: every output holds the box's border.
- Marks grouped by their own 8-connected components: the common box pattern in test0 (`2 2 8 / 2 8 8 / 8 8 2`) has a mark that touches no other mark, so one box would split into two groups.

## Tickets filed
- none
