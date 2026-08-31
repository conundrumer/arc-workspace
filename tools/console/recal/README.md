# Callout rate recalibration

This pipeline re-measures the engagement counts behind `CALLOUT_RATES` in
`tools/console/solver_console/prompts.py`. The checkpoint is
`labels.json`: one record per classified pair, timestamped, so a rerun
classifies only pairs the store has not seen. Transcripts age out of the
Claude store, so the labels here are the durable record of past
measurements.

The extraction scripts write large intermediate JSONs next to themselves.
Copy `extract.py` and `pool.py` to a scratch location and run them there;
`checkpoint.py` runs here, against the store.

## Procedure

1. `python3 extract.py` — scans the Claude transcript store for solver
   sessions and pulls every user comment with its preceding assistant
   message. Writes `corpus.json`.
2. `python3 pool.py` — filters to eligible pairs (drops junk, duplicates,
   bare workflow triggers), tags them for stratification, and samples.
   Writes `_pool.json` and `_sample.json`. For a checkpointed rerun the
   old eras are already labeled, so the sampling quotas only matter for
   pairs newer than the store.
3. `python3 checkpoint.py todo _sample.json todo.json` — the sample rows
   not yet in the store. Only these get classified.
4. Classify `todo.json` in subagent batches of ~25 pairs. Each batch
   prompt carries `RUBRIC.md` in full and writes `batches/out_<n>.json`.
   Before this step, refresh the kind descriptions in `RUBRIC.md` from
   `CALLOUT_RATES` — they must match verbatim. A description change
   invalidates the store: bump `RUBRIC_DATE` in `checkpoint.py` and
   re-classify everything (`counts` refuses a store with mixed rubric
   dates).
5. `python3 checkpoint.py merge _sample.json batches/` — folds the new
   labels into `labels.json`.
6. `python3 checkpoint.py counts <era-cut>` — era-split per-kind counts
   from the whole store. Eras derive from timestamps at this step, so
   pick the cut per run: typically old = everything up to the previous
   measurement, new = since.
7. Put the counts into `CALLOUT_RATES` as `(picked_old, raised_old,
   picked_new, raised_new)` per kind, and update the era-cut date in the
   comment above it. Then sanity-check the band cuts: for each band, sum
   the weighted raised counts of its kinds and check the share of total
   volume — a P1 band holding half the volume is what a miscalibrated
   cut looks like.

## Choices a rerun should keep

- A pair is one comment plus its preceding assistant message; `picked`
  credits engagement in the comment or the next five user messages.
- Counting is per raised item: a message raising two items of one kind
  contributes 2 to that kind's `raised`.
- Items outside every description go to `other`, which is measured but not
  published in the table.
- The stratification taxonomy in `pool.py` only shapes the sample; it
  plays no role in classification.

## Known limitations

- The corpus measures engagement with discrete report items generally, not
  callout sections specifically; almost no pairs have a literal
  `## Callouts` heading.
- Byte-identical assistant messages (retries) can enter the sample twice.
- `picked` measures attention, not agreement or action.
