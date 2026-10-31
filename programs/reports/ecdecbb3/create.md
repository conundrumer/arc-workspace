# ecdecbb3

## Departures
- The witness file has a witness that `witnesses.json` lacks, `background=DominantColor`. `derive` wrote it, and it records the `@derive DominantColor` line on `background`. That line's branch fits every pair, and `analyze.md` does not give it.
- The witness file has a second witness that `witnesses.json` lacks, `wall-dominant`. It is a 5×9 grid with walls of 8 at cols 0, 2, 4, 6, 8 and a dot of 2 at (2,3). `witness` reported that no run showed `$BeamInDotColor` with the stored `background` defined and different from `$BeamInDotColor & background=DominantColor`. This witness shows it: with the stored value the case beams from the one dot, and with the derived value every 0 cell counts as a dot.
- Under `$BeamInDotColor`, a dot is a cell of any color other than `background` and the wall color. `analyze.md` says "neither `background` nor on a wall". The `partial-wall` output that `witnesses.json` gives `$BeamInDotColor` needs this form, because a segment cell of 8 that is not on a full line must not fire a beam. The `@scene dots` line of the branch states it.

## Judgments
- Cases: six two-way choice points (`wall`, `hit`, `dot`, `edge`, `mark`, `line`) and the `@derive` lines on `mark_color` and `background` give 160 cases, and every one fits. The run keeps 12 of them as witnessed cases. Combinations whose output no single branch gives are recorded by `record --all`.
- A beam is cast only across the wall axis, read from the axis of the full lines (`across`). With a cast in all four directions, the `mark_color=RarestColor` case gives the wall cells, read as dots, beams along their own wall. `witnesses.json` says that case draws nothing there.
- A bracket takes the color of the hit cell in the input. Under the concept that color is `line_color`, and under `$LineColorFromLines` it is the color of the wall that the beam hits.
- `@derive DominantColor` on `background`: the plausibility is `variant`, because the witness is train0 with colors 0 and 1 swapped. The verdict is `concept`. The witness has `@relaxed walls`, because the `walls` scene line gives background 0.
- `wall-dominant`: the plausibility is `borderline`, because the dot is 1 cell from two walls and the walls outnumber the background. The verdict is `concept`, the beams of the one dot. The solver has no `@witness` line for it, because it is a further witness of a `@derive` branch.
- Determination: `background` is the commonest color of every input (lib `Mode`). `line_color` is the color other than the background that fills a full-length line in every input. `mark_color` is the remaining color of every input. `ring_radius` is the distance from each train hit cell to every side of the bounding box of its bracket that the grid does not clip. Without that exception, the `bracket-past-edge` witness gave a different value. `Parse<Key>` holds the full-line derivation that the program and `Determine` share.
- `deletions` lists 20 deletions that change nothing on the pairs. All of them stay. These are the `across` atoms (the `mark_color=RarestColor` witness separates them), the branch clauses `hit_exempt`, `dot_exempt` and `inside(B, ZERO)` (their witnesses separate them), and the universal "gap" clauses and hit and bracket tests of `Determine`, which state the facts the determination reads.
- Lint hints: `pass-through` on `wall`. I folded `wall` into the `$FullLine` blocker clause. `common-subexpr` in `Determine`. I factored the shared atoms into `hit_in_box`.
- `@keywords: lines cast stamp`.

## Unsettled
- The third `determination-plan` run asked for a change to `ring_radius` at `bracket-past-edge`. I changed it to skip clipped sides, and that hit the plan's run cap. The pairs run reports `determination: ok (background, line_color, mark_color, ring_radius)`. Another plan run would show whether the entry is now settled.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
