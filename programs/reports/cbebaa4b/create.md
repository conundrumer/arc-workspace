# cbebaa4b

## Departures
- No case fits the task: every case is undefined on test0 and test1, where analyze.md finds that the concept and the branches with witnesses fit every pair. The program cannot state `pieces-fit` (see Concept faults), so it runs an approximation of `assemble`, and the approximation decides neither test.
- The cases that take `$Disjoint`, apart from the concept case, are no cases of the solver: each one left under Subsumption. Under the approximation, `$OverlapAllowed` differs from `$Disjoint` only by one check that it drops, so wherever a case that takes `$Disjoint` gives a grid, the case that takes `$OverlapAllowed` in its place gives the same grid. The derived background's concept-base case left in the same way (`@ignore: derive $Disjoint`).
- `witness --file programs/reports/cbebaa4b/witnesses.json` cannot compare the groups `$AnchorSolidBlock`, `$ConnectorDerived` and `$ClipAssembly`: the model of each of these branches alone takes `$Disjoint`, so it is no case of the solver (see the departure above). On each witness, the case that takes the branch together with `$OverlapAllowed` gives the grid that witnesses.json gives the branch.
- The witness file names the background branch `bg=DominantColor`, where witnesses.json names it `background=DominantColor`: [Witness file](docs/handbook/solver-file.md#witness-file) builds that name from the parameter's name, which is `bg`.
- Under `$ClipAssembly`, a piece takes only a place that puts some cell of it on the grid or on one of the eight copies of the grid that lie one grid extent away. analyze.md's model has no bound. The places the joins lead to must be a finite set given before the propagation runs, and the bound of one grid extent counts something the task has.
- The determination relation of `anchor` reads the color of the part that fills its bounding box, where `determination-plan` proposed `UnchangedColor`: a relation that kept the color whose cells no output changes drew the `determine prediction` hint, because it reads inputs and outputs together.
- The judged output of `tied-join` is test0's output from the task file, and not the output of `grid` on a control grid: the approximation's joins depend only on the shapes of the pieces, so no change of the places of the pieces makes the program give it, and test0's output used as an input also gives no grid.

## Judgments
- The approximation of `assemble`: two pieces join at the one offset at which the most of their dots meet with no other cells sharing a place, where one offset does. Each piece takes the place that these joins lead it to from the anchor piece. The output stands only where that assembly is a fit: each piece takes one place, each dot meets exactly one dot of another piece, and (`$Disjoint`) no other cells share a place. Where the scene claim `pieces-fit` holds, an output is therefore the fit; where the joins lead nowhere or to two places, every case is undefined, and the approximation gives no wrong grid. On the train pairs every join with one most-meeting offset is a true join; on test0 the 9 piece meets the large 8 piece at two dots at two offsets, and on test1 the 4 piece meets the large 3 piece at two dots at an offset that the fit does not use.
- Why `assemble` has no relational form: the translation it reads is the one joint assignment of offsets to all pieces that meets `pieces-fit`, and finding it needs a search over joint assignments, which no set of clauses in the program states (see Concept faults). An approximation that refutes placements by local consistency was tried in a scratch model: refuting a placement when one of its dots has no live placement of another piece to meet it, and when it clashes with the one live placement of a piece, decides train0 and train1, and still leaves hundreds of placements per piece on test0 and test1. Clauses for it would also need a walk in an order over placements that the task does not have.
- Witness `tied-join`: ordinary, other. It is test0's input, which breaks no scene claim.
- Witness `field-tie` (separates `bg=stored` from `bg=DominantColor`): borderline, concept. The 4 block covers as many cells as the field, which the generator gives only under unusual conditions.
- Witness `off-edge` (separates `$Inside` from `$ClipAssembly`): ordinary, concept. It breaks no scene claim. Under analyze.md's `$ClipAssembly` model the fit is the same, so the difference comes from the approximation's joins, which under `$ClipAssembly` lead the 3 piece to a second place past the top edge.
- Witness `touching` (separates `$StoredConnector` from `$ConnectorDerived`): borderline, concept. The 1 piece touches the anchor and the two dots touch each other.
- Hint `head-zero` on `place`: kept with `@ignore`. The zero offset is the anchor's place, which is no move.
- Hint `common-subexpr` on `near`: kept with `@ignore`. The second jump starts from the cells of the first, and a shared relation would need recursion.
- Keyword: `assemble` is proposed and added: "pieces translate so that the join marks they carry meet, and together they form one figure". `move` and `markers` each give part of it, and no listed keyword gives the matching of marks between pieces.
- The `@derive DominantColor` line stays although `derive` prints that `bg=DominantColor` fails Fit at test 0: the concept case fails there in the same way, and the constructors' cases, which fail there too, stay as witnessed cases.
- Develop step 3: no item under Not formed in analyze.md gave a case. The two models it gives (dots erased once joined, output cropped to the assembly) fail Fit at every train pair, and the `SharedColor` item states no model.
- Develop steps 4 and 5: `store` prints no value to store, and `derive` prints no derivation that fits.
- The branches `$PieceByColor`, `anchor=RarestColor`, `$FacingJoin`, `$TurnPieces` and `$LooseDots` have no witness in analyze.md, which finds that each one fails Fit. They are not constructors.
- The Determine relations: `bg` is the commonest color of every train input; `connector` is the color no cell of which lies beside no color other than its own and the background in any train input; `anchor` is the color of the part that fills its box, through `Parse`, which the program shares for `$AnchorSolidBlock`. `determination: ok (anchor, bg, connector)`.
- Performance: Souffle scanned the whole of `place` for the atom `place([A, C, O, B], [Ob, W])`, whose second argument is a record built from bound variables, and a run on one grid took 44 s. With `place` as flat columns the run took 0.7 s. The whole run takes about 5 s.
- No file under `src/` was read.

## Unsettled
- The audit's derive section still prints that `bg=DominantColor` fails Fit at test 0: a lib construction that lets the concept case fit the tests, or a rule for a derive branch whose only failure is the concept's own, would settle it.
- The audit's store section skipped `lead.edge`, over 20000 rows on an input.
- `deletions` did not run: its baseline needs the stored source to pass train and test.
- The cases that left under Subsumption rest on the approximation: with a search that states `pieces-fit`, `$OverlapAllowed` can leave a fit ambiguous where `$Disjoint` does not, and those cases would come back.

## Concept faults
- cbebaa4b `pieces-fit` (and `assemble`, which reads its fit): it needs a search over joint translations of the pieces, which is recursion through negation (a placement is refuted when one of its dots has no live placement of another piece to meet it, or when it clashes with the one live placement of a piece), or a recursion that builds one state per partial assembly. The program bans recursion. A walk that states such a universal needs an order over placements, and the `typed-order` lint rejects an order on `Ident`. No lib relation states it: `PlacementPruning` refutes a candidate only where some piece has no compatible candidate, `CoverForcing` needs an exact cover, and `Take` needs states that atoms outside its recursion ground.

## Fixes elsewhere
- none

## Tickets filed
- tickets/deferred/17-118_task_cbebaa4b_create.md
- tickets/new/17-119_task_cbebaa4b_create.md
- tickets/new/17-120_task_cbebaa4b_create.md
