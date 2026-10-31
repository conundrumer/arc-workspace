# da6e95e5

## Departures
- The solver adds the branch `inset=TileDim` (a `@derive TileDim` line on `inset` under `$FrameInset`), with the witness `inset=TileDim`, which the Analyze files do not give: Develop step 4 holds every built-in derivation that fits, and `derive` reported that TileDim fits `inset`.
- The witness file holds the witness `inset=TileDim` beside `wide-frame`: the `@derive` branch needs a witness with that id, and `witness` needed a run that shows `$FrameInset & inset=TileDim` defined and different from `$FrameInset`.

## Judgments
- Concept-branch constructor is named `ShapeBox`: `analyze.md` names the concept branch of `crop window` only as `concept`.
- `$FourAdjacent` and `$MostCommonColor` have no constructor: `analyze.md` gives them no witness, and each one fails Fit (at test0 and at train2).
- No Not formed item became a branch: the interior crop is `$FrameInset` at `inset` 1; the unique-color reading fails Fit at train0; the commonest-frame-color reading fails Fit at train2; the several-matches reading adds an output that nothing supports; and "the frame found from the colored cells nearest a shape" does not state one model.
- Background is derived as the commonest color (`Mode`): the concept file gives no parameter, and the background color is different between pairs (3, 8, 4, 4, 1).
- Frame parse: a bracket corner is a non-background cell whose two arms run away from its corner's edges. A frame is the box that two bracket corners of one color at opposite corners bound (`Bbox`), with a bracket corner of that color at each of its four corners. The shape is the one 8-connected one-color piece in the box interior (`Unanimous`), and it is a shape only when none of its cells is outside the interior. The interior test rejects spurious boxes that span several same-colored frames, such as in train1, where all five frames are color 1.
- Pieces are keyed by color (`Components8<[Key, Color]>`), so a shape is one-color as `framed-shape` states, and "the shape's color equals the frame's color" is the piece key.
- Determination of `inset`: `determination-plan` said that TileCount covers the value from a fact that the concept does not use. So `Determine` reads `inset` as the margin between the matched frame and its shape's box, the same on all four sides and in each train example. The frame parse moved into `Parse<Key>`, which the program and `Determine` share. After that, the plan printed no actions.
- Witness `inset=TileDim`: plausibility `borderline`, verdict `concept`. The input is 9×19, with three 5×5 frames, each around a one-cell shape. On that input alone, TileDim gives 1 and not 2, so the derived case crops the 3×3 frame interior, and the stored inset crops the one-cell shape. The grid size and the one-cell shapes are far from the 30×30 inputs and 2×2 to 4×5 shapes of the task, so the generator would make this input only under unusual conditions. The generator would pair it with the shape crop.
- Deletions judged as kept: `diag_opposite` in `span.cell` states that the two corners are opposite corners, and it limits the pairs. `spills` states that the shape is clear of the frame's sides, which spurious boxes need. `uniform_inset` in `margin` states that the margin is the same on every side. `contradicted` is the universal over the train examples. The redundant `cell`/`!bg` atoms in `inner.item` were removed, because `piece.label` implies them.
- Hints: lint gave three `claim` findings (fixed by `@claim` lines) and one `long-clause` finding (fixed by wrapping). No performance issue: each pairs run finished in at most 2 s.
- Keywords: `objects crop select match`.

## Unsettled
- In `deletions`, the runs for `bg_mode.item`, `bg`, and `!bg` in `bracket_corner` timed out after 2 s on train 0, so no finding was made for those deletions: a `deletions` run with a longer per-run limit would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
