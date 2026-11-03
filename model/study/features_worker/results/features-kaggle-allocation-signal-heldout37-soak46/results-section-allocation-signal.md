### Allocation signal

Whether pool observables that read no gold and no test output tell how close a task is to a candidate, at a time that the kernel can spend on a task. Read 2026-11-01, 08:40 EST. Run folder: `features-kaggle-allocation-signal-heldout37-soak46/`, with `manifest.json`.

- Target: census of `gold-v3-rigid-round50`, as the ast corpus of gen-v3 holds it, parents context, priors that leave out the 99 evaluation tasks, sampler 8a5ffec60. 79 tasks: the 37 held tasks and 42 evaluation tasks of the pool reads. 1,554 forms, 1,516 valid. The census has no row for 4 forms, of kinds with no walk.
- Forms with no bits: 38 forms that aren't valid, 25 of them with a RIGID_DET or CHOOSE form in scope, which the walk can't replay, and the 4 forms with no walk, on 14 tasks. Such a task ranks above every task on total bits and is negative on each binary target.
- Observables: nodes, forms, proposals, the best `gain` of `outfeat.py` over nodes, and forms with a Position column that gives exactly the output grid's cells on every train pair. Forms covered needs gold, so it is a reference column and it isn't in a joint score.
- Cut at S seconds: in events, the visits to S give the proposals and the forms, and nodes count to that draw. In worker logs, the last line at or before S, about every 12 s, gives the counts, and nodes count to that number in record order. The clock of a log adds the time before each renewal.
- Joint: logistic regression on within-arm ranks, 5 task folds, 5 repeats. Its weights are fit on held tasks by cross-fit, and weights for the kernel must be refit on non-held tasks.
- A pooled read compares tasks inside an arm, gives each task weight 1 over its arms, and takes a 95% task bootstrap of 2,000 draws.

