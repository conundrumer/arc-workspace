# cbebaa4b

## Departures
- The solver and the witness file are as refine-1.md left them. The coordinator's instruction was: "Encode `pieces-fit` as a pick with one row per dot, whose candidate is a partner dot together with the place of the dot's own piece, using the five `never` pairs you listed. [...] Check whether the refutation narrows each pair's input to one place per piece. If it does not, report what survives on which input and stop." The refutation does not narrow test0 or test1 to one place per piece (see Judgments). The `PlacementPruning` encoding also cannot run in a short run: its `conflict` input holds 110 million pairs on train0 and 1.9 billion on test0, from the first `never` alone. So no Souffle encoding of the pick was written, and the pass stops here.
- No case fits the task. Every case is undefined on train0, train1, test0 and test1, because `CoverForcing` forces no join on any of them (refine-1.md).
- The join cover the refine-1.md override gave is encoded: `Canon` joins, `CoverForcing` keyed by dot color, and `Propagation` over the forced joins, followed by the checks after the places (refine-1.md).
- The witness file pins the branches on inputs of two pieces with one dot each, the only inputs `CoverForcing` decides. `shared-cell` keeps the input that witnesses.json gives it, and every case is undefined on that input (refine-1.md).
- The `$OverlapAllowed` case `[ByColor, StoredConnector, OverlapAllowed, Inside]` stays, against the `witness` finding under Unsettled. So do the non-concept cases that take `$Inside` (refine-1.md).
- The determination relation of `anchor` keeps the color of a part that fills its box only where every example input holds that color (refine-1.md).
- The cases that take `$Disjoint`, other than the concept case, are not cases of the solver: each one left under Subsumption (create.md).
- `witness --file programs/reports/cbebaa4b/witnesses.json` cannot compare the groups `$AnchorSolidBlock`, `$ConnectorDerived` and `$ClipAssembly` (create.md).
- The witness file names the background branch `bg=DominantColor`, where witnesses.json names it `background=DominantColor` (create.md).
- Under `$ClipAssembly`, a piece only takes a place that puts some cell of it on the grid, or on one of the eight copies of the grid one grid extent away (create.md).

## Judgments
- The pick was checked in a Python model of `PlacementPruning`'s refutation. Each candidate is a dot's partner dot (a dot of another piece) and a place for the dot's own piece, with both pieces' places in the bounded set and the anchor's dots at no offset. The `never` pairs are the five that refine-1.md lists, with `$Disjoint` and `$Inside`:
    - two dots of one piece at different places
    - two dots that choose each other at places that do not put them on one cell
    - a dot whose partner chose another dot
    - two dots of different pieces that land on one cell and are not partners
    - two pieces that share a place other than a dot on a dot
- The model has two parts:
    - The single part refutes a candidate where some other dot has no compatible candidate.
    - The pair part refutes a candidate where two other dots have no pair of candidates that are compatible with it and with each other.
- train0: there are 25294 candidates. The single part leaves 16, one per dot, and they give each piece the fit's place.
- train1: there are 28388 candidates. The single part leaves 16, one per dot, and they give each piece the fit's place.
- test0: there are 124278 candidates. The single part leaves 21926 after 6 rounds. The anchor keeps its one place. The other pieces keep these numbers of places: `8` (small) 199, `8` (large) 421, `9` 303, `1` 215, `3` 209, `7` 340. The pair part did not reach its fixpoint within 140 s, so what it leaves on test0 is not known.
- test1: there are 93968 candidates. The single part leaves 15720. The anchor keeps its one place. The other pieces keep these numbers of places: `8` 179, `6` 364, `3` (vertical) 484, `5` 307, `1` 234, `3` (comb) 189. The pair part was not run on test1.
- The size of the `PlacementPruning` input comes from counting the pairs of the first `never` alone, two dots of one piece at different places. There are 110346214 such pairs on train0, 138556838 on train1, 1894481474 on test0 and 1159175932 on test1. The other `never` pairs add more. The component takes `conflict` as a stored relation, so it has to hold all of them.
- A full search of the join cover finds one place-consistent cover on each input, and that cover draws the pair's output. The join cover's "each piece takes one place" spans cycles of three or more joins, so it is not pairwise (refine-1.md).
- `CoverForcing` places a join only on an input with exactly two dots on two pieces (refine-1.md).
- Witness plausibilities and verdicts on the two-dot inputs are analyze.md's. `field-tie` and `touching` stay borderline concept (refine-1.md, create.md).
- `derive` prints that `bg=DominantColor` fails Fit at train 0. The `@derive` line stays, because every case fails there in the same way (refine-1.md, create.md).
- Hint `head-zero` on `place` and hint `common-subexpr` on `near` are kept with `@ignore` (create.md).
- Keyword `assemble`, proposed and on the `@keywords:` line: "pieces translate so that the join marks they carry meet, and together they form one figure" (create.md).
- The branches `$PieceByColor`, `anchor=RarestColor`, `$FacingJoin`, `$TurnPieces` and `$LooseDots` are not constructors, because analyze.md finds that each one fails Fit (create.md).
- Performance: `place` keeps flat columns (create.md).
- No file under `src/` was read.

## Unsettled
- What the pair part of the refutation leaves on test0 and test1. Running it to its fixpoint on those inputs would settle it.
- `witness` reports that no witness separates `$OverlapAllowed` from `$Disjoint`, and that no run shows `$Inside` defined and differing from `$ClipAssembly`. Two things would settle it: a ruling on whether a `CoverForcing` case's model is the Souffle `out` or the total pick that replaces it, and a pick that decides inputs with more than two dots (refine-1.md).
- The audit's relabelings check and `deletions` did not run, because the stored program fails a train pair (refine-1.md).

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
