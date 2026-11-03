#!/usr/bin/env python
"""Writes results-section.md: the section "### Relation pick rank" from final-table.md."""
import os

D = os.path.dirname(os.path.abspath(__file__)) + '/'
table = open(D + 'final-table.md').read().strip()
text = f"""### Relation pick rank

A rank model on the relation pick, link 1 only (`features-relation-pick-rank-context-rows-heldout37`). The model is softmax boosting over a pick's options, started at the steered prior's log probability, so a gain is a gain over that prior: 500 trees of 8 leaves, step .1. Fit on 26,237 picks and 2,492,801 option rows of RULE forms from 1,010 non-held tasks, 849 train and 161 test, with all earlier forms in the context, gold from `corpus-v3mix`. A train task's prior comes from a steer fit without its task fold. A test task's prior comes from the steer in use, which was not fit on it. The steer without fold 0 pays 3.26 bits on test rows, against 3.31 for the steer in use. Tune read: task folds of the 161 test tasks, parents context. Held read: once per model, on the census's picks, Mac, engine ba0754492.

Baseline: 1,959 of 1,959 picks equal the census's bits on 431 valid forms. The 3.08 of [Relation pick: where the bits sit](#relation-pick-where-the-bits-sit) is per atom: the bits at the 1,761 picks where gold is alive, over all 1,786 atoms, with the 198 picks where gold is dead by join counted as 0. Per pick, the prior pays 3.13 at gold-alive picks and 3.26 at all picks. Saved bits below are per pick on the same picks.

Intervals are 95%, from 10,000 resamples of the 37 tasks. "Thin" marks under 50 picks or under 8 tasks. A class and position with no row has no picks.

{table}

- Saved on all picks: +.299 (+.247 to +.351) without content features, +.305 (+.254 to +.354) with them. Per atom: +.33 of 3.57.
- Content features add +.006 (-.015 to +.029). They read the option's table, its join against the prefix table, its overlap with the derived tables in scope, and its cells and colors against the train pairs. 62% of relation options have a table, 70% of gold's, and 66% of picks after the first atom have a prefix table. The rest read as no content.
- Control: the model with content, fit on a label drawn from the prior, loses .018 (.006 to .032) on held picks. That is the cost of fitting noise, and it shows no leak.
- The context of the fit matters. On tune tasks at equal size, 200 trees, a fit on parents rows saves .35 and a fit on rows with all earlier forms saves .23, on the same picks. The parents context is built from gold's reads, so the table above comes from the fit on all earlier forms.
- The count of scope forms that read an option carries .08 of that .23: without it the tune read is .15. Each form of gold's text has a reader, and this read doesn't show that the count acts the same way in a pool.
- At 500 trees the tune read still rises, by about .013 per 100 trees.
- Cost: the content features take 45 CPU ms per pick, median form 15 ms, with lib tables kept for a task. 500 trees take 6 ms per pick without content and 10 ms with it, on 2 threads. Forms have 4.5 relation picks each, so content adds about 200 ms a form against about 180 ms for a proposal.

Prediction, written before any fit: .3 in all (.1 to .5) held. About .2 without content and about .1 from content missed: structure gives .30 and content about 0. No class reaches 1 bit, derived relations gain most in total and later atoms gain more than first atoms: all held. Lib relations gain most per pick.

Finding: misses the 1 bit bar, so this isn't the next steer: the upper limit is +.35. It doesn't meet the .3 close bar either: the interval holds .3 and the point with content is +.305, though gold-alive picks, the population of the 3.08, read +.25 and +.26. Content features add nothing above noise at this cost.
"""
open(D + 'results-section.md', 'w').write(text)
