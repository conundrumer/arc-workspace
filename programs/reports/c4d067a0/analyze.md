# c4d067a0

## Concept
- Fits every pair: train0–2 and test0 each give the paired output (`check_concept.py`, `probe.py`). Every claim has a relational form. No witness has the verdict `other`, and the rules need no approximation. Every pair has exactly one key run that matches the given blocks: key row 0 in train0 and train1, key row 2 in train2, and key row 1 from column 1 in test0. In each input, the scale is read off the given blocks: k = 3 and g = 2 in train0, k = 2 and g = 1 in train1, k = 2 and g = 3 in train2, and k = 4 and g = 1 in test0.

## Choice points
- `key-pitch`
    - `concept`: stored `key-pitch` = 2.
    - `$KeyPitchFromKey`: replaces `key-period`'s stored pitch with the pitch derived from the key, which is the gcd of the dots' row and column offsets from the key's top-left dot. It is undefined where the key has one dot. It fits every pair. Witness `key-pitch-three` is a key with dots three cells apart. It stands at the stored assignment and breaks `key-period` (pitch 2). Plausibility `variant`, verdict `$KeyPitchFromKey`. The concept is undefined on it, because no run at pitch 2 matches the blocks.
- `block-size`
    - `concept`: k is read from the given blocks.
    - `$StoredBlockSize`: replaces `enlarge-key`'s k with a stored value. It fails Fit at train1, because k is 3 in train0 and 2 in train1.
- `gap`
    - `concept`: g is read between the given blocks and used on both axes.
    - `$StoredGap`: replaces `enlarge-key`'s g on both axes with a stored value. It fails Fit at train1, because g is 2 in train0 and 1 in train1.
    - `$StoredCrossGap`: replaces `enlarge-key`'s g across the blocks' line with a stored value, and keeps g along the line as the gap read between the blocks. It fails Fit at train1, because the vertical gap is 2 in train0 and 1 in train1.
- `background`
    - `concept`: the commonest color of the input.
    - `$StoredBackground`: replaces `background` with a stored color. It fails Fit at train2, because the background is 8 in train0 and 1 in train2.
    - `$BackgroundAtCorners`: replaces `background` with the color that the four grid corners share. It is undefined where the corners differ. It fits every pair. Witness `block-at-grid-corner` has a given block that fills the top-right corner. It breaks no scene claim. Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: every given block stands at least one cell in from each grid edge.
- `anchor`
    - `concept`: `anchor-by-match`, which means the given blocks land on the drawing of the key run whose colors they match.
    - `$AnchorAtKeyStart`: replaces `anchor-by-match`. The given blocks are the drawing of the run that starts at the key's top-left point. It fails Fit at train2, where the blocks 3 4 are key row 2.
- `drawing-turn`
    - `concept`: the drawing is the key unturned.
    - `$TurnedDrawing`: adds a D4 transform of the key, which is chosen by which turned keys have a run that matches the given blocks. It fails Fit at train0. In train0, the half turn and the top-bottom flip also match 4 4, and they draw the key's rows of 1 above the blocks, so the reading gives two drawings. In train2, the transpose matches 3 4 and gives a second drawing that also fits inside the grid.
- `run-spacing`
    - `concept`: `blocks-match-key`, which means the given blocks are the drawing of neighboring key dots, so the pitch is the distance between the blocks.
    - `$JointPitchMatch`: replaces `blocks-match-key`'s neighboring dots with dots m pitches apart along the key's line. The distance between the blocks is m·(k+g) with g ≥ 1, and m and the run are read together. It fits every pair, and each pair has only m = 1. Witness `blocks-skip-a-dot` has given blocks 2 and 3 that are key dots two steps apart, with a background point between them. It breaks `blocks-match-key`. Plausibility `borderline`, verdict `$JointPitchMatch`. It breaks this invariant of the inputs: in every input, the two given blocks are the drawing of neighboring key dots. The concept is undefined on it.
