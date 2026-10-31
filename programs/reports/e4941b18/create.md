# e4941b18

## Departures
- The type of the `gravity` choice point is named `Pull`, and its enumerator is `pull_choice`: the name `Gravity` is a lib component, and the lint rejects it.
- The concept branches have their own constructor names: `$BlockByColor` (`block-identity`), `$FallToEdge` (`fall-stop`), `$StoredGravity` (`gravity`). No witness of `witnesses.json` names a concept branch other than as `concept`, so no name in the witness file was rewritten.
- `background=DominantColor` is a `@derive DominantColor: ordinary concept` line on `background` and not a constructor, as Write gives for a branch that derives a parameter by a built-in derivation.
- Witness `dominant-not-stored` added (input: a field of 3 around the block, with no 7 cell). It separates `$FallUntilBlocked & background=DominantColor` from `$FallUntilBlocked`: with the stored background 7, falling until blocked finds no background cell and is undefined, and with the derived background 3 the pushed mark falls to the bottom edge. This resolves the audit's report that no run showed `background=DominantColor` defined and differing within the `$FallUntilBlocked` cases. Judged `variant` (a color permutation of the task makes 3 the background; it breaks `background` at the stored assignment), with verdict `background=DominantColor`, because the generator blanks the pusher's cell to the field color. The solver has no `@witness` line for it, as a further witness of a `@derive` branch.
- `witness --file programs/reports/e4941b18/witnesses.json` reports no difference.

## Judgments
- Of the 12 combinations of `Find`, `Stop` and `Pull`, the run gives 7 witnessed cases. All 12 fit every pair.
- The block is the bounding box of the cells that each `Find` branch takes (a `Bbox<Find>` instance). For `$BlockByColor`, this is the same as the cells of `block_color` wherever `block` holds.
- The landing for `$FallToEdge` is in the line of the cell just past the block's end, diagonal from the block's far top corner, on the grid edge toward gravity. `$LandOnBlockBase` lands beside the block's far base corner. `$FallUntilBlocked` slides from that past cell over background cells (`Slide<Choice>`, keyed per `$FallUntilBlocked` case, so that no case reads another case's gravity).
- The output is derived only where a landing cell exists inside the grid, so the model is undefined where `room-to-fall` or `marks-on-top` fails, as `analyze.md` gives.
- Case-section hints of the first run: shared clauses stood below case markers, and the shared `Slide<Unit>` read the gravity of every case. Resolved by moving the shared clauses above the markers and keying the `Slide` instance by `Choice`.
- `store` printed no line to add. `down` and `past[down]` are stored already as `gravity`, and `fall.dir` and `fall.rest` have no witness.
- `derive` listed only `background: DominantColor`, which is the `@derive` line.
- Determination: `background` is the commonest color of each input (`Mode`). `block_color` is the input color one step toward `gravity` from the pushed mark. `pusher_color` is the input color of a cell that the output turns to background. `pushed_color` is the output color of a background cell that the output changes. `gravity` keeps each edge on which every output's pushed mark lies. The first form of `block_color`, the colors whose cells the output never changes, fired the hint that it tested inputs and outputs together. The second form, the input color that is none of background and the marks, gave 3 when the plan added witness `stray-cell-beyond-block` as a pair. The third form gives `no actions`.
- `deletions` atoms kept: `perch` in `push` (marks-on-top, which makes the stored gravity undefined on `marks-beside-block`); `opposite(Down, Up)` in `past` (picks the top corner); `!params.pusher_color`, `!params.pushed_color` in `$BlockAsNonBackground` (the branch's claim); the atoms of `down` at `$GravityFromMarks` (the branch's derivation); `in(L, _)` at `$LandOnBlockBase` (`room-to-fall`); `params.background` in `fall.node` (the branch's stop test). The pairs do not exercise these atoms. Removed: `impl_choice` in `fall.dir`, which `down` already grounds, and `ex_out` in the `background` determination, which reads a value and keeps nothing that an example might contradict.
- `deletions` ran twice: the two removals above came after the first run, and the second run comes after the last edit.
- Keywords: `markers` (the pusher fixes the direction of the push), `move`, `bbox` (the landing places by the block's box).

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
