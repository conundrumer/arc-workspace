# f560132c

## Concept
- Fits every pair, train0, train1 and test0, each with one output (`work/task/f560132c/probe.py task concept`): the four pieces tile exactly one square with the key piece unturned, and coloring by corner reproduces each output.
- No witness of the concept case has verdict `other`. The rule is as the generator applies it: the generator cuts a square into four interlocking pieces, one per corner, and scatters the three that hold no key, turned. `assemble` searches every exact cover of the square, so it gives every tiling where the generator has one. The concept has no approximation.
- After step 2 the concept file was corrected and no claim changed. `turns` was dropped as a parameter, since the program enumerates every value of C4 (Every value). `background` moved to Parameters, since the program reads it to find the pieces. The key's corner within its piece, which the first draft fixed at upper-left, is now the scene parameter `key_corner`. `four-pieces` now states the distinct colors and the corner gap that the witnesses below break.

## Choice points
- `frame-shape`
    - `concept`: the pieces tile a square.
    - `$RectangleFrame`: replaces `pieces-tile-square` and `assemble`: the pieces tile any solid rectangle, one piece per corner, and the output is that rectangle. No new parameter, and it is undefined only where the concept is too, apart from where the pieces tile a non-square rectangle. It fits every pair, since a 9×16 frame in test0 has no tiling. Witness `rectangle-frame`: breaks `pieces-tile-square`. Plausibility `variant`: it breaks the invariant that the pieces' total area is a square and that they tile a square. Verdict `$RectangleFrame`.
- `piece-transforms`
    - `concept`: each non-key piece takes a rotation of C4.
    - `$ReflectPieces`: replaces `assemble`: each non-key piece takes any element of D4, another orientation type. It fails Fit at train0, where the reflected 3 piece gives a second tiling and two outputs.
    - `$TranslatePieces`: replaces `assemble`: pieces only translate. It fails Fit at train0, where the 3×4 block of 7 must stand 4×3.
- `key-piece-turn`
    - `concept`: the key piece stays unturned.
    - `$TurnKeyPiece`: replaces `assemble`: the key piece also takes a rotation of C4, and the key is read in the grid's frame. It fails Fit at train0, where the four turns of the whole assembly give four outputs.
        - `key-frame`
            - `concept`: the key is read in the grid's frame.
            - `$KeyTurnsWithPiece`: replaces `color-by-corner`: the key is read after turning with its piece. It fails Fit at train0, where it gives the four turns of the output.
- `key-piece-corner`
    - `concept`: the tiling decides which corner the key piece covers.
    - `$KeyCornerPlacement`: adds to `assemble`: the key piece covers the stored corner `key_corner` (DIAG_TL), which moves from Scene parameters to Parameters. It is undefined where no tiling puts the key piece there. It fits every pair. Witness `turned-key-piece` (train0 with the key piece and its key turned a quarter clockwise): breaks `key-piece`, since the key sits nearest the top-right of its piece at `key_corner` = DIAG_TL. It stands at the stored assignment: at DIAG_TR the branch is defined and agrees with the concept. Plausibility `variant`: the input is train0 turned, apart from pieces that turn anyway, and it breaks the invariant that the key sits at its piece's upper-left. Verdict `concept`.
        - `key_corner source`
            - `concept`: `key_corner` stored.
            - `$KeyCornerFromKey`: replaces the stored `key_corner` with a derivation by solver clauses: the corner of the key piece's box that the key is nearest, by comparing the key's distances to opposite edges. It is undefined where those distances tie on an axis. It fits every pair. Witness `moved-key` (train0 with the key moved to rows 3–4, cols 1–2 of the key piece): breaks `key-piece`. Plausibility `variant`: it breaks the invariant that the key sits one cell in from its piece's upper-left. Verdict `concept`.
