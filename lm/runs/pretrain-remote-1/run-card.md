# Unit 1: pretraining with the summary objective

## Question

Do the K-vector summaries of earlier tables carry table contents, once a hidden remote field can be answered only
from them? Measured by the remote loss by source-table size against its chance level, and by where a hidden
row's attention over the earlier tables' pooled vectors lands.

## Settings

The pretrain-full-3 flags (default shape: 2 layers, width 32, 4 heads, feed-forward 2, K 4, 2.83M parameters)
plus the two new flags.

    OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 python -u lm/pretrain.py \
      --data work/lm/data-full-2a25e0c3 --tables work/tables/full-2a25e0c3 \
      --out runs/pretrain-remote-1 --steps 800 --programs 4 --step-rows 450000 \
      --eval-every 250 --eval-limit 64 --mask-remote-groups --enc-ptr-equality --device cuda

On a fresh A100 SXM 80GB pod on the arclm-data volume, threads at min(vCPU, 16), output to
runs/pretrain-remote-1.out, time bound 3,600 s. The data pair is new: `work/lm/data-full-2a25e0c3` (streams, 7.7 MB, with
the loader cache `tables.pkl` built on the Mac) and `work/tables/full-2a25e0c3` (tables, 12.8 GB) must be copied to the
volume before the run; the afc44b43 pair on the volume is superseded. The export's `checks.txt` is empty and the
standalone export check finds 0 violations, so the loader builds and loads under its strict default. The pod's first command, before the run: the cuda code check
(lm/checks.sh is CPU-only; run the 2-step pretrain code check with --device cuda on the dev export), then the
preflight on the full export with the flag, which the builder could not run on the Mac.

## Expected

| item | last measured (pretrain-full-3/-4) | expected here |
| --- | --- | --- |
| preflight | 60 s | several minutes: key groups cost an np.unique per remote column (the count took 300 s) |
| load | 142 s | 142 s once the cache is on the volume; a build on the pod is the Mac's build time |
| step | 1.2–1.9 s at 16 threads; 2.7 s at 32 threads | about 2 s; 800 steps about 27 min |
| evaluation of 64 programs | 68 s | about 70 s, ×4 |
| device memory | 28.7 GB | about 29 GB (hidden fields per table still bounded by --mask-cap 512) |
| whole run | 2,450 s for 750 steps | about 40 min; bound 3,600 s |

## What the log must show

1. The preflight's second line: hidden remote fields by type over one draw per program, and the share of Color
   and Ident fields whose target is "no row holds it". A refusal here means the flag hides nothing on this data.
2. At each evaluation, `by_source_rows` with buckets 1-50, 51-200, 201-1000, 1001-4000, each with loss,
   chance_loss, accuracy and fields; and `parent_attention` with layers, mean, chance and fields.
3. The class heads still learn as before (Box and Number well below ln 320 and ln 1088), so the change broke
   nothing on the within-table path.

## Decision rule, fixed before the run

Read at the final evaluation (step 750), on the remote fields of the pointer types Color and Ident in the
`row_target` split (a visible row holds the value, and no row of another entry with the same key values holds
it), in the buckets 1-50 and 51-200: `group_loss` against `group_chance_loss`, both per-group means. Fields
whose target is "no row holds it" are excluded, since a row whose whole entry column is hidden can answer "no
row" from the mask pattern alone; fields with a same-key row in another entry (`row_target_cross_entry`) are
excluded, since the pointer's equality term finds that row with no summary. Parent attention is read as
`matched_parent` against `matched_recent`, the shares over the same fields on the source tables and on as many
of the most recent non-source tables, not against the uniform `chance`.

| remote loss, row-target Color and Ident, small sources | parent attention against `recent` | reading | next |
| --- | --- | --- | --- |
| at least 0.1 nats below chance | above by a clear margin | the summaries carry aggregate content (which values a source column holds, how many rows) and are found; a lookup of one row's value is not expected at K = 4 | unit 2, the comparison |
| at chance (within 0.03) | at or below | the row does not find the source summary | the parent bias is the next change |
| at chance | above | the summary is found and holds nothing usable: the binding question | no training run; design |
| below chance | at or below | the drop is a prior over values, not the summary | a control run with the pooled vectors hidden from the row, before unit 2 |

The pointer types alone decide, since a class head's chance level (uniform over 320 boxes or 1,088 numbers) is
loose: a prior over common values gets below it without any summary.

## Caveats that stay

- A remote value may be recomputable from the grid rows, two derivation levels down, since the grids stay in
  view. A loss drop with parent attention at `recent` would be read as a prior, and this route falls in the same
  row of the table. The control run named there separates the two.
- The per-field mean is kept beside the per-group mean; a difference between them shows the large groups.

## Fixes landing before the run (from the review of c13530b4)

- Hiding seeds drawn per key group, not per field.
- The remote loss split by (bucket × type) and, for pointer types, by target kind; per-group mean beside per-field.
- Remote fields labelled apart in `by_type` and `by_depth`.
- `--mask-remote-groups` with `--enc-source-rows` refused.
- `recent` beside `chance` in `parent_attention`.
- The preflight refuses when no pointer-type remote field with a row target would be hidden.
- The flows of full-2a25e0c3 are incomplete (engine-worker's verdict against full-c4ee5c2f): the IF test atoms of 107
  tasks and the key-field sites of keyed inputs in 5 tasks are missing as sources, and 61 lib-copy rows in 4 tasks are
  spurious. No flow has a wrong type or wrong values. A column with a missing source may carry a wrong label (remote
  where a same-table source is missing, or a key group over too few columns), so the remote loss of this run is read
  as an estimate on those tasks. The next export after bug 20-178 is the one unit 2 uses.
