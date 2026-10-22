# a934301b

## Departures
- The witness file names the derived-background branch `background=DominantColor` where the Analyze file wrote `bg=DominantColor`: the Witness file form `<param>=<Proposer>` takes the parameter's name, which the concept file gives as `background`. With that rename, every Analyze witness gives the branch outputs the Analyze file gives. `touching-rectangles` stays `other` as judged.
- The `@derive DominantColor` and `@derive RarestColor` lines record `variant derived` with `@relaxed rectangles`, where the Analyze report gave `borderline concept` for these branches. The rule for `@derive` lines makes the branch's witness the one `derive` builds, under the branch's name. That witness is train0 with a color swapped: 0 and 2 for `background`, 8 and 2 for `mark`. In a variant task with that permutation, the derived value gives the generator's output. The Analyze witnesses `no-marks` and `dense-field` stay in the witness file as further witnesses of those branches, with no `@witness` line. Neither duplicates the derive-built witness, because they show where the derivation errs in this task.
- A third derived branch, `drop_count=TileCount`, has the line `// @derive TileCount: ordinary concept`. The Analyze report does not list it. `derive` lists it as fitting: the tile counts 2–8 that fit the grid sides include 2, 3 and 4 on every pair. It is neither equivalent to nor subsumed by the stored table. Its witness `drop_count=TileCount` is the `five-marks` input with no `assign`. On that 5x6 grid, 5 is a tile count, so the branch erases the rectangle and the stored `$CountTable` is undefined. The added witness `five-marks-square` is the same rectangle on a 6x6 grid with `keep_count` {0, 1, 5}. On it, the branch keeps the rectangle while the concept erases it. The audit asked for that run.

## Judgments
- `count-marks` takes the restated per-rectangle text, with the concept file's per-component text as its `@approximated:` line: the Analyze report's Not formed gives per-rectangle erasure no relational form. `touching-rectangles` (borderline other, `@relaxed rectangles`) stands under that line. Every case gives an output other than the verdict's on it.
- `@scene marks` is left out of the header: no `@claim`, `@relaxed`, rule text or branch denotes it.
- `keep_count` and `drop_count` are one parameter each, with no case column. The four `$CountTable` readings give the same counts on every pair. Under `$MarkGroups`, train1's object at rows 10–13, cols 10–13 counts 3 instead of 4, and train2 still supplies 4. Determine's `keep_count` takes the counts of train objects that the output leaves unchanged, across every reading. The plan covers `drop_count`, `max_marks`, `mark`, `background` and `body` without a determination relation.
- The Not formed item "copying the kept objects onto a blank grid" is not added as a case. Every non-object cell is a `background` cell, so on every input it gives the concept's output and it fails Equivalence.
- The witness `drop_count=TileCount` is judged `ordinary concept`, as the Analyze report judged the same rectangle in `five-marks`. `five-marks-square` is judged `ordinary concept` for the same reason.
- `deletions` flagged `ink(K, P, _)` in `groups.node` as changing nothing. It is redundant: a group counts only through its cells that lie in an object. The atom was removed.
- The `run_dl.py derive` and `store` reports are settled. `store` found only `ink[col]`, which varies by position.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Issues filed
- 1791212478-a934301b-create-1.md