- `ambiguous-match`
    - `concept`: `blocks-match-key`, which means exactly one key run matches the blocks. Where more than one run matches, the reading is undefined.
    - `$EveryMatch`: adds one output grid for each matching run. It fits every pair, and each pair has one run. Witness `two-matching-runs` has given blocks 1 1 that match the key's top row and its bottom row. It breaks `blocks-match-key`. Plausibility `borderline`, verdict `$EveryMatch`. It breaks this invariant of the inputs: in every input, exactly one key run matches. In train0, the key's rows 1 and 2 are both 1 1, and the blocks show the unique row 4 4.
- `overlap-writes`
    - `concept`: `enlarge-key` and `background-dot-empty`. The blocks of non-background key points paint over whatever lies under them, and background key points write nothing.
    - `$BackgroundBlocks`: replaces `background-dot-empty`, so that a background key point paints a k×k background block. It fits every pair. Witness `drawing-covers-key` has a drawing that lands on the key. It breaks no scene claim. Plausibility `foreign`, verdict `concept`. It breaks this invariant of the inputs: the drawing and the key's bounding box are disjoint. On this witness, the block of the background point clears the key dot at (5,5).
    - `$UnderlayDrawing`: replaces `enlarge-key`'s painting, so that the drawing writes only on background cells. It fits every pair. The witness is `drawing-covers-key`, with the same plausibility, verdict and invariant. On this witness, the key dots at (1,5) and (5,1) keep their colors.
- `off-grid`
    - `concept`: a drawing that runs past the grid is clipped.
    - `$NoClip`: adds that the reading is undefined where the drawing runs past the grid. It fits every pair. Witness `drawing-off-grid` is train0's input cut to 12 rows. It breaks `fits-grid`. Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: the whole drawing lies inside the grid.
- `key-pitch` & `block-size`, `key-pitch` & `gap`, `key-pitch` & `background`, `key-pitch` & `anchor`, `key-pitch` & `drawing-turn`, `key-pitch` & `run-spacing`, `key-pitch` & `ambiguous-match`, `key-pitch` & `overlap-writes`, `key-pitch` & `off-grid`, `block-size` & `gap`, `block-size` & `background`, `block-size` & `anchor`, `block-size` & `drawing-turn`, `block-size` & `run-spacing`, `block-size` & `ambiguous-match`, `block-size` & `overlap-writes`, `block-size` & `off-grid`, `gap` & `background`, `gap` & `anchor`, `gap` & `drawing-turn`, `gap` & `run-spacing`, `gap` & `ambiguous-match`, `gap` & `overlap-writes`, `gap` & `off-grid`, `background` & `anchor`, `background` & `drawing-turn`, `background` & `run-spacing`, `background` & `ambiguous-match`, `background` & `overlap-writes`, `background` & `off-grid`, `anchor` & `drawing-turn`, `anchor` & `run-spacing`, `anchor` & `overlap-writes`, `anchor` & `off-grid`, `drawing-turn` & `run-spacing`, `drawing-turn` & `ambiguous-match`, `drawing-turn` & `overlap-writes`, `drawing-turn` & `off-grid`, `run-spacing` & `ambiguous-match`, `run-spacing` & `overlap-writes`, `run-spacing` & `off-grid`, `ambiguous-match` & `overlap-writes`, `ambiguous-match` & `off-grid`, `overlap-writes` & `off-grid`: the two branches' changes applied together
- `anchor` & `ambiguous-match`: the anchor at the key's start is one run, so only one run can match.
    - `$AnchorAtKeyStart` & `$EveryMatch`: the model of `$AnchorAtKeyStart` alone. The `ambiguous-match` point does not exist under `$AnchorAtKeyStart`. It exists under the concept branch of `anchor` and stays at the concept.

## Open parameters
- none

## Not formed
- The key found at a stored corner, in place of the single cells. That reading differs from the single-cell parse only where the given blocks are single cells (k = 1). On such an input, the given blocks and the key dots are objects of one kind, and neither reading of the pairs separates them.
- A vertical gap read apart from the horizontal one by some other means, for example from the key. No input shows two given blocks across their line. The only reading of the cross gap other than the one shared gap is a stored value, which is `$StoredCrossGap`.

## Tickets filed
- none
