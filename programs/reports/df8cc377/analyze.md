# df8cc377

## Concept
- Fits every pair, and every rule has a relational form: each count is a count of cells the input has.
- No witness has the verdict `other`.
- The train pairs alone fit `anchor` at `DIAG_TL` and at `DIAG_TR`, because every train interior has an odd width. In test0, the 2x2 interior of the 2 frame separates the two: at `DIAG_TR` the 8 cells land on (11,4), (12,3), and the output has them on (11,3), (12,4). So the solver stores `DIAG_TL`.

## Choice points
- `color-match`: how a frame picks its dot color
    - `concept`: the dot color whose dot count equals the frame's checkerboard cell count
    - `$MatchByRank`: replaces `checker-fill`'s match. The frames are ranked by checkerboard cell count and the dot colors by dot count, both dense and ascending, and the frame of rank k takes the dot color of rank k. It is undefined where two dot colors of one rank meet a frame of that rank. Fits every pair. Witness `counts-off-by-one`: breaks `counts-match`, at the stored assignment, plausibility `foreign`, verdict `$MatchByRank`. It breaks the invariant that each frame's checkerboard cell count is the dot count of one dot color.
        - `rank-key`: what ranks the frames
            - `concept`: the checkerboard cell count
            - `$RankByArea`: the interior area. Fits every pair. Witness `tied-checker-counts`: breaks `counts-match`, at the stored assignment, plausibility `foreign`, verdict `$RankByArea`. It breaks the invariant that no two frames have the same checkerboard cell count.
- `dot-count`: what a dot color's count counts
    - `concept`: its cells
    - `$CountPieces`: replaces the count in `checker-fill` with the number of 4-connected pieces of that color. Fits every pair. Witness `touching-dots`: breaks `scattered-dots`, at the stored assignment, plausibility `variant`, verdict `concept`. It breaks the invariant that no two dots touch, even at a corner.
- `frame-parse`: what a frame is
    - `concept`: a color whose cells together form one rectangle outline
    - `$FramePerPiece`: replaces `hollow-frames`. A frame is a 4-connected one-color piece that forms a rectangle outline, and a dot is every other non-`background` cell. Fits every pair. Witness `shared-frame-color`: breaks `hollow-frames`, at the stored assignment, plausibility `variant`, verdict `$FramePerPiece`. It breaks the invariant that each frame's color is a color no other frame has.
        - `piece-colors`: which cells a piece joins
            - `concept`: cells of one color
            - `$MixedColorPieces`: all non-`background` cells, and a frame is a piece of one color that forms a rectangle outline. Fails Fit at test0: the 5 dot at (1,12) touches the 1 frame at (1,11), so that piece is no outline and the 1 frame stays empty.
- `unmatched-dots`: what happens to the dots of a color that no frame takes
    - `concept`: they become `background`, like every dot (`erase-dots`)
    - `$KeepUnmatchedDots`: replaces `erase-dots`. Only the dots of a color that a frame takes become `background`, and the others keep their color. Fits every pair. Witness `frameless-dot-color`: breaks `scattered-dots`, at the stored assignment, plausibility `variant`, verdict `concept`. It breaks the invariant that the dot colors are as many as the frames.
- `background`
    - `concept`: stored 0
    - `background=DominantColor`: the commonest color of the input. It is undefined where two colors tie for the commonest. Fits every pair. Witness `background=DominantColor`: breaks no scene claim, at the stored assignment, plausibility `borderline`, verdict `concept`. It breaks the invariant that 0 is the commonest color of every input.
    - `background=SharedColor`: every color of the input, on one input alone. Fails Fit at train0, where it gives 0, 3, 4, 6 and 8.
    - `background=RarestColor`: the rarest color of the input. Fails Fit at train0, where it gives 3.
- `color-match` & `dot-count`, `color-match` & `frame-parse`, `color-match` & `unmatched-dots`, `color-match` & `background`, `dot-count` & `frame-parse`, `dot-count` & `unmatched-dots`, `dot-count` & `background`, `frame-parse` & `unmatched-dots`, `frame-parse` & `background`, `unmatched-dots` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `anchor` at `DIAG_TR`, `DIAG_BL` or `DIAG_BR`: these are values of the stored orientation parameter `anchor`, not branches. `DIAG_BL` and `DIAG_BR` fail train0 and train1 (2-row interiors), and `DIAG_TR` fails test0.
- `$MatchByRank` with one order reversed, so the rarest dot color goes to the largest frame: fails train0, where it would put 3 in the 4 frame.
- Frames matched to dots by place, such as the nearest dots or the dots in one region: fails train0, where the 3 dots and the 6 dots are both spread over the whole grid.
- `background` from a proposer that reads `ex_out` (`OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`): with `ex_out` empty, it gives no value on an input, so the branch is undefined on every pair.
- Dots kept in the output: every pair erases every dot.

## Tickets filed
- none
