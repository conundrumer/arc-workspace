# Unit 1c: pretraining with the summary objective, the parent bias by assignment, per-example summaries and the binding

## Question

When the hidden row's path to its source summary is given, and that summary holds bound (key, value) pairs that the row reads with its own key, does the hidden row recover its value? This is measured as in units 1 and 1b: the pointer-type remote losses against their per-group chance. The path is given by the parent bias, with the copy that agrees on the DET assignment marked direct. The summary is kept per example and bound by `--enc-bind`.

## Gate before the card is sent

Each item below is done and written here. Until then, the card is not sent.

- The change after round 3 has landed on `enc-bind`. It adds the parent bias by assignment agreement and the per-example K vectors, which the LM reads directly. It drops the DET tag and the DET key codes. It also splits out in the log the hidden fields whose key column is hidden in the same draw.
- Master is merged into `enc-bind`. The loader is at LOADER_VERSION 19.
- An Opus review of the measurement path is done, and its fixes are re-checked. Status: the attention width padding (287caf3e) reviewed, no defect, outputs and gradients equal to rounding on CPU and MPS; the leak fix (716d0300) traced and measured, kept memory 0 bytes a step with the losses unchanged.
- The fixture passes per column, not on the combined ratio. Each Color and Ident lookup column must be below 0.5 of chance with the flag, and over 0.85 without it. The combined ratio can pass while the Colors fail, because the Number's chance loss dominates it (round 3: Colors 0.68 and 0.78, combined 0.38). Result at f3a3508b: every lookup column at 0.00 to 0.28 of its reference with the flag (Color 8 at 0.28, the rest 0.05 or under) and 0.95 to 1.19 without it, all PASS.
- The binding holds the decision bucket's pairs. The fixture's capacity curve, with the keys built from the key columns, gives the per-column ratio at the rows per example slot of the 1-50 bucket and the 51-200 bucket. Those buckets hold a median of 12 and 62 pairs per source table, over 3 to 6 examples. The width of the run is one where the 1-50 bucket's rows per slot are under 0.5 of chance. Curve at round 4, the ratio at 300 steps for the three lookups that are not into a grid: at D 1024 under 0.5 up to 8 rows per slot (16 rows: 0.52, 0.40, 0.44); at D 2048 up to 16 rows (16 rows: 0.26, 0.18, 0.17; 32 rows: 0.50, 0.42, 0.43). The 1-50 bucket holds about 2 to 4 pairs per slot and the 51-200 bucket about 10 to 20, so D 2048 is the width that covers both. At round 5, with keys from the flows, at D 2048: 16 rows 0.01, 0.00, 0.01; 32 rows 0.06, 0.04, 0.03.
- The stored key comes from the columns of the source table that the readers' key columns come from, by their flows. Real tables seldom declare a candidate key, and a key of every column is noise. The fixture has a source table with no declared key. Result at round 5 (0c30ae82), at 8 rows per slot and D 2048: 0.00 of chance in each column with the flag, and 0.95 to 1.00 without it. In a 100-task sample, 20.5% of (hidden remote column, source table) pairs have an empty key set, and the binding cannot serve those. Up to 4 parts per table cover 99.6% of reader pairs.
- On real data, the reader key finds the true value. The preflight's key-hit line gives the share of hidden remote fields whose reader key matches a stored row that holds the true value. At round 5 on dev, with only the field's own column hidden, 22% found one value and it was true, and 52% found the true value among 2 to 5 values. Fields that miss are expected to stay at chance. At round 6 (b68daaf1), the share of hidden remote fields that find a row with the true value: on dev, 0.49 of all and 0.85 of those with a read; on a 100-task sample of full-a58352ed, 0.26 of all and 0.45 of those with a read. Causes on the full sample, as shares of hidden remote fields (round-6 review): a hit 25.7%, of which every matched row is true 9.3%; orientation types, which take no codes, 19.9%; key columns with only computed flows 10.7%; no key column 9.9%; a multi-column key that mixes rule atoms 12.5%; a key that matches only wrong rows 11.2%; a key that matches no row 6.9%; the key fields hidden 2.7%; the cap and the siblings under 1%.
- The key sets keep a rule atom's columns together, from the loader's atom of each flow. The loader keeps the atom from LOADER_VERSION 20 (master ca185716, `FLOW_ATOM`). The DET column correspondence comes at LOADER_VERSION 21, with the full-0f73004c export. Key-hit share after the atom keys, on the 100-task sample: hit 0.341 (was 0.257), exact hit 0.090 (was 0.087); on dev 0.422 (was 0.452). The branch is at loader version 21 (85fbf46f), and lm/checks.sh passes on the new dev export.
- `lm/encoder_check.py --learn` passes whole. Result at round 3 (8810cb39): exit 0, no case failed; the multi-source case by column with the flag Color 0.78, Number 0.17, Color 0.67, and without it 0.90, 0.96, 0.89, so the per-column item above is not met. At round 5 (0c30ae82): exit 0, 94 checks pass, none fail (lm/runs/enc-bind5 on the branch). At round 6 (b68daaf1): exit 0, 99 checks pass, none fail, 420 s, 4.1 GB peak. At b28a9c54, with the parent bias by assignment and per-example pooling: exit 0, 113 checks pass, none fail, 783 s, 3.1 GB peak. At f3a3508b (the model code of 716d0300 plus the keys by read code): 124 checks pass, none fail, the last case cut by the 1,800 s bound after a 10-minute wait for a heavy-command share; again at 52fedc2e: exit 0, 126 checks pass, none fail, 989 s, 4.2 GB peak.
- The binding width `--enc-bind-dim` is 2048, from the capacity curve. The CPU dev step with it took 47 to 55 s, against 19 to 25 s without it. The pod's code check measures the GPU ratio, which sets the bound below.
- The dev learning test (lm/runs/pretrain-bind-dev) stands in for the Mac check: run A, with the binding, on the A100 at 287caf3e, exit 0, 300 steps, 1.39 s a step against 0.91 s for run B without it; the key-hit fields fall 0.7 to 2.1 nats under chance with A and stay at chance with B. A's `device_gb` rose from 4.5 to 44.5 GB over the 300 steps, the leak 716d0300 fixes; B's stayed at 3.8 GB.

