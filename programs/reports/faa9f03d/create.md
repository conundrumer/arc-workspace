# faa9f03d

## Departures
- The concept branches take names of their own: `$WireMarker` (crossing-top), `$OneCell` (break-width), `$StayFree` (free-ends). The witness file names them only as `concept`, so it needed no rename.
- `$ExtendAllEnds` puts an extended end on top of a turn arm. The probe's outputs need this order: `wide-break` shows 6 over the 7 arm at (7,10), and `short-wire-end` shows the 7 arm over 6 at (7,10), where 6's own end is at (7,10) and its extension starts at (7,11). So the extension starts one cell past the end. `analyze.md` says only "on top at crossings".
- `$AnyWidthBreaks` fills a gap wider than one cell only where neither side is a `corner_color` cell and the run goes on past both sides. One-cell gaps take the concept's test. A plain "nearest ink on both sides" fill closes the gap between test0 (3,4) and (3,7), and between the 1-runs of train3 rows 0 and 3. That fails Fit, and it does not give the `witnesses.json` output. `analyze.md` gives no test for the branch.
- A `corner_color` cell joins a wire only through a neighbor of that wire that does not run on along the perpendicular axis. In `unmarked-crossing-beside-marked-wire`, the marker at (3,4) touches the passing wire 3 at (3,5). Without this test, wire 3 counts as marked, which flips (7,5) and draws (3,4) in 3. `concept.md` does not say how a marker is assigned to its wire.

## Judgments
- `$FlipAlways`, `$KeepShown`, `$ExtensionNotOnTop`, `$EraseRunOnly`, `$TurnStrandLength`, `$KeepCornerMarkers`, `corner_color=RarestColor` and `turn_color=RarestColor` get no constructor. `analyze.md` gives each a Fit failure and no witness.
- Not formed: no item states one model that meets Fit. The color-pair lookup fails Unseen key, and the other items are contradicted by pairs. None is formed.
- `derive`: `background=DominantColor` fits. It is held as `// @derive DominantColor: foreign concept`, following `analyze.md`.
- `store`: it printed no line to add. `mid_run`, `span.stop` and `run.clear` vary by an id, and the other relations have no witness.
- Hint `common-subexpr` on `mid_run` against `passing`: kept with `@ignore`. `passing` reads the input's wire colors alone, because the markers join a wire only through it. `mid_run` reads the ink, markers included.
- Hint `pass-through` on the break relation: the break clauses now derive `base` directly. Hint `common-subexpr` on `top` against `shown_top`: the shared crossing test moved into `unlaid`.
- Determine: the plan listed `background`, `corner_color` and `turn_color` as values that a proposer gives from a fact the concept does not use. `background` is the commonest color of every train output. `corner_color` is an input color that no output keeps, at a cell that meets one wire color on two perpendicular sides. `turn_color` is the other color of that kind. The second plan run gave no actions.
- Deletions: 41 deletions change no pair. Each one removes structure that only a branch or a witness uses (`passing`, the wide-break disjunct, `stretch`, `link`, `run.blocked`), or a test that the pairs never reach (the corner test in `pivot`, the same-two-wires test for `background` crossings). All of them stay. Simplify removed `span.cell`, which `span.stop` does not read, and the `in(P, C1)` atom in each `flip` clause, which its one reader already tests.
- `witness` against `witnesses.json`: ok. `witness` and audit on the solver's own witness file: ok, with no unseparated pair and no case without a showing.
- Six cases are witnessed: the concept, `$FlipByGridMarker`, `$FlipBySegmentMarker`, `$AnyWidthBreaks`, `$ExtendAllEnds` and `background=DominantColor`. The other combinations of the three `Choice` fields are cases the runner does not witness.
- Keywords: `color-class markers repair occlude cast`.

## Unsettled
- The crossing layering. `crossing-top` reads the input cell and inverts it when either wire carries a marker. It is the reading of `analyze.md`, and the generator's depth order is not known. More examples of crossings between unmarked and marked wires would settle it.
- Where a turn marker touches two wires, `pivot` takes the wire that runs on through the cell beside the marker, as in train1 (2,9). No pair has a marker at a true two-corner contact.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