Time on the kernel, by [Proposal rate on Kaggle](#proposal-rate-on-kaggle): 1 pod CPU s is 1.3 to 1.7 Kaggle CPU s, and a Kaggle worker gets .90 of a CPU, so 1 pod s is 1.4 to 1.9 Kaggle wall s.

| Pod s | Kaggle wall minutes |
|---|---|
| 60 | 1.4 to 1.9 |
| 300 | 7.2 to 9.4 |
| 600 | 14.4 to 18.9 |

The 300 s and 600 s cuts stand inside 5 to 20 minutes, 600 s nearest 20 minutes and 300 s nearest 5 minutes. Kaggle version 5 ran on Kaggle, so its cuts are 1, 5 and 10 Kaggle minutes, on sampling. No record ran search on Kaggle.

Gold's worst form under 25 bits: 0 positive tasks, 79 negative. Each of the census row sets on the 37 also gives 0 positive tasks. No AUC on that bar exists. The tables read a substitute target: worst form at or under 84.31 bits, the lowest third of the 65 tasks with every form drawable.

Pooled, arms with tables, 79 tasks, 204 rows, 7 arms, 22 positive and 57 negative on the substitute. Each cell gives the Spearman correlation with total bits, then the AUC. A negative correlation means more of the observable, fewer bits.

| Observable | 60 s | 300 s | 600 s |
|---|---|---|---|
| Nodes | -.12 (-.31 to .09); .54 (.37 to .70) | -.19 (-.38 to .03); .60 (.44 to .76) | -.21 (-.38 to .01); .58 (.41 to .74) |
| Forms | -.15 (-.33 to .06); .54 (.38 to .71) | -.22 (-.40 to .00); .62 (.45 to .77) | -.21 (-.40 to .02); .56 (.40 to .73) |
| Proposals | -.11 (-.30 to .08); .56 (.39 to .71) | -.20 (-.40 to .01); .64 (.47 to .79) | -.15 (-.35 to .05); .58 (.40 to .73) |
| Best OUT gain | -.02 (-.22 to .21); .47 (.32 to .62) | -.02 (-.21 to .17); .50 (.33 to .67) | -.11 (-.29 to .09); .61 (.44 to .77) |
| Forms of the output shape | -.26 (-.46 to -.03); .62 (.45 to .78) | -.25 (-.45 to -.01); .62 (.46 to .78) | -.25 (-.46 to -.01); .62 (.45 to .78) |
| Joint, cross-fit | -.15 (-.35 to .08); .49 (.32 to .66) | -.16 (-.36 to .07); .48 (.31 to .64) | -.14 (-.35 to .08); .53 (.34 to .71) |
| Grid area, smaller first | -.14 (-.33 to .07); .52 (.34 to .69) | -.14 (-.33 to .08); .52 (.34 to .69) | -.14 (-.33 to .08); .52 (.35 to .69) |
| Outputs keep the input size | -.14 (-.37 to .12); .58 (.45 to .69) | -.14 (-.38 to .13); .58 (.45 to .69) | -.14 (-.39 to .13); .58 (.45 to .70) |
| Forms covered, needs gold, reference | -.14 (-.33 to .07); .52 (.35 to .68) | -.27 (-.46 to -.04); .66 (.50 to .80) | -.26 (-.46 to -.03); .65 (.50 to .80) |

By read, AUC on the substitute. "Best" is the largest of the five no-gold observables at that time. Intervals are task bootstraps.

| Read | Tasks, positive, negative | 60 s | 300 s | 600 s |
|---|---|---|---|---|
| 37 held, job 23 and gate search arms | 37, 9, 28 | shape .64 (.44 to .81); joint .53 (.31 to .73); area .53; covered .61 | shape .63 (.43 to .82); joint .54 (.33 to .73); area .53; covered .57 | shape .64 (.44 to .81); joint .56 (.35 to .76); area .53; covered .58 |
| The 46: Kaggle version 5 and the soak, tasks with a target | 60, 19, 41 | shape .56 (.38 to .74); joint .37 (.19 to .56); area .49; covered .45 | proposals .58 (.39 to .75); joint .40 (.23 to .60); area .49; covered .65 | best OUT .60 (.43 to .77); joint .40 (.22 to .59); area .49; covered .65 |
| Pooled | 79, 22, 57 | shape .62 (.45 to .78); joint .49 (.32 to .66); area .52; covered .52 | proposals .64 (.47 to .79); joint .48 (.31 to .64); area .52; covered .66 | shape .62 (.45 to .78); joint .53 (.34 to .71); area .52; covered .65 |
| 37 held, 7 search arms, nodes, forms and proposals only | 37, 9, 28 | proposals .55 (.37 to .69); joint .43 (.28 to .59); area .53; covered .59 | proposals .51 (.33 to .67); joint .26 (.14 to .39); area .53; covered .58 | proposals .54 (.37 to .70); joint .40 (.24 to .56); area .53; covered .58 |

By arm, AUC on the substitute. An arm with no node records has the three cheap observables. A joint value under .5 means that no signal stays under cross-fit. Every run reached its cuts unless noted below.

| Arm | Tasks, positive, negative | Best at 60 s | Best at 300 s | Best at 600 s | Joint at 600 s | Covered at 600 s |
|---|---|---|---|---|---|---|
| Job 23 control | 35, 9, 26 | shape .65 | shape .69 | shape .69 | .51 | .55 |
| Job 23 factored | 35, 9, 26 | shape .59 | shape .69 | shape .69 | .59 | .64 |
| Gate control | 37, 9, 28 | shape .69 | proposals .62 | best OUT .63 | .47 | .55 |
| Gate | 37, 9, 28 | shape .57 | proposals .65 | forms .65 | .46 | .53 |
| Context control | 37, 9, 28 | proposals .62 | forms .40 | forms .58 | .44 | .61 |
| Context cover | 37, 9, 28 | nodes .60 | proposals .49 | proposals .53 | .14 | .61 |
| Job 17 search | 37, 9, 28 | forms .45 | proposals .48 | proposals .50 | .19 | .55 |
| Job 17 sampling | 37, 9, 28 | nodes .39 | nodes .41 | forms .45 | .38 | .58 |
| Kaggle version 5, sampling | 45, 17, 28 | shape .55 | proposals .58 | best OUT .61 | .41 | .65 |
| Soak, search | 8, 0, 8 | none | none | none | none | none |
| Soak, sampling | 7, 2, 5 | shape 1.00 | shape 1.00 | shape 1.00 | none | none |

Call against the bar of AUC .7 on a no-gold observable: it fails. On the 25-bit target no AUC exists. On the substitute, the pooled best no-gold observable reads .62 at 60 s, .64 at 300 s and .62 at 600 s, each interval crosses .5, and the joint score reads .49, .48 and .53. Forms covered, which needs gold, reads .66 at 300 s. Grid area reads .52, so grid size doesn't explain the signal, and there is little signal to explain. No allocation score for the kernel comes from these observables.

- Rank correlation with total bits: the best no-gold pooled value is forms of the output shape, -.26 at 60 s and -.25 at 600 s.
- Gold revision moves the read. On census `sampler-census-refit-heldout37-8a5ffec60`, its gold and the same 79 tasks, forms of the output shape read .68, .72 and .70, and joint .55, .64 and .65, with its own bar of 80.99 bits and 300 bootstrap draws. A shift of .10 at 22 positive tasks means a read near the bar isn't stable.
- With the 14 undrawable tasks left out, 65 tasks, 22 positive, forms of the output shape read .61, .64 and .63, and joint .46, .49 and .53.
- Thin arms: the soak's sampling arm has 7 tasks and 2 positive, and its search arm has 8 tasks and 0 positive, so neither reads alone.
- The soak is `kernel-soak-8a5ffec6`, 46 tasks. 31 of them have no target: training tasks, whose gold the priors hold, and evaluation tasks outside the 99. Its bundle's priors count every corpus task, so its pools aren't held out. The census bits are.
- Kaggle version 5 has 45 of its 46 tasks read; 981571dc has no gold in the list. The manifest of its run names no priors, so its pools are not known to be held out.
- The rows headed Kernel soak in [Gold helper rank by distance to OUT](#gold-helper-rank-by-distance-to-out) come from the records of Kaggle version 5, at about 1,196 s, and not from a soak of 1,800 s. The node counts match that record.
- Run status: job 23 and the gate arms reached their 600 s deadline, with no crash. Context control and cover ran to 3,600 s, with 68 of 74 workers killed past their end. Job 17 ran to 3,600 s, with worker deaths on 3 sampling tasks. Kaggle version 5 ran 1,165 to 1,196 s. In the soak, 6 workers were killed past their end. One sampling task, 0607ce86, ended at 424 s, and it has no target.

Recount with repairs. A form that a repair step finds costs no search bits, so it is set to 0 here, and each task's worst form is taken again. The 0 positive read above stands as it is: it is the census with no repair.

| Repair | Tasks on the list | Of the 79 | Outside the 79 | Forms set to 0 |
|---|---|---|---|---|
| ONE repair, the `--one` set of `sampler-one-repair/check.sh` | 15 | 2: 8e5c0c38, f560132c | 13 | 1 on each |
| CHOOSE lift, commit 96f903721 | 11 | 0 | 11 | none |

| Bar, bits | Before: every form drawable | After: every form drawable | After: over forms with bits |
|---|---|---|---|
| 25 | 0 | 0 | 1 |
| 28 | 0 | 0 | 1 |
| 32 | 0 | 0 | 1 |

- The lists name tasks and not forms. Rule for ONE: a form of a listed task whose text holds a `(ONE` mark. Rule for CHOOSE: a form of kind CHOOSE on a listed task. b7cb93ac is on both lists and outside the 79.
- On the 2 tasks, the worst form doesn't change: 65.52 bits on 8e5c0c38 and 267.57 on f560132c. 8e5c0c38 has every form drawable after the recount, and f560132c keeps 1 undrawable form. Tasks with an undrawable form fall from 14 to 13.
- The lowest worst form on a task with every form drawable is 35.19 bits, on 1818057f, and 32.10 bits on the earlier gold. The 1 task in the last column is 269e22fb, 18.38 bits, with 7 forms that have no bits.
- A ONE repair adds marks to a form, and the search still draws the rest of that form, so 0 bits for the whole form is an upper limit on the gain. No count depends on it, because neither form is its task's worst form.
- `sampler-one-drive.jsonl` has no trigger and no find on either task: gold without its marks passes its OUT test with an attempt on each test input. The 0 bits on these 2 forms is an assumption here, and no record of a find.
- cbebaa4b has 2 CHOOSE forms and is not on the list, so they stay undrawable.