## Settings

The unit 1b flags plus `--enc-bind --enc-bind-dim 2048 --enc-per-example`. With these, the parent bias has a fourth type, a source copy whose DET assignment disagrees, which starts at 0. Per-example pooling gives each table K vectors per example and K task-wide; on dev that takes the vectors per program at K 4 from 183 to 487. Data is the pair at master 4663b88a: tables `work/tables/full-4663b88a` (loader version 21, 3,024,222 index rows, 0 check lines) and streams `work/lm/data-full-4663b88a` (6,060 train and 659 held-out streams). Its held-out set is not unit 1b's, so the rule compares within the run. Unit 1b's numbers are context only.

Code: branch `enc-bind` at commit 716d0300 (loader version 21), sent to the pod by `git archive`. The later commits on the branch move to loader version 23, which does not read this export; on the 100-task sample they leave the key-hit share as it is (0.337 of hidden remote fields against 0.341).

The pod builds the tables cache itself, as the first step of the run. At loader version 21 the build of this export reached a 24.5 GB peak footprint on the Mac, more than the Mac's 24 GB, so it does not run there. A pod build was slow once, unexplained; the cache build's time is written into the run's log, and a build past 1,800 s stops the unit.

    OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 python -u lm/pretrain.py \
      --data work/lm/data-full-4663b88a --tables work/tables/full-4663b88a \
      --out runs/pretrain-bind-1 --steps 800 --programs 4 --step-rows 450000 \
      --eval-every 250 --eval-limit 64 --mask-remote-groups --enc-ptr-equality --enc-parent-bias 4 \
      --enc-bind --enc-bind-dim 2048 --enc-per-example --device cuda

