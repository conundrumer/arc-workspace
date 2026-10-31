# d687bc17

## Departures
- The witness file's groups were rewritten by `record --all`. Analyze's names (`concept`, `$Stack & $MoveObjects`, ...) became the fewest names over the solver's witnessed cases (`$Merge`, `$Merge & $Dots`, `$EveryWall`, `background=stored`, ...). The grids are unchanged: this is the Witness step's rewrite, and `witness --file programs/reports/d687bc17/witnesses.json` reports ok.
- `analyze.md` names three concept branches only as `concept`. The solver names them `$Merge` (landing-clash), `$Dots` (moving-unit) and `$EveryWall` (shared-wall-color), and the rewritten witness file uses those names.

## Judgments
- The solver encodes three choice points as a record `Choice = [l: Landing, m: Mover, w: WallPick]`, with all 8 combinations in `impl_choice`, and adds the `background=DominantColor` `@derive` branch. Analyze says every combination fits, and the run passes every pair. The run shows 5 witnessed cases: concept, `$Stack`, `$MoveObjects`, `$NearerWall` and `background=DominantColor`. The combined cases, such as `$Stack & $MoveObjects`, give the same output as one of their parts on every witness, so they are not witnessed.
- Branches left out as constructors: `$KeepUnmatched`, `$Blocked`, `$BlockedByUnmatched`, `background=SharedColor` and `background=RarestColor`. Analyze shows each one failing Fit and gives none of them a witness.
- The `@derive DominantColor` line has `borderline concept` and no `@relaxed`, as analyze gives that witness. `store` printed no line to add: the value `wall[d]` varies with the input.
- Movement uses lib Gravity. Under `$Merge`, each piece falls alone in its own key (`Fall`). Under `$Stack`, every piece aiming at one wall falls together (`Pile`). In both, the border cells are blocked. Under `$Merge & $Dots`, this matches `dot-to-wall` exactly: nothing else is in a dot's key, so the dot stops at the interior cell next to its wall. Gravity also gives the rigid travel `$MoveObjects` needs, so one mechanism serves every case.
- Wall colors come from the edge cells that are not corners (`box_edge` with `!corner`), not from the non-background cells of an edge. This matches the `background=DominantColor` witness that analyze judged, where a corner of color 0 must not count as a wall.
- The `$NearerWall` tie is made undefined through `live`: no `out` fact for that case on an input with a tie. This follows analyze's "undefined where two walls of its color are at equal distance".
- How the cases' pieces get their ids: `$Dots` takes each dot's id from `IdentOf<Position>`, and `$MoveObjects` takes each object's id from `Components<Color>`, keyed by color so that each object has one color. Both carry `@claim dot-to-wall`.
- Hint (case section): the first run said `$Stack & $MoveObjects` may read `dot_id`, and `$Stack & $Dots` may read `object`. The cause was that `landed($Stack)` joined `piece` on an undestructured `Pc`. Writing `[M, B]` in that join made the static check see the Mover field, and the hint cleared. It was a valid hint about how the clause was written, not a modeling issue.
- Not formed, "moved dot also stays at its own cell": this states one model, but it fails Fit at every train pair, because every train output clears each dot's cell. No combination meets Fit, so no case was added.
- Not formed, "walls found anywhere as full-length lines": I judged that this does not state one model. For a line inside the grid, it does not say which side a dot lands on. It was not formed.
- Not formed, "interior corner color": analyze states that no model can be stated, so none was formed.
- `deletions` listed 9 deletions that change nothing on the pairs. I kept all of them, each because the pairs never instantiate the structure it covers:
    - `corner`: the `background=DominantColor` witness needs it.
    - `!params.background` and `inner(P)` in `dot`: they state `scattered-dots`.
    - `live` in the first `out` clause: it ties the border cells to defined cases.
    - `tie`: `$NearerWall`'s undefinedness.
    - Determine `uneven`: the train-consistency check.
- Determine: the sweep gave `background` unique (0). The plan asked for a determination relation for `DominantColor`, and a `Mode` over each input's colors, kept where no train input disagrees, gives it.
- Keywords: `move match objects`. `objects` is for `$MoveObjects`. `match` is for dots pairing with walls by color.
- Performance: every command finished in 8 s or less, with no issue.

## Unsettled
- No witness separates the combined cases, such as `$Stack & $MoveObjects` and `$Stack & $NearerWall`, from their parts, so they stay unwitnessed: building inputs where two non-concept branches both act would settle it. Neither the Develop nor the Witness step required this.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
