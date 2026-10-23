# cbebaa4b

## Departures
- The override is applied: "`pieces-fit` and `assemble` have a stateable form. Encode them this way, in place of the most-meeting-offset approximation". A join is a `Canon` class of the two directed views of two pieces at an offset. A join covers the `connector` dots that meet under its offset. `CoverForcing`, keyed by the dot color, takes the dots as its cells and the joins as its pieces. Its `conflict` holds between two joins of the same two pieces at different offsets. Each `forced` join that is not `ruled_out` is an edge of `Propagation` over (piece, offset) nodes, bounded as before, with the anchor at `ZERO` as its source. The checks that follow the places are unchanged: each piece takes one place, each dot meets exactly one dot, and (`$Disjoint`) no other cells share a place. The `@approximated:` line and its witness `tied-join` are removed. The witness `off-edge` is also removed, because it separated `$Inside` from `$ClipAssembly` only through the approximation's joins.
- No case fits the task. Every case is undefined on train0, train1, test0 and test1, and `run` prints "no case emitted a grid" for each one. analyze.md finds that the concept fits every pair. The cause is that `CoverForcing` forces no join on any of the four inputs (`relation cbebaa4b cover.forced cover.ruled_out` on train1: no rows). See Judgments for why.
- The witness file pins the branches on new inputs: two pieces with one dot each. The witnesses in witnesses.json are built from train pairs, each with 16 or more dots, and every case is undefined on them. `anchor-not-solid`, `connector-recolored`, `bg=DominantColor` and `assembly-past-edge` keep their ids, plausibilities and verdicts, and separate the same feature on the new inputs. `field-tie` and `touching` are rebuilt in the same way. `shared-cell` keeps its input from witnesses.json, and every case is undefined on it.
- The `$OverlapAllowed` case `[ByColor, StoredConnector, OverlapAllowed, Inside]` and the non-concept cases that take `$Inside` stay, against the two `witness` findings under Unsettled. No two-dot input separates them, so no witness file input can separate them. For `$OverlapAllowed`, the two pieces have two colors, so a shared cell takes two colors in both cases. The models the override describes differ on witnesses.json's `shared-cell`, where the one place-consistent cover puts two `1` pieces on one cell.
- The determination relation of `anchor` keeps the color of a part that fills its box only where every example input holds that color. `determination-plan` showed that with `anchor-not-solid`'s pair added, the relation also kept `5`. The plan now prints `no actions`, and `run` prints `determination: ok (anchor, bg, connector)`.
- The cases that take `$Disjoint`, other than the concept case, are not cases of the solver. Each one left under Subsumption. `$Disjoint` adds one check to an assembly that does not depend on it, so where a case that takes `$Disjoint` gives a grid, the case that takes `$OverlapAllowed` in its place gives the same grid (create.md).
- `witness --file programs/reports/cbebaa4b/witnesses.json` cannot compare the groups `$AnchorSolidBlock`, `$ConnectorDerived` and `$ClipAssembly`, because the model of each of these branches alone takes `$Disjoint` and is no case of the solver (create.md). Each case is also undefined on each of those inputs.
- The witness file names the background branch `bg=DominantColor`, where witnesses.json names it `background=DominantColor`. [Witness file](docs/handbook/solver-file.md#witness-file) builds that name from the parameter's name, which is `bg` (create.md).
- Under `$ClipAssembly`, a piece only takes a place that puts some cell of it on the grid, or on one of the eight copies of the grid one grid extent away. The places must be a finite set given before the propagation runs (create.md).

## Judgments
- Why `CoverForcing` forces nothing: each dot of piece P has one candidate join per dot that lies outside P. Elimination starts only at a dot with one candidate left, so it starts only where exactly one dot lies outside P. Even then, two dots of P force two joins of the same two pieces at different offsets, which rule each other out. So a join is placed only on an input with two dots on two pieces.
- What a full search of the override's form gives, from a Python model of it (exact covers of the dots by joins, with the same conflict): there are 1499 covers on train0, 705 on train1, and at least 100000 on each of test0 and test1. On each input, exactly one cover gives each piece one place reached from the anchor. That cover lies inside the grid, keeps the pieces apart, and draws the pair's output, both tests included. The disjointness check removes no cover on these inputs, because place consistency already leaves one.
- What stops the form from deciding under a `CHOOSE`: the part of `pieces-fit` that gives each piece one place requires the joins around each cycle of pieces to sum to no offset. A cycle of three or more joins is not a pairwise constraint. The `never` that two joins of the same two pieces clash covers only the cycle of two. [Constraints](docs/arclog/constraints.md#what-it-replaces) lists a constraint that is not pairwise as not expressible. So the pick has 1499 to over 100000 models per input. Each model whose places clash derives `broken` and gives `out` no rows. Under [The output set](docs/arclog/constraints.md#the-output-set), such a model's grid has no color at any cell, so it is undefined, and every case is undefined on every pair unless the engine drops models with no rows.
- Witness plausibility and verdicts on the two-dot inputs are analyze.md's (`anchor-not-solid` borderline concept, `connector-recolored` variant `$ConnectorDerived`, `bg=DominantColor` variant derived, `assembly-past-edge` foreign `$ClipAssembly`). `field-tie` and `touching` stay borderline concept (create.md). Each input separates the feature its `separates` text states, and `grid` gives the expected two outputs on each.
- `derive` prints that `bg=DominantColor` fails Fit at train 0. The `@derive` line stays, because every case fails there in the same way (create.md, the failing pair now train 0).
- Determine: `sweep` swept no parameter, because the stored value fails train.
- Simplify: `deletions` did not run, because its baseline needs the stored source to pass train and test. The relations `overlap`, `meets`, `most`, `tie` and the type `Pair` are gone with the approximation.
- Hint `head-zero` on `place`: kept with `@ignore`. The zero offset is the anchor's place, which is no move (create.md).
- Hint `common-subexpr` on `near`: kept with `@ignore`. The second jump starts from the cells of the first (create.md).
- Keyword `assemble`, proposed and on the `@keywords:` line: "pieces translate so that the join marks they carry meet, and together they form one figure". `move` and `markers` each give part of it (create.md). `run` still prints the hint for it.
- The branches `$PieceByColor`, `anchor=RarestColor`, `$FacingJoin`, `$TurnPieces` and `$LooseDots` have no witness in analyze.md, which finds that each one fails Fit. They are not constructors (create.md).
- Develop step 3: no item under Not formed in analyze.md gives a case (create.md).
- Performance: `place` keeps flat columns. A record argument built from bound variables made Souffle scan the whole relation (create.md). A run now takes 1 to 8 s.
- No file under `src/` was read.

## Unsettled
- `witness` reports that no witness separates `$OverlapAllowed` from `$Disjoint`, and that no run shows `$Inside` defined and differing from `$ClipAssembly` in 8 pairs of cases. Two things would settle it: a ruling on whether a case's model is the Souffle `out`, where `CoverForcing` only eliminates, or the total pick that replaces it, and a pick that decides inputs with more than two dots.
- The override's form decides no pair in Souffle, and decides one only under an engine that drops a model with no `out` rows. A pick whose constraints are all pairwise would state all of `pieces-fit`. It would take one row per dot, and as candidate the dot's partner dot together with the place of the dot's own piece, with these `never` pairs:
    - two dots of one piece at different places
    - two dots that choose each other as partners at places that do not put them on one cell
    - a dot whose partner chose another dot
    - two dots of different pieces that land on one cell and are not partners
    - for `$Disjoint`, two dots whose pieces' places put other cells on one place

  Places come from the bounded set, with the anchor's dots at no offset. Each model of that pick is a fit.
- The audit's relabelings check did not run, because the stored program fails a train pair.
- `deletions` did not run, because its baseline fails.

## Concept faults
- none: the override, "`pieces-fit` and `assemble` have a stateable form", replaces create.md's fault on `pieces-fit`.

## Fixes elsewhere
- none

## Tickets filed
- tickets/new/15-28_task_cbebaa4b_refine.md