## Steps on the pod

1. Code check: the 2-step pretrain on work/tables/dev-v21 with the run's flags, the command run on the Mac above with `--device cuda`, bound 600 s. Conditions:
   - exit 0;
   - the binding weights' gradient norm after step 2 is not 0 (after step 1 it is 0: `ptr_bind` starts at zero, so no gradient reaches the binding until it moves);
   - `parent_bias` at step 2 differs from its start for the direct type (the disagree type moves only on a program with a disagreeing source copy, which 2 steps may not draw; in the dev run A it had moved by step 25);
   - `device_gb` and s/step are written down against unit 1b's code check (2.08 GB, 1.28 s a step).
   The memory per row is an estimate from shapes, about 6 KB at D 1024. The code check evaluates only at its last step, like unit 1b's. If its `device_gb` is over 1.5 times unit 1b's, the run takes `--step-rows` 450,000 × 1.5 over that ratio, rounded down to 10,000, so the step fits 80 GB. Any failed condition stops the unit.
2. The run. Its `device_gb` must stay level from the step-250 evaluation on; a peak that keeps rising means memory kept across steps, and the run is stopped. The bound is unit 1b's 4,115 s times the code check's s/step ratio to unit 1b's, plus 900 s, and not under 6,000 s. With the dev ratio of A to B, 1.53, that is 4,115 × 1.53 + 900, about 7,200 s, plus up to 1,800 s for the pod's cache build: 9,000 s.

## Expected, from unit 1b's log

| phase | unit 1b measured | expected here |
| --- | --- | --- |
| cache load from the volume | 1,187 s | built on the pod, up to 1,800 s |
| preflight | 976 s | about 1,000 s |
| step | 2.2–2.4 s | unit 1b's times the dev ratio of 1.53: 3.4–3.7 s |
| evaluation of 64 programs | about 180 s | 180 s times that ratio, 4 times |
| device memory | 48–60 GB | unit 1b's times the code check's memory ratio, under 80 GB; the code check's ratio decides, since the dev runs give no clean figure with the binding |
| whole run | 4,115 s | from the bound above |

## Decision rule, fixed before the run

Read at the step-750 evaluation, the last the bound guarantees, or at step 800 if it completes. The rule reads Color and Ident `row_target` in buckets 1-50 and 51-200: `group_loss` against `group_chance_loss`. It reads the `row_target` fields whose binding key hits a row that holds the true value, by the log's key-hit split. The fields whose key column is hidden in the same draw, and the fields whose key misses or that have no read, are read apart and do not decide. On the full data the key hits for about a quarter of hidden remote fields, and every matched row is true for about a tenth, so the loss over all fields would hide a gain on those. The `key_hit_exact` part is read beside the hits, as the case where the read gives one value. On the `key_hit` kinds the binding already limits a read to the row's own example, so those kinds measure the binding. A gain from per-example pooling would show in `key_miss`, `no_read` and `key_hidden`, which are read as context only. On dev, the row targets by kind were: Color 1,031 exact, 1,848 inexact, 255 key hidden, 130 miss, 5 no read; Ident 87 exact, 520 inexact, 82 key hidden, 9 miss, 102 no read. The attention on the agreeing source copy, against recent non-source tables, checks that the bias is in effect. The direct `parent_bias` shows whether training kept the path.

| pointer losses, small sources, key hits | reading | next |
| --- | --- | --- |
| at least 0.1 nats below chance in the 1-50 bucket for both types | the bound summaries hold the pairs, and the row reads them | unit 2, the comparison, with these flags |
| below chance in 1-50 for one type only | the binding works for one key type | design: inspect which keys fail; no run until that inspection says what to change |
| at chance in both (within 0.03), bias kept | the lookup is not learned at full scale | design: run the fixture at the full data's pairs per summary on the Mac before any run |
| at chance, bias driven toward 0 | the model rejects the given path | design: inspect what the summaries hold |
| above chance, as in unit 1b | no change | design |

