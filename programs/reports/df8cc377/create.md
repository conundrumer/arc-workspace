# df8cc377

## Departures
- The witness file holds the `background=DominantColor` witness that `run_dl.py derive` recorded, which is train0 with 0 and 1 swapped. It does not hold the 3x4 grid that `witnesses.json` gives under that id: the Witness operation removes a `@derive` branch's witness where it duplicates the one `derive` records for that branch. `run_dl.py witness --file programs/reports/df8cc377/witnesses.json` still passes on the 3x4 grid.

## Judgments
- The checkerboard parity has no lib relation, and the solver uses arithmetic for none of it. An interior cell is a checker cell when some interior cell M lies at half its taxicab distance from the interior's anchor corner. The test is a jump of M's own distance away from the anchor edge. This is the midpoint idiom of 834ec97d and d492a647, carried over to the corner distance. Rule `checker-fill` therefore has a relational form, and the solver has no `@approximated:` line.
- Frames are keyed by their outline box (`FrameKey = [f: FrameParse, b: Box]`), so one key serves both frame parses. The key carries the parse, so a `$FramePerPiece` case reads no fact that the `$ColorClassFrame` parse derives. The first draft keyed `Bbox` by the box alone, and the case-section hints fired on it.
- Under `$ColorClassFrame`, a color is a frame when `Outlines` finds a box for it and no cell of that color lies off the box's edge (`class_stray`). Under `$FramePerPiece`, the same test applies to each 4-connected one-color piece (`piece_stray`).
- `deletions` lists 18 deletions that change nothing on the pairs. Each is kept:
    - `dir_of(D, _, D_edge)` in `checker` fixes the jump direction away from the anchor edge. Without it, the jump also runs toward the anchor edge.
    - The `class_stray` and `piece_stray` rules and their negations state the `hollow-frames` claim that a frame's cells are its outline and nothing more. No pair has a frame color with a stray cell.
    - The `kept` rule, the `out` clause that reads it, and its negation are the `$KeepUnmatchedDots` branch. `frameless-dot-color` separates them, and no pair does.
    - `not_commonest` and its negation in `Determine` give the universal over the inputs. In every input, 0 is the commonest color.
- `anchor` is not an open parameter. The sweep shows that the train pairs admit `DIAG_TL` and `DIAG_TR`, and that test0 refutes `DIAG_TR`, as `analyze.md` says. Since a pair separates the two values, the solver stores `DIAG_TL` alone.
- The `determination-plan` entry for `background` is resolved by a `Determine.background` relation: the color that is the commonest in every input, through `Mode`.
- The concept file names the parameter `background`. An early draft named it `bg`, and that name broke the match with the witness names of `witnesses.json`. The parameter now has the concept file's name.
- 9 of the 48 cases are witnessed, and every witnessed case passes every pair. `witness` reports no unseparated pair of cases and no case that no run shows defined and differing.

## Unsettled
- `anchor`: a determination from the train pairs alone keeps `DIAG_TL` and `DIAG_TR`. A train pair with an even-width interior would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
