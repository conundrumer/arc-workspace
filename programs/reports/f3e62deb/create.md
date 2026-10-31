# f3e62deb

## Departures
- `$PerObject` falls together by color, not by heading. The `Gravity` key is `[ch, col]`: this rests on `direction_of_color` being one-to-one in every task, so one heading is one color across Θ.
- `$Reflected` mirrors each body inside its own bounding box before the slide. `analyze.md` does not say where the mirror is taken. For one body sliding to the edge, mirroring before or after the slide gives the same grid, and the run gives `$Reflected` the output that `witnesses.json` gives it on `two-rings-one-color` and `asymmetric-object`.
- An input with no content is undefined for every case, because `moved` needs a landed cell. `analyze.md` states this for the concept only.

## Judgments
- The concept's `background` parameter keeps its concept-file name. The `@derive DominantColor` line therefore records the branch `background=DominantColor`, as `analyze.md` names it, at `variant derived` with `@relaxed one-object`. The `derive` run wrote a second witness, `bg=DominantColor`, while the parameter was still named `bg`. I removed it because it duplicates the Analyze witness `background=DominantColor`.
- `record --all` rewrote the groups. `witness`, both on the witness file and with `--file` on `witnesses.json`, and the second `audit` report no difference and no unseparated or unwitnessed case. The run has 5 witnessed cases of 12: the concept, `$PerObject`, `$PerColor`, `$Reflected` and `background=DominantColor`.
- `store` printed no line to add. Each value it found (the ring) stands at another place on each input.
- `sweep`: `background` is unique. `direction_of_color` has 15 single-row changes that give every train output: these come from `3`, which no train pair shows, and from rows for colors no input holds. The concept fixes the table as one-to-one, so the parameter is not open and the stored set stays. `determination-plan` listed no actions.
- Hint `determine prediction` on `Determine.direction_of_color`: I dismissed it with `@ignore`. `seen` reads each heading from a train pair, as the edge that the pair's output object touches, so it reads the value from the evidence and guesses nothing.
- `deletions`: 12 deletions change nothing on the pairs. Each one is an undefinedness guard (`one_color.value`, `lost`, `carried`, `moved`), the heading flip of `$Reflected` (the ring maps to itself under every flip), or a one-to-one tie guard in `Determine`, and the pairs never instantiate any of them. All stay. `deletions` ran before the last edits, and those edits changed only comments and one `@ignore` line.
- `IdentOf` (`class_id`) carries `@claim one-object`: it names the color class that is the body. `Bbox` (`box`) carries `@claim slide-to-edge`: `$Reflected` changes that rule.
- Keywords: `objects`, `move`, and `lookup` (a stored color-to-direction table gives where content is placed).

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
