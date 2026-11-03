# Partial read

Non-held tasks done: 1,044 of 1,044, held 0 of 37. 45 plain tasks are set apart, because an output is or holds a D4 image of the whole input. That leaves 10 RIGID_DET tasks with several poses, 8 with one pose, 3 that look posed, and 978 plain. The base rate is 1.0%.

29 fixed forms are read. No form reaches recall .5 on any positive set.

| Form | Positive, of 10 | One pose, of 8 | Looks posed, of 3 | Plain, of 978 | Best AUC, positive against plain |
|---|---|---|---|---|---|
| Base: single-color component, 4 cells, 4 images, same pair, new pose | 0 | 0 | 1 | 45 | .477 |
| Any task pose, at least 3 poses | 1 | 0 | 0 | 42 | .530 (.474 to .636) |
| Tight window | 3 | 1 | 1 | 314 | .498 |

In the control, the base form holds on 0 positive tasks and .3% of plain tasks.

First reading: the fact doesn't separate these tasks. The positive rate is at or below the plain rate on most forms. The check of the full form grid, the false hits and the held read are still to come.
