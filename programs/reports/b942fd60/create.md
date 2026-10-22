# b942fd60

## Departures
- The concept fits every pair, train 1 included: the Analyze report says the concept fails Fit at train 1 because the output leaves out the branch at (1,3), but `data/tasks/b942fd60.json` now has 2 at (0,3), (3,0), (3,1) and (3,3) of the train 1 output, and the probe in `work/task/b942fd60/probe.py` and the solver's run both give every train output and the test output under every formed branch.
- The Analyze witness `background=DominantColor` is renamed `marks-outnumber-background`, and its branch name is rewritten to `bg=DominantColor`: `derive` records its own witness under the id `bg=DominantColor` (train 0 with the background recolored to 1). The Analyze witness stays as a further witness of that branch, and its judgment (`borderline concept`, relaxed `scattered-marks`) is not on a solver line.

## Judgments
- `@derive DominantColor: variant derived`, `@relaxed background` on `bg`: the witness `derive` built is train 0 with every 0 recolored to 1. A color permutation of the task is a variant task, and its generator pairs that input with the output the derived background gives. It breaks `background` at the stored value 0.
- `seed_edge` takes `@ignore: store`: `store` reports it as DIR_L on every input. A stored seed edge gives the start direction opposite it, which is what `$StoredStart` stores, so every case that stores it is equivalent to the `$StoredStart` case with the same other branches, and it takes more non-concept branches (Equivalence).
- Not formed, re-checked on the current data: "an obstacle branches only the first ray that stops before it" still fails Fit at train 1, under order of arrival by ray generation and by cells run (an event-ordered probe). The other Not formed items are derivations `derive` does not list as fitting, a redundant value, or another orientation type; none was formed.
- The sweep reports one single-row change of `obstacle` that gives every train output. The set stays {3, 6, 7, 8}: the `$StoredObstacleColors` reading is the set of colors the marks show, and nothing in the evidence points a reader to any other color, so it is not an open parameter.
- Determination: `obstacle` is the train input colors that no train output paints over, less the line color; `start` is the directions whose next cell from the seed takes the line color in every train output.
- Deletions that change nothing on the pairs stay: the `$SeedBlocks` blocked-seed clause, `corner_seed` and its negation (the undefinedness of `$StartFromSeedEdge`), and `!params.line(Col)` in the `$NonBackground` obstacle set each state their branch's claim on inputs the pairs do not show (`ray-meets-seed`, a corner seed). `ex_out(E, _, _)` in Determine's `obstacle` keeps the clause over train examples, as the determination rule for test inputs states. The redundant `params.line`/`ex_in` atoms in `unpainted` were removed.
- Keywords `markers cast walk`: the seed fixes where the line starts, rays extend along lines, and each new ray depends on where the previous one stopped.
- The solver has 24 cases (four two-way points, and `bg=DominantColor` on the 8 `$NonBackground` bases); 7 are witnessed, and `witness` reports no unseparated pair and no unwitnessed defined case.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
