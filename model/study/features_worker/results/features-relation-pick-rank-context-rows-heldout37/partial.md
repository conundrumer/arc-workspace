# Relation pick rank: partial

Fit on 81 of the 161 test tasks, by 2 of 5 task folds, 1,674 fit picks, read on the other task folds. Not a held-out read. No held task's model read exists yet.

| Arm | Saved, bits per pick, tune tasks, 120 trees |
|---|---|
| Without content features | .33 |
| With content features | .33 |

Baseline on the 37 held tasks: 1,959 of 1,959 picks equal the census, 431 valid forms. 3.082 is bits at gold-alive picks over all 1,786 atoms: it is per atom, with the 198 gold-dead picks counted as 0. Per pick the prior pays 3.13 on gold-alive picks and 3.26 on all picks.

Later tune read, on parents rows of test tasks in folds held out of the fit. Fit on all-earlier-forms rows of 1,010 tasks, about 25,000 picks, 8 leaves, step .1. No content, 2 folds: .29 at 300 trees. With content, 1 fold: .31 at 300 trees, against .29 for no content on that fold. No content, 1 fold: .32 at 500 trees. Control on a label drawn from q, 1 fold: -.005 at 200 trees.
