# dc2e9a9d

## Departures
- `$CopyOnTop` is not formed: its open parameter `top_axis` breaks a tie no alt of the task accepts.
- New branch `$WholeBox` (choice point `Extent`, concept branch `$ObjectOnly`). It comes from the Not formed item "a copy of the whole box": Develop step 3 forms each interpretation that states one model. The witnesses `nested-copies` and `whole-box` were built for it.

## Judgments
- `nested-copies` is `borderline concept` and `@relaxed room-for-copy`. One copy lies inside the interior of another copy. A person copies the outline only, so the concept output is the verdict.
- `whole-box` is borderline concept: a lone cell inside a copy's box breaks `nubbed-boxes`, and a hollow copy leaves that cell as it is.
- `two-color-boxes` is borderline concept. It separates `shape_color=RarestColor` from `$AllCells` (two boxes in different colors break `nubbed-boxes`). Every box gets a copy.
- `shape_color=RarestColor` is a `@derive` branch (`variant derived`, `@relaxed nubbed-boxes`). `derive` reported it fits, and it built the witness for it. `background=DominantColor` is a `@derive` branch, from analyze.md.
- `$Rotate` encodes the half turn as the composition of the two axis flips (`d4_compose`). This keeps the `D4_HT` literal out of the program.
- The non-box check (`nubs`, `unboxed`) stays in the program. analyze.md says an object that is not one box outline with one nub gets no copy. `deletions` reports that it is unused on the pairs, because the pairs never have such an object.
- `deletions` hints: `color_key_choice(K)` in the first `cover` clause is redundant, because `tint` grounds K. It was left in place because `deletions` runs once, after the last edit. Each other hint is a structure that only the witnesses use: the WholeBox clauses and `keep-input`'s background test.
- The shape_color determination has `@ignore: determine prediction`. It reads the color from the inputs, at the background that the changed cells give.
- shared-read lint: `background` moved under `$KeepInput, $AllCells, $WholeBox`, the cases that read it.

## Unsettled
- No determination relation for `gap`. The plan lists it as covered by DivisorRatio. A clause that reads the gap from the pairs needs a run-length measure, which my first attempt could not ground (jump with an unbound count). A lib relation that gives the length of a clear run between two cells would settle it.
- The Not formed item "`gap` read from the nub's length" is not formed. It needs a nub parse of more than one cell, and the concept's nub test finds a single cell. A nub parse by box membership in place of link count would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
