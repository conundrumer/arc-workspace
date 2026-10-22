# ba97ae07

## Departures
none

## Judgments
- The solver has one case: the Analyze report gives a witness to `background=DominantColor` alone, and that branch is a built-in derivation, so it is the `@derive DominantColor: ordinary concept` line on `background` and has no constructor. The other branches fail Fit by the report.
- Not formed: no item gives a model, by the report's own reasons, so Develop step 3 adds no branch.
- `store` lists `band_color`, `in_band` and `open_line`, each varying by a position or color id, and prints no `@store` line to add.
- Bands are read per line: a line along an axis that holds no background cell is a band line, and a crossing cell is in band lines on both axes. Each crossing cell takes the color of its own column's or row's band that differs from its input color, which matches the Analyze report's note that the concept reads each crossing by its own row and column.
- The determination-plan asked for a determination relation for `background`, since DominantColor derives it from cell counts. The `Determine` comp keeps each train-input color at which every train input fits the scene: no cell outside the bands holds another color, each axis has one run of band lines, and some bands cross. The band parse moved into `Parse` and is shared with the program.
- Hint `head-repeat` on `parse.background` in `Determine`: kept with `@ignore`. The key carries the candidate color so that one `Parse` instance reads each candidate, and `Parse` takes the background as its own input because the program's instance keys on `Unit`.
- `deletions`: the columns `band_color.a` and `band_color.l`, the `!parse.crossing` test in `band_color`, and the `split` atom in `out` change no pair because each pair has one band per axis. They state the per-line reading and stay. The `ex_out` atom in `Determine` keeps test inputs out. The `misfit` clauses and `runs` change no determined value because 0 is the only color in every train input. They state the scene claims for variant tasks and stay.
- Keywords `lines cross occlude`: band lines are found per line, the crossing cells act, and the task reads which band is drawn on top.

## Open
none

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- `10-545_task_ba97ae07_create.md`
