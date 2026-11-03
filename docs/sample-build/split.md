# Held-out split by task: design

A design and a record only. No fit ran, and no held list changed.

Folder: `model/study/samples/split_design/`. Every script below is in it, and runs as `scripts/run_heavy.py --need now python3 <script>`.

- `facts.py` writes `facts.jsonl`: one row per task of `data/tasks/`.
- `summary.py` writes `summary.out`: the spread and the missing count of each candidate variable, and their rank correlations.
- `split2.py` writes `split2.out` (every table below) and `split2.tsv` (task, block, stratum, split, u). Its first argument is the number of salts to try (default 2,000).

Paths that start with `gold-union/` are under `/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/`. Paths that start with `held/` are under `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/`.

## The design

- **Held-out** is exactly the 120 tasks whose `source` has arc-agi-2/evaluation (block E). They are held out for academic reasons, by the user's ruling. No rule, hash or stratum moves an E task out of held-out.
- **Train and dev** cover the other 1,027 tasks (block T), by a hash rule and by strata within T (Part 2).
- Dev is about 15% of T: 161 tasks, against 154.1 expected.

| Split | Tasks | Denominator |
|---|---|---|
| Train | 866 | 1,027 (T) |
| Dev | 161 | 1,027 (T) |
| Held-out | 120 | 1,147 (pool) |

## Part 0: the pool and the data

### The pool

The pool is every task file in `/Users/davidlu/code/arc-workspace/data/tasks/`: 1,147 files, one per task, `<id>.json`. Each file has `source`, a list of `{dataset, split}`, and `train` and `test`. A task can have more than one source.

| Source set (from `source`) | Tasks | Block |
|---|---|---|
| has arc-agi-2/evaluation | 120 | E |
| has arc-agi-2/training, not arc-agi-2/evaluation | 1,000 | T |
| arc-agi-1/evaluation only | 18 | T |
| arc-agi-1/training only | 9 | T |

The lists in `held/` (`ramp-fold.txt`, `tasks.txt`, `leave_out.txt`):

- The 22 (ramp fold): all 22 are arc-agi-2/training tasks, so all are in T.
- The 37: all 37 are arc-agi-2/evaluation tasks, so all are in E.
- The 99: all 99 are arc-agi-2/evaluation tasks, so all are in E. The 99 are the 37 and the 62 of `features-worker/arm/eval-tasks.txt` (the sorted union of those two lists equals the 99). The 22 and the 99 share no task. The three lists together have 121 tasks.

### Fields used

Union graph:

- `gold-union/graph-tasks-SET.jsonl`, SET in training, ramp, 37: `task`, `goal_depth`, `goal_depth_cases`, `tables`, `productions`, `goals` (the count of goal options), and `error` (a row that has `error` has no graph).
- `gold-union/graph-prods-SET.jsonl`: `task`, `ident`, `heads`, `reads`. These give the `fewest_productions` count below.
- `gold-union/case-counts.jsonl`: `task`, `cases`, `distinct_programs`. `cases` is already the count after excluded cases are taken out (`model/study/gold/reads/union/gold_case_counts.py` lines 71 and 78), so it is used as written.

Not used: `bits`, `bits_productions`, `cost_known`, `cost_low`, `path`, `minimax_path`, and every `per_depth` field. `path.productions` is a count, but `path` is the hyperpath of least known bits (`gold_union_graph.py` docstring), so it is chosen under a prior. In its place, `facts.py` computes `fewest_productions` from `heads` and `reads` alone: for each parameterized table, the smallest set of queries that makes it, by set union over a query's reads, to a fixed point; then the least over the goal options. It is an upper bound on the fewest queries of a hyperpath (exact where no read is shared), so every value of it is an estimate.

Grid facts (the F2 set of `features-search-finds-kinds/fit/common.py` line 81, `GRID`): `train_pairs`, `test_cases`, `input_cells_median`, `output_cells_median`, `output_size_equals_input`. `facts.py` computes them from `data/tasks/<id>.json` for all 1,147 tasks, by the definitions of `model/study/gold/reads/task_facts/gold_task_facts.py` (cells are height times width; `input_cells_median` is over train inputs and test inputs; `output_cells_median` and `output_size_equals_input` are over train pairs). It reads no test output. On the 1,110 tasks of `gold/gold-task-facts/task-facts.jsonl`, all five facts are equal to that file's values (`summary.out`, last check line). No outcome field of `outcomes.jsonl` is read.

### Tasks that have no graph

A task has a graph where a graph-tasks row has no `error` and a finite `goal_depth`. 975 tasks have a graph-tasks row without `error`. 2 of them (3490cc26, 696d4842, both arc-agi-2/training) have `goal_depth` inf, so 973 tasks have a graph.