The 201-1000 bucket is read but does not decide. Its summaries hold about 210 pairs. The fields whose key does not determine the value, 39% of hidden remote fields by rows in a 100-task sample, need a second lookup and are not expected to move.

## Caveats

- Unit 1's caveat stands: a remote value may be recomputable from the grid rows two levels down.
- The binding width and the memory per row are set from the Mac and the fixture. Only the pod's code check measures them at CUDA scale.

## Result

Code `enc-bind` at 716d0300, loader version 21, data pair full-4663b88a, the flags of the command above with `--step-rows 390000`. The code check's device memory ratio of 1.716 over unit 1b's scaled `--step-rows` down from 450,000. The reading is at step 750.

- Run:
    - A100 SXM, 800 steps of 4 programs, exit 0, 2 h 12 min from 15:22:09 to 17:34:34 UTC, under the bound of 10,131 s;
    - cache build on the pod: 24.5 min (15:23:44 to 15:48:15);
    - preflight: 1,265 s, ending at 16:28:44;
    - 5,965 training programs, 64 held-out programs, 165 left out over `--step-rows`;
    - 4.53 s a step (3,886 s at step 800, with four evaluations of about 65 s each), against 2.31 s in the code check;
    - `device_gb` 55.5 at all four evaluations, so level from step 250;
    - cost about $4.4.
- Decision figures at step 750, held-out, group means, loss / chance, with the number of groups:
    - exact hits, 1-50: Color 0.03 / 1.41 (153), Ident 0.12 / 1.92 (258);
    - exact hits, 51-200: Color 0.48 / 1.60 (68), Ident 0.16 / 1.51 (157);
    - inexact hits, 1-50: Color 6.55 / 1.66 (28), Ident 1.16 / 2.87 (46);
    - inexact hits, 51-200: Color 0.99 / 1.61, Ident 0.56 / 1.61;
    - key misses: Color 4.66 / 2.18 (123) in 1-50 and 4.80 / 1.43 (17) in 51-200;
    - all `row_target` fields, 1-50: Color 1.82 / 1.51, Ident 0.50 / 2.00;
    - all `row_target` fields, 51-200: Color 1.32 / 1.59, Ident 1.44 / 2.27.
- Step 800 is worse than step 750 on the four exact-hit entries (1-50: Color 0.22, Ident 0.48).
- Bias and attention at step 750: the direct `parent_bias` is 4.02 in both layers, and the three other types are within 0.08 of 0. Parent attention is 0.209 on the agreeing source copy, 0.039 on as many recent tables, 0.046 chance; on the disagreeing copy it is 0.017.
- The remote loss over all types is 2.57 / 4.61 per group, over 25,449 groups. This log predates the `freq_loss` and `nb_loss` baselines, so it is read against chance only.
- Reading, by the table above:
    - the exact-hit fields of both types in the 1-50 bucket are over a nat below chance, so the bound summaries hold the pairs and the row reads them (the first row);
    - where the key matches several rows (inexact hit) or misses, Color is far above chance: the model answers with confidence from a wrong row, so over all Color row targets in 1-50 the loss is above chance (1.82 against 1.51);
    - the binding's gain is on the exact hits alone.
- The next step in the table, unit 2 the comparison, is superseded: the encoder's token is now trained and measured as a clue at decode branch points (viable, relevant, what next), on the branch-point data of alt-lead with negatives, and not on the masked loss.
- Record files in this directory: `log.jsonl`, `pretrain-bind-1.out`, `pretrain-bind-1.rc`, `build.txt`, `status.txt`, `pod-parameters.txt`, `codecheck/` and `codecheck2/`. `encoder.pt` is on the pod volume at `/workspace/bind1/runs/pretrain-bind-1/encoder.pt` and is not in the repo.
