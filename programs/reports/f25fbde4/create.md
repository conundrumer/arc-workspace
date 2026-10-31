# f25fbde4

## Departures
- The solver has a branch `ink=RarestColor`, a `@derive RarestColor: variant concept` line on `ink` (read by `$CropInkColor`), which `analyze.md` does not give: `run_dl.py derive` reports that RarestColor fits `ink`, and Develop step 4 holds each built-in derivation that fits. Its witness `ink=RarestColor` is train0's input with 4 recolored to 1. On it, `$CropInkColor` at the stored `ink` 4 is undefined, and `$CropInkColor & ink=RarestColor` gives the concept's output.
- The solver has no `impl_choice` and no enumerators: every combination of the three `Choice` fields is a case, and after `out` stopped reading `impl_choice`, no clause read it. `deletions` showed that the atom changed nothing.
- `Determine` has relations for `ink`, `factor` and `axis_factor`, which the Analyze files do not give: `determination-plan` asked for them.

## Judgments
- The `bg-source` branch `bg=DominantColor` is a `@derive DominantColor: borderline concept` line on `bg`, and not a constructor. Its `@relaxed` lines are `one-drawing` and `blank-field`, as `analyze.md` gives them.
- `ink=RarestColor` witness: plausibility `variant`, because a color permutation of a train input is a variant task. It breaks `one-drawing` (ink 4) at the stored assignment, so it is `@relaxed one-drawing`. Verdict `concept`: the generator doubles the recolored drawing.
- The "Not formed" item "`factor` from the number of 8-connected components plus one" fails Relational form: the "+1" needs arithmetic, which the program bans, and no lib relation states it. The fractal and cell-count items fail Fit at train0. So Develop step 3 forms no branch.
- Hints "case section" (`box`, `cropped`, `out`): the clauses that every case shares were under a `// --- concept ---` marker. I moved them above the case markers, and the hints stopped.
- Hints "determine prediction" on `factor` and `axis_factor`: these are kept with `@ignore`. `tile_size` reads the block side from the drawing box's extent and the output's extent, and `misfit` only drops a side that some train pair contradicts. The value is read from the evidence, and is not a guess.
- `bg` has no determination relation: DominantColor derives it from the commonest color, and `blank-field` gives the background as that same fact. `ink` has the relation "the input's color other than `bg`", because RarestColor derives it from a different fact (the least common color).
- `deletions` items that are kept: `largest.value` (no pair has two pieces, so no tie occurs), and `misfit` with its negations (no train pair contradicts a fitting side). In both, the pairs never instantiate the structure.
- 7 of the 18 cases are witnessed: the concept case, the four non-concept constructors, and the two `@derive` branches. No input of the task or of the witness file gives a combination an output that its partial cases do not give.
- Keywords: `crop` and `scale` come from the concept, `objects` and `rank` from `$CropObject8` (the largest piece), and `count` from `$FactorColorCount`.
- `witness --file programs/reports/f25fbde4/witnesses.json` printed no difference. `record --all` rewrote the groups of the witness file to add the two `@derive` branches.

## Unsettled
- `Determine` builds the drawing box of each train input from `ex_in`, and this repeats the program's `$NonBg & $AllSelected` box over `in`. It is not in `Parse`, because the program's box is keyed per `CropKey` over `selected`. To settle it, decide whether a `Parse<Key>` that holds the non-background box, keyed by example and by unit, is the principled form when only one case's box is shared.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
