# Prediction, before any fit

Written by the design agent. No model was fit. The coordinator's prediction was not read.

Set H, form-runs of `sampler-form-rows.tsv` with `pop` `ready_end`, last write, M-T:

| Measure | Hand score | Prediction, median | 80% range |
|---|---|---|---|
| M1, chance per opening of holding all reads, replay | .00055 | .002 | .0007 to .008 |
| M2, absolute rank of RULE reads | about 4,500 | 1,500 | 500 to 3,500 |
| M3, form-runs at .1 or more, of 34 | 2 | 3 | 2 to 6 |

Set B, gain in median chance over the hand score: 3 times, 80% range 1.5 to 8 times.

Verdict: Weak at 45%, Closed at 30%, Signal at 20%, Useful or better at 5%.

M-TS against M-T: tune favors M-TS, and on held tasks the two are within 2 times of each other at 70%.

C-hand against M-T: C-hand reaches at least a third of M-T's gain at 60%, since the hand reader's faults hurt some tables and the objective acts on the top ranks.

Session key labels: reads with no table fall by 5 to 20 points from 71.5% at 3,600 s on the 13 tasks. Base M1 stays within 3 times of .00055.

Why: earlier content features on picks added about 0 over structure, and hand scores hold about 3 bits in a depth band. The reader fixes give real gain, as 43% of nodes have alternatives and 31% have tables that the hand reader skips. Per-instance facts can't tell which of many well-formed junk tables a program needs. Rank 10 of 14,700 needs a false positive rate near 1 in 1,500, which these facts don't give at the recall the forms need.