| Source set | Tasks | Graph | `error` "no tables" | `error` "pinned: ..." | No graph row, has a case-counts row | No graph row, no case-counts row | Goal depth inf | No graph, total |
|---|---|---|---|---|---|---|---|---|
| arc-agi-2/evaluation | 120 | 35 | 6 | 13 | 63 | 3 | 0 | 85 |
| arc-agi-2/training | 1,000 | 917 | 33 | 15 | 0 | 33 | 2 | 83 |
| arc-agi-1/evaluation only | 18 | 14 | 1 | 3 | 0 | 0 | 0 | 4 |
| arc-agi-1/training only | 9 | 7 | 0 | 1 | 0 | 1 | 0 | 2 |
| All | 1,147 | 973 | 40 | 32 | 63 | 37 | 2 | 174 |

- The "pinned: ..." errors are "rows unread: ... TableWork cap" for all but one ("does not end", e872b94a).
- The 63 tasks that have gold and no graph row are 62 of the 62 and 1 of the 37: no `graph-tasks-62.jsonl` exists.
- Of the 37, 29 have a graph, 7 have an `error` row (3 "no tables", 4 "pinned"), and 1 has no row. Of the 99, 29 have a graph. All 22 of the ramp fold have a graph.
- Held-out (E) has 85 of 120 tasks without a usable union graph. A measurement of reach on held-out covers the 35 tasks that have one. T has 89 of 1,027 without a graph.

## Part 1: strata variables and bin edges

Strata apply to T only. A stratum is one cell of the cross of the variables below. Spreads are from `summary.out` (n, quantiles) and `split2.out`. Rank correlations are Spearman over the 941 pool tasks that have a graph, a `fewest_productions` value and a case count.

| Variable | Source field | Bins in T | Why, in one line of fact |
|---|---|---|---|
| Goal depth | `graph-tasks-SET.jsonl` `goal_depth` | 1-4 (270), 5-7 (344), 8 and up (324), `none` (89) | It has a wide spread (pool: n 975, q10 3, median 6, q90 12, max 29, 2 inf) and 172 pool rows missing. |
| Output size | grid fact `output_size_equals_input` | same (703), diff (324) | It is missing for no task, and its rank correlation with goal depth is 0.12. |

The cross gives 8 strata. The smallest has 29 tasks (`none` / diff).

Variables left out of the strata, with the fact that left each out. Each is a balance check in Part 3.

- `fewest_productions` (estimate): rank correlation with goal depth 0.91.
- `tables` of graph-tasks: rank correlation with goal depth 0.75, with `fewest_productions` 0.83. `productions`: 0.94 with `tables`.
- `cases` of case-counts: n 1,076, median 2, q90 36, max 4,608, 71 missing; rank correlation with goal depth 0.24. It goes in as a check, to keep the strata few.
- `input_cells_median`: rank correlation with goal depth 0.43, with `output_cells_median` 0.62.
- `train_pairs`: 647 of 1,147 tasks have 3, so it splits the pool little.

Bin edges for goal depth are near the tertiles of the 973 pool tasks that have a graph (`summary.out`: q25 4, median 6, q75 9).

## Part 2: the assignment rule

1. A task whose `source` has arc-agi-2/evaluation is held-out.
2. For any other task `t`, u = (the first 16 hex digits of sha256 of the text `1533:t`, as an integer) / 16^16. So u is in [0, 1). The task is in train where u < 0.85, and in dev where u ≥ 0.85. The cut is the same in every stratum.
3. The salt 1533 was chosen once, and is fixed from now on. `split2.py` tried salts 0 to 1,999. For each salt it summed (count − expected)² / expected over the 8 strata, on the dev count (expected is 0.15 of the stratum). Salt 1533 has the least sum, 0.71. The median over the 2,000 salts is 6.27.

Stability:

- A task's split depends only on its `source` and its id, through the fixed salt. A new task does not move an old one.
- The rule does not hash the stratum into u. A task's stratum can change: for example, a T task goes from `none` to a depth bin when a graph of it is built. Its split stays the same.
- The strata set the salt only. A T task added after this design falls in train and dev at the rates 0.85 and 0.15, with no balance by stratum. A task added with arc-agi-2/evaluation in its source is held-out.
- The rule reads no held list.

## Part 3: sizes

Overall: pool 1,147; train 866 of 1,027 (T); dev 161 of 1,027 (T); held-out 120 of 1,147 (pool).

The salt's sum does not constrain the dev total. Dev is 161 against 154.1 expected, and every stratum is within 3 tasks of its expected count.

Train and dev per stratum (`split2.out`). "Dev expected" is 0.15 of the stratum.

