# cbebaa4b

## Departures
- The coordinator gave this instruction: "Find a form for `pieces-fit` that follows how a person actually solves cbebaa4b. [...] If it puts every piece at its fit place, encode it in the solver and run the usual checks." It replaces the join cover of refine-1.md and the per-dot pick of refine-2.md. The form put every piece at its fit place in the Python model on all four inputs. It is now the solver's program, and every case it keeps passes train0, train1, test0 and test1.
- The program runs the form as an approximation of `assemble`, with the `@approximated:` line and the witness `twin-pairs` (see Judgments). The judged output of `twin-pairs` was written by hand and checked against a Python search over joint translations, which finds one fit inside the grid with the pieces apart. It does not come from `grid` on a control grid. Every change that makes the program decide that input also changes the shape or the dots of a piece, and so changes the output.
- Two cases taking `$Inside` failed Subsumption against the case taking `$ClipAssembly` in its place, and left: the case that takes the branch `$OverlapAllowed` alone, and each other case that took `$OverlapAllowed` with `$Inside`. `witness` found no run on which the `$Inside` case was defined and differed. `$Inside`, like `$Disjoint`, only rejects an assembly that the two steps found apart from the bounds. `impl_choice` now holds the concept case and the four cases `[A, C, $OverlapAllowed, $ClipAssembly]`. The `$Disjoint` cases left in the same way (create.md). The `@ignore: derive $Disjoint` text now names both branches.
- The witness file holds the inputs of witnesses.json again for `anchor-not-solid`, `connector-recolored`, `bg=DominantColor`, `assembly-past-edge` and `shared-cell`. On each, the kept cases give the grids witnesses.json gives. This reverts refine-1.md's two-dot inputs, because the program now decides inputs with many dots. `field-tie` and `touching` keep refine-1.md's two-dot inputs.
- The determination relation of `anchor` keeps the color of a part that fills its box only where every example input holds that color (refine-1.md).
- `witness --file programs/reports/cbebaa4b/witnesses.json` cannot compare the groups `$AnchorSolidBlock`, `$ConnectorDerived` and `$ClipAssembly`, because the model of each of these branches alone is no case of the solver (create.md). The cases that take each branch with `$OverlapAllowed` and `$ClipAssembly` give the grids witnesses.json gives the branch.
- The witness file names the background branch `bg=DominantColor`, where witnesses.json names it `background=DominantColor`. [Witness file](docs/handbook/solver-file.md#witness-file) builds that name from the parameter's name, `bg` (create.md).
- Under `$ClipAssembly`, a piece takes only a place that puts some cell of it on the grid, or on one of the eight copies of the grid one grid extent away (create.md).
- The witness `off-edge` stays removed, because it separated `$Inside` from `$ClipAssembly` only through create.md's approximation (refine-1.md).

## Judgments
- What a person does on the four inputs:
    - Each piece's dots form a pattern: two dots on one side at some spacing, two dots on a corner at some offset from each other, or a lone dot.
    - A person matches a pattern with the same pattern on another piece, at the offset where both dots of each meet and the two pieces do not run into each other. Examples: 3's bottom pair 4 apart and 8's top pair 4 apart (train0); the large 8's two dots 1 row and 5 columns apart and the 4 block's (test0).
    - Where a dot could go to two such matches, a person takes the match that is the only one left for some other dot. On test0, the 9's dot (10,5) goes with the small 8's top pair, so the 9 joins the large 8 by its dots (8,3),(9,4) and not by (9,4),(10,5).
    - The dots left over pair up last. On test1 these are the vertical `3`'s one dot and the large 8's top dot.
    - The pieces then go in place one by one, outward from the `4` piece.
    - Every join on train0, train1 and test0 has two dots on each side. Test1 has one lone-dot join.
- The relations that state those steps:
    - A join is a `Canon` class of two pieces at an offset.
    - `overlap` excludes a join that puts any other cells of the two pieces on one place.
    - A first `CoverForcing`, `matched`, takes the joins at which two or more dots of each piece meet. A dot that only one of them can take forces it, and a join that shares a dot, or the pair of pieces at another offset, with a forced join is out.
    - A second `CoverForcing`, `paired_up`, takes the joins among the dots that no forced join took.
    - `Propagation` moves the pieces out from the anchor along the forced joins.
    - The checks after the places are unchanged.
    - The only search is the one the converter's `CHOOSE` adds where elimination stalls, over the few joins with two meeting dots.
- What the Python model gives (person.py in the session scratchpad):
    - train0: 4 two-dot joins, all forced.
    - train1: 4 two-dot joins, all forced.
    - test0: 7 two-dot joins, 6 forced. The 8 and 9 join at the tied offset is out.
    - test1: 6 two-dot joins, 5 forced. The second join of the 4 block and the comb 3 is out. The two dots left, (0,3) and (14,4), pair up in the second step.
    - On every input, each piece takes its fit place.
- Why `assemble` has no relational form: it reads the one joint translation that meets `pieces-fit`. Telling that translation apart takes a search over joint assignments, which no set of clauses in the program states. The two eliminations decide wherever some dot has one join left at each step. Where every dot keeps two or more joins, they place nothing, and every case is undefined.
- Witness `twin-pairs`, borderline, other. The 1 bar and the 6 bar each carry a pair of dots 2 apart below them. Both the 4 block and the 3 frame carry a pair of dots 2 apart above them. So no dot has one join left, and only the joint placement keeps the bars apart. It breaks no scene claim. It is borderline because in each of the four inputs, each pair of dots has one pair of the same spacing facing it, which the generator seems to keep to.
- Deletions:
    - Of the 55 deletions that change nothing, most remove the checks after the places (`broken`, `doubled`, `shared_dot`, `anchor_rival`), the `$ClipAssembly` bounds, the rival conflicts, or `overlap`. The pairs never exercise these, and each states a part of `pieces-fit` or of a branch, so they stay.
    - The `dir_elem(D)` atoms keep `neighbor` to the cardinal directions, so they stay.
    - `!matched.ruled_out` in `taken` guards a forced join that a later forced join rules out, so it stays.
    - The determination atoms the report lists keep the determinations exact on inputs other than the train pairs, so they stay.
- Hint `single-consumer` on `chosen`: `chosen` was folded into `lead.edge`.
- `sweep`: `bg`, `connector` and `anchor` are each unique at the stored value. At `connector` = 0, train 0 timed out, and no finding rests on that run.
- The audit is clean. `derive` now finds that `bg=DominantColor` fits, which settles the derive item of create.md and refine-1.md. The relabelings check passes.
- Hint `head-zero` on `place` and hint `common-subexpr` on `near` are kept with `@ignore` (create.md).
- Keyword `assemble`, proposed and on the `@keywords:` line: "pieces translate so that the join marks they carry meet, and together they form one figure" (create.md).
- The branches `$PieceByColor`, `anchor=RarestColor`, `$FacingJoin`, `$TurnPieces` and `$LooseDots` are not constructors, because analyze.md finds that each one fails Fit (create.md).
- Performance: `place` keeps flat columns (create.md). A run takes 1 to 7 s, and `deletions` took 74 s.
- No file under `src/` was read.

## Unsettled
- The audit's store section skipped `lead.edge`, which has over 20000 rows on an input. A store check that reads a relation of that size would settle it.
- Under the converter's `CHOOSE`, `twin-pairs` has two covers in the first step. One of them leaves two pieces on one place, and its model gives `out` no rows. Whether the output is then the fit or undefined depends on how the engine treats a model with no rows (refine-1.md). On the four inputs, the first step has one cover, because every dot that a two-dot join covers is covered by one forced join. On test1, the two leftover dots have no two-dot join.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
