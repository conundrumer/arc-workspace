# Relation steer within groups: S under the recorded scope

`REC` is `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22`.

## The change

At each atom start where the relation steer applies (`sample2_col.py` 2428-2430), the options split into D (KIND `relation`, `rel_name` `declared`) and B (all other options, NOT among them). For each group G of two or more options, with `r_o` the factor that `rel_factors` gives:

`ws'[o] = T_G * ws[o] * r_o / sum_{j in G} ws[j] * r_j`, where `T_G = sum_{j in G} ws[j]` before the steer multiply.

`alt` gets the same change with its own totals. A group of one option keeps its weight. `split-steer/job2.py` makes this change as a monkeypatch: `rel_factors` gives the kit factors of 1 and keeps its own, and `GuidedDrawer.pick_complete` regroups the weights. `--b-unsteered` leaves B unsteered. S is `or_q.walk` summed over orders, as `job.py` walks it.

## Check: switch off

With the switch off, S equals the recorded S on all 82 forms: 39 C and 43 covered. With the switch on, every walk is valid and every order sum is exact.

## Results

The bits saved a form are S_today − S_new: medians with a 95% task bootstrap (2000 resamples, `default_rng(0)`).

| set | forms (tasks) | total saved: median [CI], sum | read-atom picks: median [CI], sum | builtin picks: median [CI], sum | chance per try, median |
|---|---|---|---|---|---|
| C | 39 (15) | 0.00 [0.00, 0.08], +5.6 | 0.00 [-0.01, 0.00], -0.7 | 0.00 [0.00, 0.00], +2.9 | 1.00 |
| covered | 43 (19) | -0.13 [-0.24, 0.00], -12.1 | 0.00 [-0.01, 0.00], -2.0 | 0.00 [-0.23, 0.00], -8.2 | 0.91 |

The S − DB gap that stays:

| set | forms with DB | median S_today − DB | median S_new − DB | share that stays | per-form share that stays, median |
|---|---|---|---|---|---|
| C | 38 | 3.91 | 4.13 | 1.06 | 1.00 |
| covered | 37 | 2.61 | 2.61 | 1.00 | 1.00 |

- C: 2 forms gain 1 bit or more (`db695cfb g2`, both seeds: +2.64 and +2.10), and 1 form loses 1 bit or more (`abc82100 g12`, −2.23, all at read-atom picks).
- Covered: no form gains 1 bit, and 6 forms lose 1 bit or more.
- Forms whose picks all lie in INIT bodies have a delta of exactly 0: an INIT body has no relation steer (`rel_off`), so its factors are 1.

`forms.tsv` has the per-form rows: set, arm, task, g, S_today, S_new, delta, the deltas at read-atom and builtin picks, the chance factor 2^(S_today − S_new), DB, and the gap before and after. `summary.json` has the summary and the checks.

## Why the change saves little

These are facts from the earlier pick logs (`../cause/read.md`, one order per form):

- At builtin picks, P's derived total is the same in S and in R: 0.567 against 0.572 (C). The change keeps P's split between D and B, so a builtin in S keeps about P's 0.43 of the mass for all of B. Today the steer gives S's derived options 0.61 together, and that is close to P's split already.
- At read-atom picks, the gold relation's weight among the derived options is 0.57 bits above an even split with the steer, and 0.08 bits above it under P. The change keeps the steer's ranking within D, so the gold relation keeps about 1 / (count of derived options) of D's mass.
- R's advantage at builtin picks is that the steer moves mass from D to B: the lone derived option falls from P's 0.57 to 0.05. The change takes that move away.

## Not run

`dd6b8c4b g14` (C, both seeds) and `f560132c g10` (C, seed 0) are not in the tables. Each S walk of these forms is long: the recorded `job.py` row of `dd6b8c4b g14` took 25 s with R included, and `f560132c g10` took 616 s, where `or_q.walk` stops an order sum at 300 s. The commands are streaming and resumable, one per shard, and each does only the forms left in its shard:

```
bash REC/env.sh split-steer/job2.py --set C --shard 0/2    # f560132c g10: two S walks, about 10 to 20 min
bash REC/env.sh split-steer/job2.py --set C --shard 1/2    # dd6b8c4b g14, both seeds: four S walks, about 2 min
/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 /Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python REC/split-steer/read2.py    # seconds
```