| Stratum (goal depth / output size) | T pool | Train | Dev | Dev expected |
|---|---|---|---|---|
| 1-4 / diff | 111 | 94/111 | 17/111 | 16.7 |
| 1-4 / same | 159 | 133/159 | 26/159 | 23.9 |
| 5-7 / diff | 100 | 84/100 | 16/100 | 15.0 |
| 5-7 / same | 244 | 208/244 | 36/244 | 36.6 |
| 8+ / diff | 84 | 70/84 | 14/84 | 12.6 |
| 8+ / same | 240 | 201/240 | 39/240 | 36.0 |
| none / diff | 29 | 25/29 | 4/29 | 4.4 |
| none / same | 60 | 51/60 | 9/60 | 9.0 |
| All | 1,027 | 866/1,027 | 161/1,027 | 154.1 |

Held-out (E) is not split by strata. Its makeup, by the same facts, over its 120 tasks:

| Group | Tasks |
|---|---|
| Has a graph, output size diff | 10/120 |
| Has a graph, output size same | 25/120 |
| No graph, output size diff | 29/120 |
| No graph, output size same | 56/120 |
| Graph tasks at goal depth 1-4, 5-7, 8 and up | 0, 5, 30 (of 35) |

Balance checks on variables that are not strata. Each row gives the bin's T pool count, then its train and dev counts with their share of the bin, then the held-out count with its share of the 120. The `cases` bin 0 has 1 task, and is joined with the no-row bin.

| Variable, bin | T pool | Train | Dev | Held-out |
|---|---|---|---|---|
| `cases` 1 | 262 | 219 (0.84) | 43 (0.16) | 37 (0.31) |
| `cases` 2-3 | 368 | 309 (0.84) | 59 (0.16) | 36 (0.30) |
| `cases` 4 and up | 332 | 281 (0.85) | 51 (0.15) | 40 (0.33) |
| `cases` 0 or no case-counts row | 65 | 57 (0.88) | 8 (0.12) | 7 (0.06) |
| `fewest_productions` (estimate) up to 7 | 300 | 252 (0.84) | 48 (0.16) | 0 (0.00) |
| `fewest_productions` 8-12 | 354 | 295 (0.83) | 59 (0.17) | 6 (0.05) |
| `fewest_productions` 13 and up | 284 | 243 (0.86) | 41 (0.14) | 29 (0.24) |
| `fewest_productions` none (no graph) | 89 | 76 (0.85) | 13 (0.15) | 85 (0.71) |
| graph `tables` up to 15 | 247 | 205 (0.83) | 42 (0.17) | 0 (0.00) |
| graph `tables` 16-30 | 438 | 368 (0.84) | 70 (0.16) | 6 (0.05) |
| graph `tables` 31 and up | 255 | 219 (0.86) | 36 (0.14) | 29 (0.24) |
| graph `tables` none | 87 | 74 (0.85) | 13 (0.15) | 85 (0.71) |
| `input_cells_median` up to 81 | 322 | 277 (0.86) | 45 (0.14) | 3 (0.03) |
| `input_cells_median` 82-225 | 401 | 331 (0.83) | 70 (0.17) | 31 (0.26) |
| `input_cells_median` 226 and up | 304 | 258 (0.85) | 46 (0.15) | 86 (0.72) |
| `train_pairs` 2 | 165 | 141 (0.85) | 24 (0.15) | 36 (0.30) |
| `train_pairs` 3 | 587 | 492 (0.84) | 95 (0.16) | 60 (0.50) |
| `train_pairs` 4 | 195 | 165 (0.85) | 30 (0.15) | 18 (0.15) |
| `train_pairs` 5 and up | 80 | 68 (0.85) | 12 (0.15) | 6 (0.05) |

Train and dev match each other on these variables. Held-out does not match T: 86 of its 120 tasks have `input_cells_median` 226 and up (0.72, against 304 of 1,027 in T, 0.30), and its graph tasks are deep (30 of 35 at goal depth 8 and up).

### What a dev set and a held-out set of this size can show

Scale is from `solve-noise-test-size/read.md` Part B. That record's normal formula gives the seeds per arm for a paired test at two-sided 0.05 and power 0.8: s = [1.960 √(D0 + Δ) + 0.842 √(D0 + Δ − Δ²/N)]² / Δ², where Δ is the change in solves and D0 the count of discordant tasks in a control pair. Here D0 is scaled from the ramp fold's per-task rate (0.0625 per 22 tasks for solves, 0.625 per 22 for "solves or has a candidate"), so every D0 and seed count below is an estimate. The ramp fold is a T set, so the rate is untested on E. A change is given as a lift in the share of tasks solved, so Δ = lift × N.

| Set | N | Lift 1 point: Δ, seeds | Lift 2 points: Δ, seeds | Lift 5 points: Δ, seeds |
|---|---|---|---|---|
| Held-out | 120 | 1.2, 9 | 2.4, 4 | 6.0, 2 |
| Held-out, tasks that have a graph | 35 | 0.35, 29 | 0.7, 13 | 1.75, 5 |
| Dev | 161 | 1.6, 7 | 3.2, 3 | 8.1, 2 |

