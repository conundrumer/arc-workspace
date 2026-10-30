# e76a88a6

## Concept
- The concept case fits every pair: `work/task/e76a88a6/probe.py` reproduces train0, train1 and test0.
- The generator's rule is the one the concept file states: each placeholder block has the pattern's extent, and the pattern's box is carried onto the block's box. No witness has verdict `other`.
- The concept is undefined on a gray object whose extent differs from the pattern's. The `block of another shape` point holds the readings that are defined there.

## Choice points
- `placeholder color`: how the blocks are told apart from the pattern
    - `concept`: the stored `placeholder` 5; the pattern is the one object with no `placeholder` cell
    - `$MonoPlaceholder`: replaces `one-pattern` and `placeholder-blocks`: the pattern is the one object of more than one color, and every other object is a one-color block of the pattern's extent; no `placeholder` parameter; undefined where the count of multicolored objects is not one. Fits every pair. Witness `blocks-in-another-color`, at the stored assignment: it breaks `placeholder-blocks` and `one-pattern`; plausibility `variant`; verdict `$MonoPlaceholder`; it breaks the invariant that every block of every input is color 5.
    - `placeholder=SharedColor`: derives every color of the input, so every object holds a `placeholder` cell. Fails Fit at train0.
    - `placeholder=RarestColor`: derives 2 at train0. Fails Fit at train0.
    - `placeholder=DominantColor`: derives 0, the field. Fails Fit at train0.
    - `placeholder=VanishedColor`, `placeholder=ChangedColor`, `placeholder=UnchangedColor`: with `ex_out` empty, these give no value or every color of the input. Fail Fit at train0.
- `background`
    - `concept`: the stored `background` 0
    - `background=DominantColor`: replaces the stored value with the commonest color of the input. Fits every pair. Witness `background=DominantColor`, at the stored assignment: it breaks no scene claim; plausibility `borderline`; verdict `concept`; it breaks the invariant that the field is the commonest color of every input, with 52 or more of the 100 cells.
    - `background=SharedColor`, `background=RarestColor`: derive several colors, or 2, at train0. Fail Fit at train0.
- `adjacency`: the steps that join an object's cells
    - `concept`: 4-adjacency
    - `$Adjacency8`: replaces 4-adjacency in `one-pattern` with 8-adjacency; undefined where a placeholder object meets the pattern at a corner. Fits every pair. Witness `split-block`, at the stored assignment: it breaks `placeholder-blocks`; plausibility `foreign`; verdict `$Adjacency8`; it breaks the invariant that every gray object is a solid rectangle with a field cell between it and every other object, at the sides and the corners.
- `block of another shape`: a gray object whose cells are not a copy of the pattern's box
    - `concept`: undefined where the object's extent differs from the pattern's; a non-solid object of the pattern's extent takes the pattern's cells at its own cells
    - `$SkipMismatched`: replaces `placeholder-blocks` with blocks of any extent, and adds to `stamp-pattern` that a block whose extent differs from the pattern's keeps its color. Fits every pair. Witness `smaller-block`, at the stored assignment: it breaks `placeholder-blocks`; plausibility `foreign`; verdict `$SkipMismatched`; it breaks the invariant that every gray block has the pattern's extent.
    - `$ScaleToBlock`: replaces `placeholder-blocks` with blocks whose extent is a whole multiple of the pattern's on each axis, and adds to `stamp-pattern` that such a block takes the pattern scaled by those multiples; undefined on another extent. Fits every pair. Witness `larger-block`, at the stored assignment: it breaks `placeholder-blocks`; plausibility `foreign`; verdict `$ScaleToBlock`; it breaks the same invariant.
    - `$TileRegion`: as `$ScaleToBlock`, with the pattern repeated across the block in place of scaled. Fits every pair. Witness `larger-block`, as above.
    - `$ClipAtCorner`: replaces `placeholder-blocks` with blocks of any extent, and replaces `stamp-pattern`: each block cell takes the pattern cell at the same offset from the `anchor` corner of the two boxes, where one exists, and keeps its color otherwise. The case runs every `anchor` value TL, TR, BL and BR, and is undefined on an input where those values give different outputs. Fits every pair. Witness `smaller-block`, as above: the case is undefined there, since the four corners give different outputs.
    - `$TurnToBlock`: replaces `placeholder-blocks` with blocks of the pattern's extent or its transposed extent, and adds to `stamp-pattern` that a transposed block takes the pattern under the `turn` element; undefined on another extent. The case runs every `turn` value CW, CC, DG and AD, and is undefined on an input where those values give different outputs. Fits every pair. Witness `transposed-block`, at the stored assignment: the case is undefined there, since the four elements give different outputs; it breaks `placeholder-blocks`; plausibility `foreign`; verdict `$TurnToBlock`; it breaks the same invariant.
    - `$MatchFootprint`: adds to `placeholder-blocks` that the object's cells are the pattern's cells moved; undefined on any other gray object. Fits every pair, and fails Subsumption: wherever it is defined, the concept case is defined and gives the same output. It has no witness, for that reason.
- `placeholder color` & `background`, `placeholder color` & `adjacency`, `placeholder color` & `block of another shape`, `background` & `adjacency`, `background` & `block of another shape`, `adjacency` & `block of another shape`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- the pattern is erased after it is copied, as in 321b1fc6: every train output keeps the pattern in place.
- a choice among several patterns, by size or by color count: every input holds one multicolored object, and no claim of the concept or of a branch reads a count of patterns other than one.
- a gray object made of the placeholder color and other colors: the generator gives no source for one, and every branch is undefined on it.

## Tickets filed
none
