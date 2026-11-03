# Measurement: seed-to-seed noise of solve counts, and the test size it implies

No new search run. Every count comes from fields that the runs wrote. The script `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/solve-noise-test-size/solves.py` opens those fields and prints the tables of Part A. It opens no test output.

Paths below that start with `sampler/` or `features-worker/` are under `/Users/davidlu/code/arc-workspace/work/lm/data-study/`.

## Part A: the solve counts

### Judges

- Solves: tasks with at least one candidate that solves every test input (`work/measures.md` "True positive" line 230, "Test accuracy" line 402). The count is of tasks.
- Solves or has a candidate: tasks with a candidate that solves, or with any candidate (`work/measures.md` "Candidate program" line 222). A candidate that solves is a candidate, so this is the count of tasks with at least one candidate.

### Fields

- Worker path (search-worker and sampler-worker pool runs): `<arm>/<task>/supervisor.log`, last line `task <task> lives L candidates C done`. C > 0 gives "solves or has a candidate". These runs write no field for solves. Their `submission.json` holds the attempts, and a count of solves needs the test outputs, so it is not given here.
- Direct path (R120, S120): `<out>/<task>.done.json`, fields `candidates` and `right`. `right` > 0 gives "solves"; `candidates` > 0 gives "solves or has a candidate".
- `sampler/sampler-worker/sampler-pool-fold-seeds-600s/read-fresh.txt`: the `right [...]` lists that the run's own `read_fresh.py` wrote, section `== fold 22`.
- `work/results.md`: where a run wrote no field, the count of solves is the one in its results entry, cited by line.

### Where each named run is

| Name | Run folder | Arms | Budget | Tasks | Source of the name |
|---|---|---|---|---|---|
| R120 | `sampler/sampler-worker/sampler-cover-clauses-train-120s-c87cf482a/out` and `.../sampler-cover-clauses-train20-120s-c87cf482a/out` | one, seed 0 | 120 s | 991 + 20 | `work/lm/data-study/gold/gold-v3-combined-cut/cover-harvest/design.md` line 10; manifest field `budget` |
| S120 | `features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search` | one; `--seed-level 1`, which seeds gold nodes to one third of depth (manifest field `training_eligible`) | 120 s | 930 started, 899 with `done.json` | same design.md line 9; manifest fields `command`, `no_done_json` |
| N600 | `sampler/sampler-worker/sampler-pool-dag-nodes-train50-600s/out/nodes_s0` | one, `nodes_s0`, seed base 0 | 600 s | 50 | `features-worker/results/features-node-score-refit-loop/common2.py` line 37 (`SETS['n600']`); manifest field `what`: "one seed" |
| Ramp 22, round 1 | `sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out` | `bundle_s0`, `bundle_s1` (control), `refit_s0`, `refit_s1` (lever) | 600 s | 22 ramp fold + 37 held-out | given in the brief |
| The ramp's test runs | not found as a run name | | | | see below |

"The ramp's test runs": no file I searched uses that name, and I can't tell which runs it means. The runs below are every run on the ramp fold whose count of solves I found written. I give them as found, and I don't claim that they are the runs the name means.

- `sampler/sampler-worker/sampler-pool-refit-ext-ramp-600s`, arms `ext_s0`, `ext_s1`, 59 tasks, 600 s (`work/results.md` lines 1235, 1246 to 1265).
- `sampler/sampler-worker/sampler-pool-cover-fold-600s`, arms `coverf_s0`, `coverf_s1`, 22 fold tasks, 600 s (`work/results.md` line 1876).
- `sampler/sampler-worker/sampler-pool-fold-seeds-600s`, arms `fresh_2000` to `fresh_5000`, 22 fold tasks, 600 s, the same priors as `coverf` (manifest field `arm`: `models-coverf`; `work/results.md` line 1857).
- `sampler/sampler-worker/sampler-pool-fold-hour-3600s`, arms `hour_s0`, `hour_s1`, 13 easy fold tasks, 3,600 s (`work/results.md` lines 1857, 1865, 1866).
- Eight ramp soaks, `kernel-soak-<code>-linux-ramp59-2400s`, 59 tasks, about 1,200 s per task, one seed each, each on different code (`work/results.md` lines 3507 to 3709).