(Solves. For "solves or has a candidate" the seeds are 26, 8 and 3 on held-out; 87, 28 and 7 on the 35 held-out tasks that have a graph; 19, 6 and 2 on dev. `split2.out`.)

- A change of 3 solves on 22 tasks needs about 4 seeds, and is a lift of 14 points. On held-out, a change of 3 solves is a lift of 2.5 points, and it needs 3 seeds (estimate, s = 2.89 before rounding up). On dev it is a lift of 1.9 points, and it needs about 3 seeds (s = 3.00). The seeds follow Δ more than N. A larger set turns the same lift per task into a larger Δ.
- A measurement of reach on held-out covers 35 tasks, since 85 of the 120 held-out tasks have no usable union graph. On those 35, a lift of 1 point is Δ = 0.35, which is below one task. A change of 3 tasks is a lift of 8.6 points.
- Base rate, for scale: R120 solves 8 of 989 training tasks at 120 s (record Part A). At that rate, held-out has about 1.0 base solves and dev about 1.3 (estimates; the rate comes from T tasks).
- For a per-task mean over held-out, such as a fit's score per task, the standard error is √(120/22) = 2.3 times smaller than on the 22, and over dev √(161/22) = 2.7 times smaller, at equal spread per task (arithmetic).
- Dev takes the choices of a fit (settings, when to stop). Held-out is scored once per decision.

## Part 4: where the 22, the 37 and the 99 fall

- The 37 and the 99 are all E, so all 37 and all 99 are held-out.
- The 22 are all T, so they fall into train or dev by the rule: 19 in train, 3 in dev. None is held-out.

The 37 and the 99 by held-out group:

| Held-out group | Held-out | The 37 | The 99 |
|---|---|---|---|
| Has a graph, output size diff | 10 | 5/37 | 5/99 |
| Has a graph, output size same | 25 | 24/37 | 24/99 |
| No graph, output size diff | 29 | 1/37 | 21/99 |
| No graph, output size same | 56 | 7/37 | 49/99 |
| All | 120 | 37/37 | 99/99 |

The 99 are 99 of the 120 held-out tasks. The other 21 held-out tasks are in none of the three lists.

The 22 by stratum:

| Stratum | T pool | The 22 | Expected | Train | Dev |
|---|---|---|---|---|---|
| 1-4 / diff | 111 | 2/22 | 2.4 | 2 | 0 |
| 1-4 / same | 159 | 8/22 | 3.4 | 6 | 2 |
| 5-7 / diff | 100 | 4/22 | 2.1 | 4 | 0 |
| 5-7 / same | 244 | 4/22 | 5.2 | 4 | 0 |
| 8+ / diff | 84 | 1/22 | 1.8 | 1 | 0 |
| 8+ / same | 240 | 3/22 | 5.1 | 2 | 1 |
| none / diff | 29 | 0/22 | 0.6 | 0 | 0 |
| none / same | 60 | 0/22 | 1.3 | 0 | 0 |
| All | 1,027 | 22/22 | 22.0 | 19 | 3 |

"Expected" is the stratum's share of the 1,027 times 22. The 22 over-fill goal depth 1-4 (10 against 5.8 expected), under-fill goal depth 8 and up (4 against 6.9), and have no task without a graph (1.9 expected).

## Part 5: what the ruling fixes

- Held-out is the 120 E tasks, and no other task. The 37 and the 99 are inside it, so no fit trains on either. A held-out result on the 37 or the 99 stays comparable between fits.
- A fit trains on train, which has no E task. Dev has no E task, so dev shows nothing about E. Held-out is the only set that measures E, and its tasks differ from T in grid size and in graph depth (Part 3).
- The 22 are not a held-out set. A fit trains on 19 of them and may use the other 3 as dev tasks. A score on the 22 is no longer a held-out score.
- Train and dev are balanced by goal depth and output size, so a dev score applies to T with the same strata mix.
- Held-out is 120 tasks, and a measurement of reach on held-out covers 35 of them. Part 3 gives what that size can show.
- The lists in `held/` are not changed by this record. `split2.tsv` is the assignment.

## Notes

- `model/study/gold/reads/task_facts/gold_task_facts.py` sets `union_cases` to case-counts `cases` less `excluded`. `cases` is already net of excluded cases, so `union_cases` in `gold/gold-task-facts/task-facts.jsonl` takes them out twice (13 tasks get a value below 0). This design uses `cases` as written. Dataset-worker has fixed it: `union_cases` is now `cases`, and the new `task-facts.jsonl` (sha256 prefix 0bfa09c7) has no value below 0. The strata use no case count, so the split does not change.
- `fewest_productions` is an upper bound (Part 0), and it is a balance check only. No stratum uses it.