- `piece-color`
    - `concept`: each piece takes the key's color at the corner of the square it covers.
    - `$KeyCornerMap`: replaces `color-by-corner`: a stored relation `key_map` from key corner to square corner, the identity here. It fits every pair. Witness `key-map` (train0's input): at the stored identity the branch agrees with the concept on every input, so the witness stands at `key_map` swapping DIAG_TR and DIAG_BL, the one parameter changed. It breaks no scene claim. Plausibility `ordinary`. Verdict `concept`.
    - `$ColorBySizeRank`: replaces `color-by-corner`: the key piece takes the top-left color, and each other piece takes a corner from a stored map keyed by its size rank among the three (largest BR, middle TR, smallest BL). It fails Fit at test0, where the largest piece, of 5, covers TR.
    - `$ColorByScenePlace`: replaces `color-by-corner`: a piece takes the key color of the scene quadrant it lies in. It fails Fit at train0, where the 4 piece lies bottom-left and fills BR with 9.
    - `$KeepKeyCells`: replaces `color-by-corner`: key cells keep their own colors. It fails Fit at train0: output (1,2) is 1, not 5.
- `piece-parse`
    - `concept`: pieces are the 4-connected components of non-`background` cells.
    - `$Pieces8`: replaces the parse in `four-pieces` with 8-connected components. It is undefined where a corner contact leaves three pieces. It fits every pair. Witness `diagonal-touch` (train0 with the 7 block at rows 2–4, cols 6–9, touching the key piece at (1,5)/(2,6)): breaks `four-pieces`. Plausibility `borderline`: it breaks the invariant that pieces stand several cells apart. Verdict `concept`.
    - `$PiecesByColor`: replaces the parse in `four-pieces`: a piece is a color class, with the key cells it holds. It is undefined where two pieces share a color. It fits every pair. Witness `shared-piece-color` (train0 with the 7 block recolored 3): breaks `four-pieces`. Plausibility `variant`: it breaks the invariant that the eight colors are distinct. Verdict `concept`.
- `background`
    - `concept`: `background` stored, 0.
    - `background=DominantColor`: replaces the stored `background` with each input's commonest color. It fits every pair. Witness `background=DominantColor` (id `crowded-scene` in the witness file): a 20×20 puzzle, train0's assembly with row 6 and column 6 repeated 8 times and its pieces pushed apart, with 162 cells of 4 against 144 of 0. It breaks no scene claim. Plausibility `borderline`: it breaks the invariant that 0 outnumbers every other color several times over. Verdict `concept`.
    - `background=SharedColor`, `background=RarestColor`: each fails Fit at train0. On one input these derivations give every color of the input, or the four key colors, and at any non-0 value the pieces are not four.
    - `background=OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`: each fails Fit at train0. Each reads train outputs, which are empty under `@derive`, so they give no value and are undefined on every input.
- `frame-shape` & `piece-transforms`, `frame-shape` & `key-piece-turn`, `frame-shape` & `key-piece-corner`, `frame-shape` & `piece-color`, `frame-shape` & `piece-parse`, `frame-shape` & `background`, `piece-transforms` & `key-piece-turn`, `piece-transforms` & `key-piece-corner`, `piece-transforms` & `piece-color`, `piece-transforms` & `piece-parse`, `piece-transforms` & `background`, `key-piece-turn` & `key-piece-corner`, `key-piece-turn` & `piece-color`, `key-piece-turn` & `piece-parse`, `key-piece-turn` & `background`, `key-piece-corner` & `piece-color`, `key-piece-corner` & `piece-parse`, `key-piece-corner` & `background`, `piece-color` & `piece-parse`, `piece-color` & `background`, `piece-parse` & `background`: the two branches' changes applied together.
    - Of these, the following combinations meet Fit at every pair, and the witness file groups them:
        - `$TurnKeyPiece & $KeyCornerPlacement`: the key piece is turned so that it covers the stored corner.
        - `$TurnKeyPiece & $KeyTurnsWithPiece & $KeyCornerPlacement`: the same, with the key read in the piece's turned frame.
    - On `turned-key-piece` the two combinations give train0's square colored 8, 1, 9, 5 from TL to BR, and train0's own output. The concept gives train0's output turned a quarter clockwise. Verdict `concept`.
    - `$TurnKeyPiece & $KeyCornerFromKey`, with or without `$KeyTurnsWithPiece`: the key's nearest corner turns with the piece, so all four turns of the assembly meet it. It fails Fit at train0 with four outputs.
    - `$ReflectPieces` with `$KeyCornerPlacement` still fails Fit at train0, with two outputs.

## Open parameters
- none

## Not formed
- A piece count other than four: the key's four corners give one piece per corner, and a different count has no corner map.
- A tiebreak among several tilings: every pair has exactly one tiling, so no pair shows a tie, and the concept gives each tiling's output where there are several.
- Pieces covering no corner or two: `color-by-corner` has no color for such a piece, so no model gives an output there to set against the concept.

## Tickets filed
- none