I added one run that the brief doesn't name: `sampler/search-worker/runs/search-pass-r1-heldout37-ramp22-2seeds-600s-0729e4943`, arms `bundle_s0`, `bundle_s1`, `pass_s0`, `pass_s1`. `work/measures.md` line 348 counts its bundle arms with those of round 1 as the control runs of one code ("round 1 and first-pass bundle controls, 6 pairs"), so its bundle arms give rerun pairs.

Task sets: ramp fold is `sampler/sampler-worker/held/ramp-fold.txt` (22 tasks); the 37 are `sampler/sampler-worker/held/tasks.txt` (37 tasks); training is every other task.

### Per run, per seed: the ramp fold (22 tasks)

| Run, arm | Budget | Tasks | Solves or has a candidate | Solves | Source |
|---|---|---|---|---|---|
| round 1, `bundle_s0` | 600 s | 22 | 2: 74dd1130, c35c1b4c | not written | supervisor.log `candidates` |
| round 1, `bundle_s1` | 600 s | 22 | 0 | not written | same |
| round 1, `refit_s0` | 600 s | 22 | 0 | not written | same |
| round 1, `refit_s1` | 600 s | 22 | 1: 74dd1130 | not written | same |
| first pass, `bundle_s0` | 600 s | 22 | 0 | not written | same |
| first pass, `bundle_s1` | 600 s | 22 | 1: 74dd1130 | not written | same |
| first pass, `pass_s0` | 600 s | 22 | 1: 74dd1130 | not written | same |
| first pass, `pass_s1` | 600 s | 22 | 0 | not written | same |
| `ext_s0` (seed 0) | 600 s | 22 | 0 | 0 | supervisor.log; `work/results.md` line 1250 |
| `ext_s1` (seed 1000) | 600 s | 22 | 1: 74dd1130 | 1: 74dd1130 | supervisor.log; `work/results.md` lines 1250, 1265 |
| `coverf_s0` | 600 s | 22 | 0 | 0 | supervisor.log; read-fresh.txt |
| `coverf_s1` | 600 s | 22 | 0 | 0 | same |
| `fresh_2000` | 600 s | 22 | 1: d23f8c26 | 0 | same; `work/results.md` line 1870 (wrong on test) |
| `fresh_3000` | 600 s | 22 | 0 | 0 | same |
| `fresh_4000` | 600 s | 22 | 0 | 0 | same |
| `fresh_5000` | 600 s | 22 | 0 | 0 | same |
| `hour_s0` | 3,600 s | 13 | 2: 74dd1130, d23f8c26 | 2: 74dd1130, d23f8c26 | same |
| `hour_s1` | 3,600 s | 13 | 1: 74dd1130 | 1: 74dd1130 | same |
| R120 | 120 s | 21 (+1 in train20) | 1: 74dd1130 (train20's task: 0) | 1: 74dd1130 | done.json `candidates`, `right` |
| S120 | 120 s, seeded | 20 | 1: 74dd1130 | 1: 74dd1130 | done.json `candidates`, `right` |

Ramp soaks, 59 tasks, one seed each, solves from `work/results.md`: `0eec50f18` 1 (74dd1130, line 3512); `94d525b92` 0 (line 3543); `cc44bebf3` 0 (line 3566); `2d21a0079` 1 (74dd1130, line 3595); `e8ded5733` 1 (74dd1130, line 3621); `413397046` 0 (line 3647); `ec15d12f0` 1 (74dd1130, line 3671); `8ed4fe634` 1 (74dd1130, line 3695). Each soak has 0 candidates on the 37 (same lines). Candidates on the other fold tasks are not stated in every entry, so "solves or has a candidate" is not given for the soaks.

### Per run, per seed: the 37 held-out tasks

| Run, arm | Budget | Tasks | Solves or has a candidate | Solves |
|---|---|---|---|---|
| round 1, `bundle_s0`, `bundle_s1`, `refit_s0`, `refit_s1` | 600 s | 37 each | 0 each | not written |
| first pass, `bundle_s0`, `bundle_s1`, `pass_s0`, `pass_s1` | 600 s | 37 each | 0 each | not written |
| `ext_s0`, `ext_s1` | 600 s | 37 each | 0 each | 0 each (`work/results.md` lines 1251 to 1263) |

### Per run: training

| Run | Budget | Tasks | Solves or has a candidate | Solves | Source |
|---|---|---|---|---|---|
| R120 | 120 s | 970 + 19 (train20) | 10 + 0 | 8 + 0 | done.json `candidates`, `right` |
| S120 | 120 s, seeded | 879 | 32 | 31 | done.json `candidates`, `right` |
| N600 | 600 s | 50 | 1: fc754716 | not written | supervisor.log `candidates` |

Each training run has one seed, so no training run has a control pair.

### Seed-to-seed spread

A control pair is two runs of the same code that differ only in seed, or a rerun at the same seed. A discordant task is a task that one run of a pair solves and the other doesn't. The difference is the first run's solve count less the second's.

Ramp fold, "solves or has a candidate":

| Pair | Budget | Tasks | Both | Only first | Only second | Neither | Difference |
|---|---|---|---|---|---|---|---|
| round 1 `bundle_s0`, `bundle_s1` | 600 s | 22 | 0 | 2 (74dd1130, c35c1b4c) | 0 | 20 | +2 |
| round 1 `refit_s0`, `refit_s1` | 600 s | 22 | 0 | 0 | 1 (74dd1130) | 21 | -1 |
| first pass `bundle_s0`, `bundle_s1` | 600 s | 22 | 0 | 0 | 1 (74dd1130) | 21 | -1 |
| first pass `pass_s0`, `pass_s1` | 600 s | 22 | 0 | 1 (74dd1130) | 0 | 21 | +1 |
| round 1 `bundle_s0`, first pass `bundle_s0` (rerun) | 600 s | 22 | 0 | 2 (74dd1130, c35c1b4c) | 0 | 20 | +2 |
| round 1 `bundle_s1`, first pass `bundle_s1` (rerun) | 600 s | 22 | 0 | 0 | 1 (74dd1130) | 21 | -1 |
| round 1 `bundle_s0`, first pass `bundle_s1` | 600 s | 22 | 1 (74dd1130) | 1 (c35c1b4c) | 0 | 20 | +1 |
| round 1 `bundle_s1`, first pass `bundle_s0` | 600 s | 22 | 0 | 0 | 0 | 22 | 0 |
| `ext_s0`, `ext_s1` | 600 s | 22 | 0 | 0 | 1 (74dd1130) | 21 | -1 |
| `fresh_2000` against each of `coverf_s0`, `coverf_s1`, `fresh_3000`, `fresh_4000`, `fresh_5000` (5 pairs) | 600 s | 22 | 0 | 1 (d23f8c26, in `fresh_2000`) | 0 | 21 | ±1 |
| the other 10 pairs of `coverf_s0`, `coverf_s1`, `fresh_3000` to `fresh_5000` | 600 s | 22 | 0 | 0 | 0 | 22 | 0 |
| `hour_s0`, `hour_s1` | 3,600 s | 13 | 1 (74dd1130) | 1 (d23f8c26) | 0 | 11 | +1 |

Ramp fold, "solves" (only pairs where both runs have the count):

| Pair | Budget | Tasks | Both | Only first | Only second | Neither | Difference |
|---|---|---|---|---|---|---|---|
| `ext_s0`, `ext_s1` | 600 s | 22 | 0 | 0 | 1 (74dd1130) | 21 | -1 |
| the 15 pairs of `coverf_s0`, `coverf_s1`, `fresh_2000` to `fresh_5000` | 600 s | 22 | 0 | 0 | 0 | 22 | 0 |
| `hour_s0`, `hour_s1` | 3,600 s | 13 | 1 (74dd1130) | 1 (d23f8c26) | 0 | 11 | +1 |

The 37, both judges where written: every pair above that holds the 37 (round 1 and first pass, all 8 pairs; `ext_s0`, `ext_s1`) has 37 tasks solved in neither run, so 0 discordant tasks and a difference of 0.

Largest difference over the control pairs:

| Set | Judge | Largest absolute difference | Pairs | Discordant tasks per pair at 600 s, mean |
|---|---|---|---|---|
| Ramp fold (22) | solves or has a candidate | 2 (round 1 `bundle_s0` against `bundle_s1`; against first pass `bundle_s0`) | 24 at 600 s, 1 at 3,600 s | 15 over 24 pairs = 0.625 |
| Ramp fold (22) | solves | 1 (`ext`; `hour` at 3,600 s on 13 tasks) | 16 at 600 s, 1 at 3,600 s | 1 over 16 pairs = 0.0625 |
| The 37 | solves or has a candidate | 0 | 10 | 0 |
| The 37 | solves | 0 | 1 (`ext`) | 0 |
| Training | either | no control pair | 0 | none |

The 24 pairs at 600 s share runs (4 round-1 and first-pass bundle runs give 6 pairs; 6 `coverf` and `fresh` runs give 15 pairs), so they are not independent.

Pairs of different code, left out as noise: round 1 `bundle` against `refit`; first pass `bundle` against `pass`; `ext` against `extk` and against `coverf`; `hour` against `fresh` and `coverf` (other budget); R120, S120 and N600 against each other (other code, budget and seeding); the eight ramp soaks against each other.

## Part B: test size for solves

Script: `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/solve-noise-test-size/power.py`. It opens no data file; its inputs are the D0 values of Part A.

### Method

A live test runs arm A and arm B on the same N tasks, at s seeds each, and pairs A's seed i with B's seed i. The change Δ is A's solve count less B's, per seed.

- Model, per seed pair, tasks independent: p01 = D0 / 2N is the chance that a task is solved by B only, and p10 = D0 / 2N + Δ / N the chance that it is solved by A only. D0 is the expected count of discordant tasks in a control pair (Part A). The change adds Δ tasks to A's side and leaves the noise as it is.
- Seeds pooled: the s seeds give n = sN paired tasks.
  - Normal formula for the McNemar test (Connor 1987): n = [z_{α/2} √π_d + z_β √(π_d − δ²)]² / δ², with δ = p10 − p01 = Δ / N, π_d = p10 + p01, z_{α/2} = 1.960, z_β = 0.842. Seeds: s = ⌈n / N⌉. In the counts of one seed this is s = [1.960 √(D0 + Δ) + 0.842 √(D0 + Δ − Δ² / N)]² / Δ².
  - Exact: the two-sided binomial sign test on the discordant tasks (b A only, c B only, reject when 2 P(Bin(b + c, ½) ≤ min(b, c)) ≤ .05). Power is summed over the multinomial of (b, c) at n = sN. The table gives the least s with power ≥ .8.
- Seeds as separate replicates: each seed pair gives one sign, of b_i − c_i. The exact two-sided sign test runs over the s signs, with ties dropped. A sign test over s signs can reach p ≤ .05 only at s ≥ 6 (2 × ½⁶ = .031; 2 × ½⁵ = .0625), so this method needs 6 seeds whatever the change. Under the normal approximation the replicate method gives the same s as the pooled formula above, since the variance of b_i − c_i is the count D0 + Δ − Δ² / N.
- Two-sided 95% confidence, 80% power, for every row.

### Assumptions

- Tasks are independent of each other, and seed pairs are independent of each other.
- D0 comes from the 600 s control pairs of Part A: the mean over those pairs, and the largest. The pairs share runs, so they are not independent.
- In the pooled method, a task on seed i and the same task on seed j count as two independent paired units. If the change flips the same Δ tasks on every seed, they aren't independent, and the pooled method overstates the evidence.
- The training runs have no control pair, so no D0 exists for training. The training rows use D0 = 0, which is the least any rate can be. Each training row is a lower bound on the seeds, not an estimate.
- The 37 have D0 = 0 in all 10 pairs, at a base of 0 solves in every run. A D0 of 0 from 10 pairs doesn't show that the rate is 0.

### Seeds per arm

Tasks are the set's task count. Seeds are per arm, so a test runs 2 × tasks × seeds jobs.

| Set | Judge | D0 per pair | Δ | Tasks | Seeds, pooled, normal (n) | Seeds, pooled, exact (power) | Power at 1 seed, pooled exact | Seeds, replicates, sign test (power) |
|---|---|---|---|---|---|---|---|---|
| Ramp fold | solves or has a candidate | 0.625 (mean) | 3 | 22 | 4 (67.1) | 4 (.904) | .080 | 7 (.854) |
| Ramp fold | solves or has a candidate | 0.625 (mean) | 5 | 22 | 2 (36.4) | 2 (.879) | .364 | 6 (.936) |
| Ramp fold | solves or has a candidate | 0.625 (mean) | 10 | 22 | 1 (15.8) | 1 (.936) | .936 | 6 (1.000) |
| Ramp fold | solves or has a candidate | 2 (largest) | 3 | 22 | 5 (93.5) | 5 (.836) | .095 | 9 (.807) |
| Ramp fold | solves or has a candidate | 2 (largest) | 5 | 22 | 3 (45.9) | 3 (.918) | .320 | 6 (.839) |
| Ramp fold | solves or has a candidate | 2 (largest) | 10 | 22 | 1 (18.2) | 1 (.852) | .852 | 6 (.998) |
| Ramp fold | solves | 0.0625 (mean) | 3 | 22 | 3 (56.3) | 3 (.887) | .070 | 7 (.959) |
| Ramp fold | solves | 0.0625 (mean) | 5 | 22 | 2 (32.5) | 2 (.947) | .381 | 6 (.975) |
| Ramp fold | solves | 0.0625 (mean) | 10 | 22 | 1 (14.8) | 1 (.972) | .972 | 6 (1.000) |
| Ramp fold | solves | 1 (largest) | 3 | 22 | 4 (74.3) | 4 (.855) | .086 | 8 (.819) |
| Ramp fold | solves | 1 (largest) | 5 | 22 | 2 (39.0) | 2 (.837) | .352 | 6 (.909) |
| Ramp fold | solves | 1 (largest) | 10 | 22 | 1 (16.4) | 1 (.913) | .913 | 6 (.999) |
| The 37 | both | 0 | 3 | 37 | 3 (94.4) | 3 (.894) | .075 | 7 (.965) |
| The 37 | both | 0 | 5 | 37 | 2 (55.7) | 2 (.946) | .384 | 6 (.972) |
| The 37 | both | 0 | 10 | 37 | 1 (26.6) | 1 (.959) | .959 | 6 (1.000) |
| Training, N600 size, lower bound | both | 0 (no pair) | 3 | 50 | 3 (128.4) | 3 (.892) | .078 | 7 (.963) |
| Training, N600 size, lower bound | both | 0 (no pair) | 5 | 50 | 2 (76.1) | 2 (.942) | .384 | 6 (.969) |
| Training, N600 size, lower bound | both | 0 (no pair) | 10 | 50 | 1 (36.8) | 1 (.952) | .952 | 6 (1.000) |
| Training, R120 size, lower bound | both | 0 (no pair) | 3 | 991 | 3 (2,590) | 3 (.885) | .084 | 7 (.956) |
| Training, R120 size, lower bound | both | 0 (no pair) | 5 | 991 | 2 (1,553) | 2 (.933) | .384 | 6 (.961) |
| Training, R120 size, lower bound | both | 0 (no pair) | 10 | 991 | 1 (776) | 1 (.934) | .934 | 6 (1.000) |

Facts from the table:

- At these D0 values the noise is small against Δ, so the seed counts are set mostly by Δ and little by N or D0.
- No set here is too small to show a change of 3, 5 or 10 at some seed count. On the ramp fold, a change of 10 is 10 of 22 tasks, and the base arms solve 0 to 2 of the 22 (Part A).
- At one seed, a change of 3 or 5 can't be shown when only the Δ changed tasks are discordant: the least two-sided p is 2 × ½³ = .25 for 3 and 2 × ½⁵ = .0625 for 5. A change of 10 can: 2 × ½¹⁰ = .002. The pooled exact power at one seed (column "Power at 1 seed") is .07 to .10 for 3 and .32 to .38 for 5.

## Part C: reach per depth

Script: `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/solve-noise-test-size/reach_depth.py`.

### Inputs

- Bands: `work/measures.md` line 348 (ramp) and line 349 (the 37). The band B of a depth is the largest |gained − lost| over 6 control pairs, from the round 1 and first-pass bundle runs.
- Move rule: `work/measures.md` line 350. A depth moves when gained − lost is past its band, and at least 2, in both seeds with one sign. So a seed passes when gained − lost ≥ T, with T = max(B + 1, 2).
- Per-depth reach: `work/lm/data-study/gold/gold-union/reach-ramp.jsonl` and `reach-37.jsonl`, written by `gold_union_reach.py`, field `per` (`tables`, `reached` per depth, per task and job), jobs `r1 bundle_s0` and `r1 bundle_s1`, `seconds` 600. These are the only control jobs in those files. The first-pass bundle jobs are not in them.
- Ramp: `graph-tables-ramp.jsonl` has sha256 prefix f10a4683fb9a4c7b, the version that line 348 names. The tables per depth in the reach file equal those of line 348.
- The 37: `graph-tables-37.jsonl` now has sha256 prefix d3c089a9218e22ef, and line 349 names db082dafb2b79020. The reach file holds 36 tasks, and line 349 gives 29. Its tables per depth equal those of line 349 at depths 0 to 6, and it has 714 tables at depth 7 and deeper against 723. The reach file groups every depth from 7 on into one row, so it gives no reach at single depths past 6.

### Reach per depth in the control pair, round 1 `bundle_s0` and `bundle_s1`, 600 s

For each depth: union tables (the denominator), tables reached on each seed, the difference (seed 1000 less seed 0, which is gained − lost), and the sum over tasks of the squared per-task difference. That sum estimates the variance of gained − lost for one pair of runs, when tasks are independent.

Ramp fold, 22 tasks:

| Depth | Union tables | Reached, seed 0 | Reached, seed 1000 | Difference | Sum of squared per-task differences | Band (line 348) |
|---|---|---|---|---|---|---|
| 0 | 79 | 68 | 69 | +1 | 3 | 2 |
| 1 | 59 | 33 | 37 | +4 | 12 | 8 |
| 2 | 52 | 15 | 11 | -4 | 6 | 5 |
| 3 | 47 | 2 | 3 | +1 | 1 | 3 |
| 4 | 53 | 0 | 0 | 0 | 0 | 0 |
| 5 | 48 | 0 | 0 | 0 | 0 | 1 |
| 6 | 39 | 0 | 0 | 0 | 0 | 1 |
| 7 and deeper | 68 | 0 | 0 | 0 | 0 | 0 |
| Total, beside the rows | 445 | 118 | 120 | +2 | | |

The 37, 36 tasks, graph version d3c089a9218e22ef:

| Depth | Union tables | Reached, seed 0 | Reached, seed 1000 | Difference | Sum of squared per-task differences | Band (line 349) |
|---|---|---|---|---|---|---|
| 0 | 123 | 88 | 84 | -4 | 6 | 6 |
| 1 | 78 | 37 | 36 | -1 | 11 | 7 |
| 2 | 74 | 18 | 19 | +1 | 5 | 2 |
| 3 | 85 | 4 | 5 | +1 | 3 | 2 |
| 4 | 83 | 2 | 3 | +1 | 1 | 2 |
| 5 | 98 | 0 | 1 | +1 | 1 | 1 |
| 6 | 88 | 0 | 2 | +2 | 2 | 2 |
| 7 and deeper | 714 | 6 | 6 | 0 | 0 | 9: 1; 11: 1; 12: 1; 15: 1; 16: 7; others 0 |
| Total, beside the rows | 1,343 | 155 | 156 | +1 | | |

### Method

- σ is the standard deviation of gained − lost for one seed pair, arm against the control of its seed. Two values are given:
  - σ (pair): the square root of the sum of squared per-task differences above, from the one control pair.
  - σ (band): B / 1.96, which takes the band to be a two-sided 95% bound on one pair's gained − lost. This is an assumption. A band is the largest of 6 values that share runs.
- The move rule as written: power at 2 seeds = P², with P = Φ((M − (T − 0.5)) / σ), the chance that one seed's gained − lost is at least T under a normal distribution with mean M (with a continuity step of 0.5). Under the rule, every seed must pass, so at s seeds the power is P^s, which falls as s grows. The rule shows a move at 2 seeds or at no seed count.
- A mean test at two-sided 95% and 80% power, on the mean of gained − lost over s seeds: s = ⌈(1.960 + 0.842)² σ² / M²⌉, at least 2 because the rule needs 2 seeds. Where σ is 0, the floor of 2 is given.
- Where no control job reached a table at a depth, σ (pair) is 0, and the noise there is not measured.

### Seeds per depth

M is the true move in tables at that depth, per seed. Each cell gives σ (pair) first and σ (band) second.

Ramp fold:

| Depth | Band | T | σ (pair), σ (band) | Mean-test seeds, M = 3 | M = 5 | M = 10 | Rule power at 2 seeds, M = 3 | M = 5 | M = 10 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 2 | 3 | 1.73, 1.02 | 3, 2 | 2, 2 | 2, 2 | .38, .47 | .86, .99 | 1.00, 1.00 |
| 1 | 8 | 9 | 3.46, 4.08 | 11, 15 | 4, 6 | 2, 2 | .00, .01 | .02, .04 | .45, .41 |
| 2 | 5 | 6 | 2.45, 2.55 | 6, 6 | 2, 3 | 2, 2 | .02, .03 | .18, .18 | .94, .92 |
| 3 | 3 | 4 | 1.00, 1.53 | 2, 3 | 2, 2 | 2, 2 | .10, .14 | .87, .70 | 1.00, 1.00 |
| 4 | 0 | 2 | 0, 0 | 2, 2 | 2, 2 | 2, 2 | 1.00, 1.00 | 1.00, 1.00 | 1.00, 1.00 |
| 5 | 1 | 2 | 0, 0.51 | 2, 2 | 2, 2 | 2, 2 | 1.00, 1.00 | 1.00, 1.00 | 1.00, 1.00 |
| 6 | 1 | 2 | 0, 0.51 | 2, 2 | 2, 2 | 2, 2 | 1.00, 1.00 | 1.00, 1.00 | 1.00, 1.00 |
| 7 and deeper | 0 | 2 | 0, 0 | 2, 2 | 2, 2 | 2, 2 | 1.00, 1.00 | 1.00, 1.00 | 1.00, 1.00 |

The 37:

| Depth | Band | T | σ (pair), σ (band) | Mean-test seeds, M = 3 | M = 5 | M = 10 | Rule power at 2 seeds, M = 3 | M = 5 | M = 10 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 6 | 7 | 2.45, 3.06 | 6, 9 | 2, 3 | 2, 2 | .01, .02 | .07, .10 | .85, .76 |
| 1 | 7 | 8 | 3.32, 3.57 | 10, 12 | 4, 5 | 2, 2 | .01, .01 | .05, .06 | .60, .58 |
| 2 | 2 | 3 | 2.24, 1.02 | 5, 2 | 2, 2 | 2, 2 | .35, .47 | .75, .99 | 1.00, 1.00 |
| 3 | 2 | 3 | 1.73, 1.02 | 3, 2 | 2, 2 | 2, 2 | .38, .47 | .86, .99 | 1.00, 1.00 |
| 4 | 2 | 3 | 1.00, 1.02 | 2, 2 | 2, 2 | 2, 2 | .48, .47 | .99, .99 | 1.00, 1.00 |
| 5 | 1 | 2 | 1.00, 0.51 | 2, 2 | 2, 2 | 2, 2 | .87, 1.00 | 1.00, 1.00 | 1.00, 1.00 |
| 6 | 2 | 3 | 1.41, 1.02 | 2, 2 | 2, 2 | 2, 2 | .41, .47 | .92, .99 | 1.00, 1.00 |
| 9, 11, 12, 15 (each) | 1 | 2 | no pair value, 0.51 | 2 | 2 | 2 | 1.00 | 1.00 | 1.00 |
| 16 | 7 | 8 | no pair value, 3.57 | 12 | 5 | 2 | .01 | .06 | .58 |
| other depths from 7 | 0 | 2 | 0 (7 and deeper as one row), 0 | 2 | 2 | 2 | 1.00 | 1.00 | 1.00 |

Facts from these tables:

- Under the move rule, a row with power at 2 seeds under .8 can't show that move at any seed count. On the ramp fold those are: M = 3 at depths 0 to 3; M = 5 at depths 1 and 2, and at depth 3 on σ (band); M = 10 at depth 1. On the 37 they are: M = 3 at depths 0 to 4 and 6, and at 16; M = 5 at depths 0, 1 and 16, and at depth 2 on σ (pair); M = 10 at depths 1 and 16, and at depth 0 on σ (band).
- The rule's chance of a false move at M = 0 (2 P0², with P0 = Φ(−(T − 0.5) / σ)) is at most .035 in every row (the 37, depth 2, σ (pair)), and under .012 in every other row. So the rule is stricter than a two-sided 95% test, and that strictness is why the rule needs larger moves than the mean test.
- Under the mean test at 95% and 80%, the seeds at depth 1 are 11 to 15 for M = 3 and 4 to 6 for M = 5 on the ramp fold, and 10 to 12 and 4 to 5 on the 37. Depth 16 of the 37, on σ (band) alone, needs 12 and 5. Every other row needs 2 to 9 seeds for M = 3, and 2 to 3 for M = 5 and M = 10.

## Settled

- A live test on the ramp fold runs 22 tasks and 4 seeds per arm. It pools the seeds and counts "solves or has a candidate". Reach per depth goes beside it at depths 0 and 2 to 7 and deeper, under the move rule of `measures.md` line 350.
- Training R120 (989 tasks; 8 solves and 10 with a candidate at one seed) is the set where "solves" has power for a change of 10 at one seed (pooled exact power .934 at 991 tasks, Part B). That power is a lower bound, because training has no control pair, so its noise is set to 0. A live test that can pay for it runs on training R120 too. S120 (31 solves of 879) is seeded with gold nodes, so it does not serve as a base for a live test.
- The noise band of the 37 in `measures.md` line 349 is on graph version db082dafb2b79020. The reach file used here is on d3c089a9218e22ef (Part C, Inputs). They have the same tables per depth at depths 0 to 6, and 714 against 723 tables at depth 7 and deeper. A measurement of the 37 against that band states which graph version it used.
