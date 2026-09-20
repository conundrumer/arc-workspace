# Callout rate recalibration
- This pipeline re-measures the engagement counts behind `CALLOUT_RATES` in `tools/console/solver_console/prompts.py`.
- The checkpoint is `labels.json`: one record per classified pair, timestamped, so a rerun classifies only pairs the store has not seen.
- Transcripts age out of the store, so a rerun sees fewer old pairs than the run before it; the checkpoint is what keeps the old counts.

* comment: when editing this doc
    - State the procedure as numbered steps, since a rerun follows them in order.
    - Keep a choice under Choices a rerun should keep only while a rerun could reasonably go the other way.

## Procedure
1. `python3 extract.py` scans the Claude transcript store for solver sessions and pulls every user comment with its preceding assistant message. It writes `corpus.json`.
2. `python3 pool.py` filters to eligible pairs, dropping junk, duplicates, and bare workflow triggers, tags them for stratification, and samples. It writes `_pool.json` and `_sample.json`.
    - For a checkpointed rerun the old eras are already labeled, so the sampling quotas only matter for pairs newer than the store.
3. `python3 checkpoint.py todo _sample.json todo.json` gives the sample rows not yet in the store. Only these get classified.
4. Classify `todo.json` in subagent batches of about 25 pairs. Each batch prompt carries [Classification rubric](tools/console/recal/RUBRIC.md) in full and writes `batches/out_<n>.json`.
    - Before this step, refresh the kind descriptions in the rubric from `CALLOUT_RATES`. They match verbatim.
    - A description change invalidates the store: bump `RUBRIC_DATE` in `checkpoint.py` and re-classify everything. `counts` refuses a store with mixed rubric dates.
5. `python3 checkpoint.py merge _sample.json batches/` folds the new labels into `labels.json`.
6. `python3 checkpoint.py counts <era-cut>` gives era-split per-kind counts from the whole store.
    - Eras derive from timestamps at this step, so pick the cut per run: typically old is everything up to the previous measurement, and new is since.
7. Put the counts into `CALLOUT_RATES` as `(picked_old, raised_old, picked_new, raised_new)` per kind, and update the era-cut date in the comment above it.
8. Sanity-check the band cuts: for each band, sum the weighted raised counts of its kinds and check the share of total volume.
    - A P1 band holding half the volume is what a miscalibrated cut looks like.

## Choices a rerun should keep
- A pair is one comment plus its preceding assistant message, and `picked` credits engagement in the comment or the next five user messages.
- Counting is per raised item: a message raising two items of one kind contributes 2 to that kind's `raised`.
- Items outside every description go to `other`, which is measured and left out of the published table.
- The stratification taxonomy in `pool.py` shapes the sample alone, and plays no role in classification.

## Known limitations
- The corpus measures engagement with discrete report items generally, and not callout sections specifically. Almost no pairs carry a literal `## Callouts` heading.
- Byte-identical assistant messages, from a retry, can enter the sample twice.
- `picked` measures attention, and not agreement or action.
