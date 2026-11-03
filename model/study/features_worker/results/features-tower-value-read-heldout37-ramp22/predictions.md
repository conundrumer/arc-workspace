# Predictions

Written before any fit or any read of a score against a label. Data was only listed and opened to learn its format.

## AUC on the read set (bundle arm of round 1, node label: a later cover reads the node, directly or through descendants, or is it)

| Score | Median per-run AUC, 37 | Median per-run AUC, ramp | Range I expect for the 37 |
| --- | --- | --- | --- |
| Fit value (boosted trees on T facts and tower facts) | 0.74 | 0.74 | 0.66 to 0.82 |
| Shipped node score (hand model) | 0.66 | 0.66 | 0.58 to 0.75 |
| Depth-only control (boosted trees on depth) | 0.58 | 0.58 | 0.50 to 0.65 |

- The pooled AUC is within 0.03 of the median per-run AUC for each score.
- Value minus node score: +0.07, with a 95% interval by task that I expect to exclude 0 on the 37 and not to exclude it on the ramp (22 tasks, few covers).
- Value minus depth-only: +0.15.
- Ranks of positive nodes at each cover's time: the value puts the median positive node above the median rank of the node score, by a factor of about 1.5 in rank; top 10 and top 100 shares are higher for the value, with the largest relative gain at top 100.
- On nodes with exposure of 1 or more, every AUC falls toward 0.5 by 0.03 to 0.08, because the nodes no scope held are mostly easy negatives (deep, late nodes).

## Reasons, in short

- Positives are the ancestors of covers, so they skew to shallow nodes with common column types, which the T facts and the tower facts see.
- The node score was fit on a node label for a cover of the node's own table, and does not see tower facts. Its AUC on a tower label is lower.
- The fit set is 50 tasks at one seed; the fit may carry task-specific facts that do not transfer, which is why I expect the value to stay under 0.80.
