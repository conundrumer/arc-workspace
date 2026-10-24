# f8cc533f

## Concept
- The concept fits every pair, train and test (`work/task/f8cc533f/check_concept.py`). Each non-background color is one copy. The pattern box takes the largest copy extents on each axis. Each copy is placed at the spot in that box that gives the smallest overlay, and in every pair that spot is unique. The overlay is the pattern, and each copy's color fills it at that copy's placement. No copy is complete in any pair, so only the overlay recovers the pattern. The train2 8 copy has lost its whole right column (its box is 5×4), and placing it by containment handles that.
- Rule as the generator applies it: draw one pattern, stamp it once per color, erase some cells of each stamp but never a cell from every stamp, and pair the input with every stamp made whole. On every input that keeps `pattern-is-union`, the overlay rule gives the same output. No witness has verdict `other`.
- Every pair's pattern is D4-symmetric. This is an invariant of the inputs. The concept does not claim it, and `$SymmetricClosure` reads it.

## Choice points
- `copy-repair`
    - `concept`: every copy is repaired from one pattern that all the copies share
        - `pattern-source`
            - `concept`: the overlay of the aligned copies; a cell is in the pattern when some copy holds it
            - `$CopyCountThreshold`: replaces `pattern-is-union`: a cell is in the pattern when at least `min_copies` aligned copies hold it. Parameter `min_copies` (number), stored 1, because train1 has 7 pattern cells that only one of its two copies holds. Defined on every input. Fits every pair. Witness `cell-in-one-copy` (train1 input) stands at `min_copies` = 2. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
            - `$MajorityVote`: replaces `pattern-is-union`: a cell is in the pattern when more than half of the copies hold it. No parameters. Defined on every input. Fails Fit at train0, where 2 pattern cells sit in only 2 of the 4 copies.
            - `$LargestCopy`: replaces `pattern-is-union`: the copy with the most cells is the pattern, and it stamps at every copy's placement. No parameters. A tie for the most cells gives one output per tied copy. Fails Fit at train0, because no copy in any pair is complete.
            - `$SymmetricClosure`: replaces `pattern-is-union`: the pattern is the overlay closed under the symmetry group `pattern_sym` about the center of the pattern box. Parameter `pattern_sym` (Sym), open values `SYM_D4` and `SYM_BOX`. Undefined where the pattern box is not square. Fits every pair, since each pair's overlay is already closed under D4. Witness `asymmetric-pattern`: it breaks no scene claim, plausibility `variant`, verdict `concept`. It breaks the invariant that every input's pattern is closed under D4.
            - `$StoredPattern`: replaces `pattern-is-union`: the pattern is a stored grid parameter, and each copy is placed where it lies inside that grid. Fails Fit at train1, whose pattern is not train0's.
        - `copy-alignment`
            - `concept`: each copy sits where its cells lie inside the pattern box, at the placement that gives the smallest overlay
            - `$CornerAlign`: replaces the placement in `pattern-is-union`: each copy's bounding box shares the corner `align_corner` with its pattern box. Parameter `align_corner` (DiagDir), open values `DIAG_TL` and `DIAG_BL`. Train2's 8 copy rules out `DIAG_TR` and `DIAG_BR`. Defined on every input. Fits every pair. Witness `copy-missing-left-column` (train0 with the 2 copy's left column erased): it breaks no scene claim, since train2 already shows a copy that lacks a whole edge column. Plausibility `ordinary`, verdict `concept`.
    - `$SelfSymmetry`: replaces `copies-of-one-pattern`, `pattern-is-union` and `restore-copy`: each copy is a D4-symmetric figure with cells missing. It is repaired by closing it under D4 about its own bounding-box center. No parameters. Defined on every input. Fails Fit at train2, because the 8 copy has lost its right column and its box center is off by half a column. It also fails both tests.
- `copy-grouping`
    - `concept`: the cells of one non-background color form one copy (`one-color-per-copy`)
    - `$ComponentCopies`: replaces `one-color-per-copy`: each 8-connected component of non-background cells is a copy. No parameters. Fails Fit at train2, where the pattern itself is four separate 2×2-bounded blocks and the input splits into 11 components.
- `background`
    - `concept`: the commonest color, derived from the input
    - `$StoredBackground`: replaces the derivation in `background` with a stored color. Fails Fit at train1, whose background (2) is not train0's (3).
- `copy-repair` & `copy-grouping`, `copy-repair` & `background`, `copy-grouping` & `background`, `pattern-source` & `copy-alignment`, `pattern-source` & `copy-grouping`, `pattern-source` & `background`, `copy-alignment` & `copy-grouping`, `copy-alignment` & `background`: the two branches' changes applied together

## Open parameters
- `align_corner`: `DIAG_TL`, `DIAG_BL`, under `$CornerAlign`
- `pattern_sym`: `SYM_D4`, `SYM_BOX`, under `$SymmetricClosure`

## Not formed
- Copies as 4-connected components: this is `$ComponentCopies`' parse under another adjacency. Train2 splits into more components under it, and it fails Fit at train2 for the same reason.
- A copy holding a cell outside the pattern (noise to remove): no input has one, and no output removes a non-background cell, so no pair or probe proposes it.
- A pattern cell erased from every copy: it breaks `pattern-is-union`. The concept leaves the cell blank, and the generator's own output holds it. The branch `$SymmetricClosure` recovers it wherever a symmetric counterpart shows, and that branch is formed and judged above.

## Tickets filed
- none
