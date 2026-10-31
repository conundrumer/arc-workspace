# cd3c21df

## Departures
- `$PairedOthers` (the `copy-count` choice point) is not in the solver: it fails Subsumption. The audit found no run where it is defined and differs from the concept. No such input exists: where it is defined, no object has two or more copies, so the one object outside every pair is the one object with no copy. `analyze.md` says the same.
- Witness `triple-copies` is removed from the witness file, and `$PairedOthers` is removed from the groups of every other witness. Once `$PairedOthers` left, `triple-copies` separated nothing: every case gives the 8 bar.
- Three witnesses were added that `witnesses.json` does not have. `two-color-odd` separates `$OwnColor` from `$Unmatched & $ColorSetCopy`. `shape-differs` shows `$CongruentCopy` defined and differing from `$ColorSetCopy`. `own-color-dot` shows `$OwnColor` defined and differing from `$Unmatched & $ColorSetCopy`. The audit asked for each of these.
- `witness --file programs/reports/cd3c21df/witnesses.json` reports only that `$PairedOthers` names no case, which comes from the Subsumption drop above. Every branch's output matches the output `witnesses.json` gives for it.

## Judgments
- The concept branches got constructor names of their own: `Unmatched` at `odd-object`, `Translate` at `match`, `Adjacency4` at `adjacency`, `FillBackground` at `box-fill`. The other constructors keep the names `analyze.md` gives them. `match` is nested as a field of `Unmatched`, because the choice point stands under the concept branch of `odd-object`.
- `$ShapeCopy` was not formed: `analyze.md` gives it no witness, and it fails Fit at train1 and train2.
- Not formed: the rank over object size or color count states no model that fits the pairs (train0 has no extremum that gives the 4-cell 2 bar). So no branch was formed from it.
- `background=DominantColor` is held as a `// @derive DominantColor: borderline concept` line on `background`, as the `derive` command printed. It is borderline because the witness breaks the invariant that 0 is the commonest color, and the verdict is concept, both as `analyze.md` gives them. `background=SharedColor`, `background=VanishedColor` and `background=RarestColor` fail Fit, and `derive` did not list them. `store` reported no findings.
- Each copy relation is a `KeyedSetCompare` over each object's cells cropped to its box. This follows the footprint comparison in approved solvers 228f6490 and 1fad071e.
    - `$Translate` compares (position, color) sets.
    - `$CongruentCopy` compares each D4 image (`apply` on the box-frame position, over every `d4_elem`) against the other object.
    - `$ColorSetCopy` compares color sets.
    - `$RecolorCopy` requires equal footprints and no clash: no two cells that one object colors alike while the other does not, checked in both directions so the renaming is a bijection.
- Every case is undefined unless it has exactly one candidate. The `rival` defect relation drops every candidate when two or more exist. Without it, two crops could overlap into one total grid by accident.
- Witnesses built:
    - `two-color-odd`: ordinary, verdict concept. It breaks no scene claim; the odd object only shares each of its colors with a repeated pair.
    - `shape-differs`: ordinary, verdict concept. It breaks no scene claim; the unique L shares its color with a pair of bars.
    - `own-color-dot`: foreign, verdict any. Two objects are unmatched, so it breaks `one-unique-object`, as `shared-color-odd` does.
- Determination: `background` is derived in `Determine` as the color that is commonest in every train input, using `Mode` over `ex_in` and ranging over examples with `ex_out` rows. The plan asked for this relation (DominantColor exact), and after it was written the plan gave "no actions". The sweep gave the unique value 0.
- Hints:
    - `case section` (Adjacency4/Adjacency8 markers): the clauses that read objects bound the adjacency only through `O = [A, _]`, so I rewrote them with `[A, I]` record patterns. The hint no longer fires.
    - `head-repeat` on `peer`: it went away when `peer` was rewritten with `O != O2` on the records.
- Deletions:
    - Applied, as redundant: the `footprint.equals` guard in `recolor_clash`, and the object's own `obj` atom in `shared_color`.
    - Inlined: `unmatched`, which had one consumer, into `candidate`.
    - Kept because the pairs never instantiate them: the reverse disjunct of `recolor_clash`, `rival` and its negation, and the background fill disjunct. The concept or the branch's meaning needs each of them.
- Keywords: `objects crop select match congruent`. `match` is in because the objects pair off as copies and the output acts on what is left unpaired. `congruent` is in for `$CongruentCopy`.
- No performance issues. The audit skipped no checks.

## Unsettled
- Whether the determination-plan line "a proposer derives from a fact other than any the concept derives it from" intends a determination relation when the concept stores the value outright: a doc or tool statement of that case would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
