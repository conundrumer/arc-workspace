# a934301b

## Departures
- The witness file names the derived-background branch `background=DominantColor` where the Analyze file wrote `bg=DominantColor`: the Witness file form `<param>=<Proposer>` takes the parameter's name, which the concept file gives as `background`. A run of the Analyze file with that rename gives every branch the output the Analyze file gives it. (create)
- The `@derive DominantColor` and `@derive RarestColor` lines record `variant derived` with `@relaxed rectangles`, where the Analyze report gave `borderline concept` for these branches: `derive` prints these lines, and the branch's witness is the one `derive` builds under the branch's name, train0 with 0 and 2 swapped for `background` and 8 and 2 swapped for `mark`. In a variant task with that permutation, the derived value gives the generator's output. `no-marks` and `dense-field` stay in the witness file as further witnesses of those branches, with no `@witness` line. (create)
- A third derived branch, `drop_count=TileCount`, has the line `// @derive TileCount: ordinary concept`, which the Analyze report does not list: `derive` lists it as fitting, and Develop holds each fitting derivation as a branch. Its witness `drop_count=TileCount`, the `five-marks` rectangle on a 5x6 grid with no `assign`, shows it defined where the stored table is undefined. `five-marks-square`, the same rectangle on a 6x6 grid with `keep_count` {0, 1, 5}, shows it keeping the rectangle where the concept erases it. (create)

## Judgments
- The three departures above hold under the current docs. Each rests on what it states, and no case is added or dropped by them beyond the derived branches `derive` lists.
- The `separates` texts of `five-marks`, `no-marks` and `dense-field` now state the output of every group the file lists for them. Before, they left out `drop_count=TileCount` (undefined on `five-marks`, where 5 is both a kept and a dropped count), `$CountTable & mark=RarestColor` (undefined on `no-marks`, with no entry for six), and the `$NonBody` readings under `background=DominantColor` on `dense-field`. `$NonBody & $MarkGroups` keeps the grid there, since every cell of the 0 object is a mark and they form one group. `$NonBody & $CountTable` is undefined there, with thirteen marks. The groups are unchanged, and `witness` passes.
- `keep_count`, `drop_count` and `max_marks` take no case column. They are distinct parameters across the readings of `count-marks`. Take a task where an object with three 8s in one group stays and an object with four 8s in two groups is erased: `$MarkCells` fits it with `max_marks` 3 and `$MarkGroups` fits it with 1. A chain of corner-touching objects separates `$FourAdjacent` from `$EightAdjacent` in the same way. Even so, every case stores the same values in this task, and [Params](docs/handbook/solver-file.md#params) gives a relation a case column only where its cases store different values.
- `count-marks` takes the concept file's per-component text. Every rectangle is one connected component on every input, as `analyze.md` measures, so this text is the generator's rule and it has no `@approximated:` line.
- `@scene marks` is left out of the header: no `@claim`, `@relaxed`, rule text or branch denotes it. (create)
- The Not formed item "copying the kept objects onto a blank grid" is not added as a case. Every non-object cell is a `background` cell, so on every input it gives the concept's output and it fails Equivalence. (create)
- The witness `drop_count=TileCount` is judged `ordinary concept`, as the Analyze report judged the same rectangle in `five-marks`. `five-marks-square` is judged `ordinary concept` for the same reason. (create)
- `deletions` reports that every deletion changes the result. Simplify finds no shorter form. The two `Tally` domains repeat one body, and naming it would add a relation for two uses.
- The `run_dl.py derive` and `store` reports are settled. `store` finds only `parse.cell[col]` and `parse.ink[col]`, which vary by position. (create)

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Issues filed
- none
