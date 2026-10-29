# Unit 1b: pretraining with the summary objective and the parent bias

## Question

With the path from a hidden row to its source tables' pooled vectors given (`--enc-parent-bias`), do those vectors
carry usable content? Measured by the pointer-type remote losses against their per-group chance, as in unit 1.

## Settings

The unit 1 flags plus `--enc-parent-bias 4`. Data: the pair at master 5529bd39 (tables full-5529bd39, streams
data-full-5529bd39), exported together after changes 20-177, 20-179 and 20-181, with no known mismatch: 6,872
cases in the tables, 6,538 streams (5,938 train, 600 held-out) against unit 1's 6,394, so the held-out set is not
unit 1's; the decision rule compares within the run. The cache is built on
the Mac (about 440 s, 7.5 GB resident) and copied with the tables dir, mtimes preserved.

    OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 python -u lm/pretrain.py \
      --data work/lm/data-full-5529bd39 --tables work/tables/full-5529bd39 \
      --out runs/pretrain-parent-1 --steps 800 --programs 4 --step-rows 450000 \
      --eval-every 250 --eval-limit 64 --mask-remote-groups --enc-ptr-equality --enc-parent-bias 4 --device cuda

Mac check before sending (the Practice rule): each command below run on work/tables/dev with --device cpu, exit status
written here: the 2-step code check of step 1 with --device cpu, exit 0, 34 s a step on 14 threads; parent_bias at step 2 [3.99991, 3.99988] direct, 7e-5 / -7e-5 ancestor, 1e-4 unrelated; matched_parent 0.678, matched_recent_nondirect 0.020. Code at master f895184f.

## Steps on the pod

1. Code check: the 2-step pretrain on work/tables/dev with the run's flags and --device cuda, bound 600 s. Conditions:
   exit 0; in the step-2 held-out record `parent_bias` differs from [4, 0, 0] (the bias gets a gradient on the CUDA
   kernel); `device_gb` and the step time near unit 1's code check (pretrain-remote-1-codecheck.out). A failed
   condition stops the unit.
2. The run, bound 6,000 s.

## Expected, from unit 1's log (not from memory)

| phase | unit 1 measured | expected here |
| --- | --- | --- |
| cache load from the volume | 1,106 s | 1,100 s |
| preflight | 909 s | 900 s |
| step | 2.2–2.3 s | 2.3 s; 800 steps 1,850 s |
| evaluation of 64 programs | about 180 s | 180 s × 4 |
| device memory | 60–61 GB | 61 GB |
| to the step-750 evaluation | | about 4,300 s |
| whole run | | about 4,600 s; bound 6,000 s |

## Decision rule, fixed before the run

Read at the step-750 evaluation (the last the bound guarantees; step 800 if it completes), on Color and Ident
`row_target` in buckets 1-50 and 51-200, `group_loss` against `group_chance_loss`. `matched_parent` is read only as a
check that the bias is in effect (it was 0.064 in unit 1 and 0.67 at initialization on the dev export);
`matched_recent_nondirect` is the recency control. `parent_bias` per layer shows whether training kept, raised or
removed the given path.

| pointer losses, small sources | parent_bias direct | reading | next |
| --- | --- | --- | --- |
| at least 0.1 nats below chance | kept or raised | the summaries carry usable content, and the given path is used | unit 2, the comparison, with the bias |
| at chance (within 0.03) | kept | the summary is found and holds nothing usable: the binding question | design; no training run |
| at chance | driven toward 0 | the model rejects the given path: the pooled vectors hurt the within-table prediction | design; inspect what the pooled vectors hold |
| below chance | driven toward 0 | the drop is not the summary | the control run with the pooled vectors hidden |

## Caveats

- Unit 1's caveats stand: a remote value may be recomputable from the grid rows two levels down; the control run
  separates that.
- The labels rest on full-5529bd39's flows, which engine-worker's checks pass over all 6,872 cases.
