# cb227835

## Departures
- `$NonBackground` is undefined only where a third marker stands, and returns the input where fewer than two cells are off `background`. `analyze.md` gives it as undefined wherever the count is not two: the branch changes only which cells are markers, so it takes the concept case's rule for a missing marker. No witness input has fewer than two non-background cells, so no recorded output differs.
- In `programs/reports/cb227835/witnesses.json`, the name `background=DominantColor` stands for the nested branch, `$NonBackground & background=DominantColor`. The runner reads the bare name as the concept base with a derived `background`, and that is no case, so `witness --file` printed "denotes a model that is no case of the solver" under each of the three witnesses. In the solver, the case `$NonBackground & background=DominantColor` gives the grid that each group of `witnesses.json` lists for that name.
- The witness file holds two witnesses that `witnesses.json` does not give: `stray-cells` and `one-row`. They resolve the case pairs that `witness` reported as unseparated (see Judgments).

## Judgments
- The corner of the outline is the cell that a straight ray from one marker and a diagonal ray from the other marker both reach, no farther along the straight ray's direction than the other marker. On the two markers' lines there are four such ray crossings. This test keeps only the one inside the box that the markers bound. Where the markers share a row, a column or a diagonal, the corner is a marker, and the outline is the one line the concept draws there.
- The distance test is `dist(C, D1, K_c), dist(B, D1, K_b), K_c >= K_b`, a bound comparison. The principled form `!nearer(D1, C, B)` aborts the run (ticket filed). The two forms state the same relation, so I did not mark the comparison as a `@workaround`.
- A case is undefined where three distinct markers stand (`crowded`). This follows the Analyze probe's concept, which gives no output for more than two markers, and the Not formed item that no source says which markers join. In Simplify, I replaced a `Unanimous` partner instance and its `Mark` key record with the direct three-marker test. That leaves one clause in place of a comp, a type and a clause.
- `deletions` reported three removals that change no pair: the `crowded` rule, `!crowded(Ch)` in `out`, and the marker atom in `corner` (now `marker(Ch, A), marker(Ch, B), A != B`). The pairs never hold a third marker. The witnesses `stray-cells` and `background=DominantColor` need `crowded`. The marker pair in `corner` states that the corner joins two distinct markers, so I kept all three.
- `derive` gave `marker_color=RarestColor` and `background=DominantColor`. Each is a `@derive` line with the plausibility and verdict of its `analyze.md` witness: `variant derived` and `variant concept`, each `@relaxed two-markers`. `store` gave no relation to add. No branch of `path-color-source` fits, so no `@derive` line or `@ignore: derive` line stands on `path_color`.
- `determination-plan` gave each parameter as covered by a proposer, `exact`: `marker_color` by RarestColor, `background` by DominantColor and `path_color` by AnyOutNewColor. Each proposer reads the same fact that the concept reads: the markers are the few cells on the field, the field is the commonest color, and the outline color is the color that is new in the outputs. So the solver has no `Determine` comp. `sweep` gave one value for each parameter.
- Witness `stray-cells` is train0's input with three 5 cells in the bottom-right corner. Verdict `concept`, plausibility `borderline`, because it breaks `two-markers` ("no other cell"). The concept case and the rarest-color case draw the outline and keep the 5 cells. Both non-background cases see five markers and are undefined.
- Witness `one-row` is the 1×4 grid `8 0 0 8`. Verdict `concept` (`8 3 3 8`), plausibility `foreign`, because it breaks `markers-off-lines` and no generator grid is this small. It is the only kind of input on which `$NonBackground` at the stored `background` is defined and differs from `$NonBackground & background=DominantColor`: on a grid of five or more cells, with exactly two cells off 0, 0 is the single dominant color. It also separates `$NonBackground & background=DominantColor` (input returned) from `$Colored & marker_color=RarestColor` (undefined, because 0 and 8 tie as rarest).
- Keywords `markers cast span`: the markers fix the outline's ends, the runs are rays cast from the markers, and the corner bounds each run.
- The relation for `background` keeps the name that `analyze.md` uses, in place of the corpus's frequent `bg`, so the witness names match.
- No hint appeared. Lint passed. The audit reported nothing open after the two witnesses, and it skipped no check. No step had a performance problem.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 17-38_task_cb227835_create.md
