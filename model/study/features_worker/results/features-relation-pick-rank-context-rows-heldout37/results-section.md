### Relation pick rank

A rank model on the relation pick, link 1 only (`features-relation-pick-rank-context-rows-heldout37`). The model is softmax boosting over a pick's options, started at the steered prior's log probability, so a gain is a gain over that prior: 500 trees of 8 leaves, step .1. Fit on 26,237 picks and 2,492,801 option rows of RULE forms from 1,010 non-held tasks, 849 train and 161 test, with all earlier forms in the context, gold from `corpus-v3mix`. A train task's prior comes from a steer fit without its task fold. A test task's prior comes from the steer in use, which was not fit on it. The steer without fold 0 pays 3.26 bits on test rows, against 3.31 for the steer in use. Tune read: task folds of the 161 test tasks, parents context. Held read: once per model, on the census's picks, Mac, engine ba0754492.

Baseline: 1,959 of 1,959 picks equal the census's bits on 431 valid forms. The 3.08 of [Relation pick: where the bits sit](#relation-pick-where-the-bits-sit) is per atom: the bits at the 1,761 picks where gold is alive, over all 1,786 atoms, with the 198 picks where gold is dead by join counted as 0. Per pick, the prior pays 3.13 at gold-alive picks and 3.26 at all picks. Saved bits below are per pick on the same picks.

Intervals are 95%, from 10,000 resamples of the 37 tasks. "Thin" marks under 50 picks or under 8 tasks. A class and position with no row has no picks.

| Picks read | Picks | Tasks | Prior bits per pick | Saved, no content | Saved, with content |
|---|---|---|---|---|---|
| All | 1959 | 37 | 3.26 | +0.30 (+0.25 to +0.35) | +0.30 (+0.25 to +0.35) |
| Gold alive | 1761 | 37 | 3.13 | +0.25 (+0.20 to +0.31) | +0.26 (+0.21 to +0.32) |
| Derived relation in scope | 886 | 37 | 3.26 | +0.35 (+0.30 to +0.41) | +0.37 (+0.30 to +0.44) |
| Lib relation | 246 | 34 | 4.58 | +0.67 (+0.51 to +0.83) | +0.67 (+0.53 to +0.82) |
| The form's own earlier atom | 224 | 36 | 2.92 | +0.05 (-0.10 to +0.23) | -0.01 (-0.15 to +0.12) |
| The rest | 603 | 36 | 2.84 | +0.16 (+0.08 to +0.24) | +0.18 (+0.10 to +0.26) |
| First atom | 431 | 37 | 2.60 | +0.11 (+0.03 to +0.18) | +0.15 (+0.08 to +0.21) |
| Second atom | 473 | 37 | 3.27 | +0.29 (+0.21 to +0.37) | +0.32 (+0.23 to +0.41) |
| Third atom | 371 | 37 | 3.25 | +0.33 (+0.26 to +0.40) | +0.32 (+0.24 to +0.39) |
| Later atoms | 684 | 36 | 3.67 | +0.41 (+0.32 to +0.51) | +0.39 (+0.31 to +0.47) |
| Derived relation in scope, first atom | 355 | 37 | 2.53 | +0.18 (+0.12 to +0.25) | +0.21 (+0.15 to +0.27) |
| Derived relation in scope, second atom | 268 | 37 | 3.25 | +0.37 (+0.31 to +0.44) | +0.40 (+0.31 to +0.50) |
| Derived relation in scope, third atom | 125 | 37 | 3.86 | +0.36 (+0.22 to +0.50) | +0.34 (+0.21 to +0.49) |
| Derived relation in scope, later atoms | 138 | 34 | 4.63 | +0.75 (+0.50 to +1.00) | +0.74 (+0.50 to +0.99) |
| Lib relation, first atom (thin) | 12 | 8 | 7.16 | -0.91 (-1.77 to +0.60) | -0.64 (-1.29 to +0.51) |
| Lib relation, second atom (thin) | 49 | 20 | 4.76 | +1.18 (+0.89 to +1.44) | +1.26 (+0.95 to +1.57) |
| Lib relation, third atom | 67 | 26 | 4.74 | +0.75 (+0.59 to +0.91) | +0.68 (+0.51 to +0.85) |
| Lib relation, later atoms | 118 | 33 | 4.15 | +0.57 (+0.43 to +0.74) | +0.55 (+0.42 to +0.70) |
| The form's own earlier atom, second atom (thin) | 33 | 16 | 2.92 | -0.42 (-0.58 to -0.23) | -0.36 (-0.47 to -0.24) |
| The form's own earlier atom, third atom (thin) | 36 | 24 | 1.98 | -0.20 (-0.48 to +0.05) | -0.17 (-0.44 to +0.10) |
| The form's own earlier atom, later atoms | 155 | 33 | 3.13 | +0.21 (+0.01 to +0.43) | +0.10 (-0.07 to +0.25) |
| The rest, first atom | 64 | 29 | 2.12 | -0.09 (-0.24 to +0.03) | -0.03 (-0.15 to +0.08) |
| The rest, second atom | 123 | 33 | 2.82 | -0.07 (-0.16 to +0.02) | -0.06 (-0.14 to +0.02) |
| The rest, third atom | 143 | 34 | 2.33 | +0.24 (+0.12 to +0.36) | +0.25 (+0.14 to +0.36) |
| The rest, later atoms | 273 | 36 | 3.28 | +0.28 (+0.16 to +0.41) | +0.30 (+0.18 to +0.43) |

- Saved on all picks: +.299 (+.247 to +.351) without content features, +.305 (+.254 to +.354) with them. Per atom: +.33 of 3.57.
- Content features add +.006 (-.015 to +.029). They read the option's table, its join against the prefix table, its overlap with the derived tables in scope, and its cells and colors against the train pairs. 62% of relation options have a table, 70% of gold's, and 66% of picks after the first atom have a prefix table. The rest read as no content.
- Control: the model with content, fit on a label drawn from the prior, loses .018 (.006 to .032) on held picks. That is the cost of fitting noise, and it shows no leak.
- The context of the fit matters. On tune tasks at equal size, 200 trees, a fit on parents rows saves .35 and a fit on rows with all earlier forms saves .23, on the same picks. The parents context is built from gold's reads, so the table above comes from the fit on all earlier forms.
- The count of scope forms that read an option carries .08 of that .23: without it the tune read is .15. Each form of gold's text has a reader, and this read doesn't show that the count acts the same way in a pool.
- At 500 trees the tune read still rises, by about .013 per 100 trees.
- Cost: the content features take 45 CPU ms per pick, median form 15 ms, with lib tables kept for a task. 500 trees take 6 ms per pick without content and 10 ms with it, on 2 threads. Forms have 4.5 relation picks each, so content adds about 200 ms a form against about 180 ms for a proposal.

Prediction, written before any fit: .3 in all (.1 to .5) held. About .2 without content and about .1 from content missed: structure gives .30 and content about 0. No class reaches 1 bit, derived relations gain most in total and later atoms gain more than first atoms: all held. Lib relations gain most per pick.

Call: this isn't the next steer, as the upper limit of +.35 is far under the 1 bit bar. The search-structure question closes. Gold-alive picks read +.25 and +.26, all picks read +.299 and +.305, and the part of the reader count may not carry to a pool. The interval holds .3 on both sets of picks. Content features add nothing above noise at this cost.
