# Prediction: rank model for right intermediates

Written before any design or fit, by the coordinator, on 2026-11-01 at about 16:05 EST.

Read: a rank model fit on pool records of training tasks, with the label "is an intermediate of the right program", on DAG-invariant features, read on the 13 hour runs and the 37 at 600 s against the hand score.

1. Rank of the reads of ready forms on the hour runs, median, hand score about 4,500 of 14,700: the model gives 900 to 2,500. It doesn't reach the top 100 at the median.
2. Chance per opening for those reads, median, hand score .0003: the model gives .001 to .004, a gain of 3 to 13 times. It stays under .01.
3. Share of those reads in the top 100: under 25%.
4. On the 37 at 600 s, the gain is smaller than on the hour runs in rank share terms, since pools are small.
5. Most of the gain comes from the table against the task's pairs and test input, and form shape adds little over depth. A control with labels shuffled by task gives 0.
6. The bar of about rank 10 at the median isn't met.
