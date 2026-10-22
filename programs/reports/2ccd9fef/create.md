# 2ccd9fef

Create and Refine pass for change 9-216, written again on the lib at dd5823bf. The files under `2/` were read as notes.

## Catalog
- `DemonstratedChoice`: `Stretch`, `Push`, `Stay`, each with its own clauses over the tracked figures.
- `catalog.confirmed` per input: train 0 `Stretch`, `Stay` (one grid); train 1 `Push`; test 0 `Stay`; test 1 `Stretch`.

## Judgments
- Train 0 and test 1 demonstrate one rule, `Stretch`: a figure travels with one end while its other end runs out ahead, and the gained lines repeat the leading end's line. Train 0's figures travel with a still end. A train-0 rule of its own, with the still end required, would be `Stretch` restricted, and would add no prediction, so the catalog holds three rules for four inputs.
- `Stay` is also confirmed on train 0 and gives the same grid.
- Figures are 4-connected components, tracked from stage to stage by a shared cell. On per-line runs, `Push` would be confirmed on train 0, train 1 and test 1 alike, so runs do not tell the inputs' rules apart.
- The growth axis is the axis across the strip.
- `recolor` keeps a color whose stage turns disagree. Train 1's 4 turns into 1 at (2,4) and stays 4 at (3,4). Only `Stay` reads `recolor`.
- One case, with no `Choice`. The earlier cases (`$Slices`, `$Runs($Velocity)`, `$Runs($Demo)` with `Drag`) each build each input's growth through one parameterized mechanism, which change 9-216 rules out, so none is kept. Their witnesses go with them, and the witness file holds none.
- Deletions run: each deletion it reports was kept, because each states part of a rule that the pairs do not test, such as `!succ_stage(Pan, J)` in `recall`, which keeps a demonstration from reading its own answer.

## Open
- Branches of the catalog concept, such as runs in place of components, rank in place of overlap pairing, and a stored blank-panel end, were not formed: no Analyze pass ran on the new concept.
