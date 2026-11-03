# Node rank model on pool records: design

Reader: the Sonnet agent that builds this work, and the coordinator who runs its slow commands.

## Goal

Ready forms stop because the right program's intermediates rank at about 4,500 of 14,700 nodes under the hand node score, and a form needs its reads at about rank 10. The measure is the chance per opening at the top ranks. AUC is not the measure.

This work fits a rank model on pool records, with the label "is an intermediate of the right program", on DAG-invariant per-instance features. It reads the model once on the 13 hour runs and once on the 37 at 600 s, as the rank of each right intermediate and the chance per opening at a scope draw, against the hand score.

## Rules

1. Features read only what the search has at that point. They never read gold, `gold_atom`, point_group depth, `d_out`, or task, case, point or author names. Labels may read gold.
2. hop1 features never read `tags`, `is_gold`, `gold_sexp`, test outputs or clause text. This design doesn't use hop1 rows.
3. No lexical order and no binder marks. No feature reads a form's text position, an atom's index, the last atom, `*` or `^`.
4. Held tasks tune nothing. Each final model is read once on the 37 and on the 13 hour runs, and each read has a line in `ledger.jsonl`.
5. Do not read `runC*_holdout`, `D/runR3_holdout`, `D/relpicks_*.tsv`, `feat-exp/private/`, `feat-exp/case-cache*/`, `feat-exp/out/`, `feat-exp/stream/`, `*.building`, `judgetool/dataset-contexts/`, `dataset-export-receipts/`, `operator/private`, or `inform-key/`.
6. Every Bash call is one command under `timeout 30`. No background commands. Never poll a task output. Each script takes a SECONDS argument, resumes, and streams its rows. A slow command goes to the coordinator with its ETA. If `timeout 30` stops a command, don't rerun it in pieces.
7. At most 4 processes at once on the Mac. Run each heavy command through `/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus N`.
8. Write nothing in the repo outside the run folder. Write no test files. A check in this design is a count that a script prints.

## Paths

- `W` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/`
- `F` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/`
- `G` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/`
- `RUN` = `F/features-node-rank-model-train-read-hour13-heldout37/`, the run folder. It holds `manifest.json`, the scripts, rows and models.
- `DESIGN` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-node-rank-model-design/`. Its `scratch/` folder holds short check scripts: `rt.sh`, `label_check.py`, `rebuild_rate.py`, `rebuild_diag2.py`, `hand_cost.py`, `seed_vs_found.py`.
- `POOLG` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/poolg/`, with `common2.py`, `poolrun.py`, `aucs.py`. Its `common2.py` loads `flat/common.py` from the folder beside `poolg/`.
- `JOINT` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/scope-joint/`, with `sampler-picks-cache.py`, `sampler-ready-forms.py`, `sampler-ready-read.py`, `sampler-label-matrix.py`, `sampler-label-read.py`, `sampler_replay.py` and `rows/`. `W/sampler-scope-joint-read/` holds a durable copy of part of it, with the same rows.
- Engine scripts run with `DESIGN/scratch/rt.sh`: Mac runtime ba0754492, Python 3.13 venv `ast/run/runtime-kaggle-py313/venv`, sklearn 1.6.1, numpy 2.1.3. Fits run on that same Python. Scripts with no engine run on `work/lm/.venv/bin/python -I`.

## Record sets

| Name | Path | Tasks after the exclusions | Pool | Rows of a table | Gold revision of the run | Arm |
|---|---|---|---|---|---|---|
| R120 | `W/sampler-cover-clauses-train-120s-c87cf482a/out/`, and `W/sampler-cover-clauses-train20-120s-c87cf482a/out/` | 970 + 19 | 120 s, median 661 nodes, depth mostly 1 to 3 | `x_rows` in the record | `gold-v3-drawable-rewrite-ba59a0ab1` | Plain pool, fold priors, old steers, one process, no `ONE_REPAIR`, wheel c87cf482a |
| S120 | `F/features-corpus-pool-seed1-120s-ship7/level1_search/` | 910 | 120 s, gold seeded to 1/3 of depth, about 670 nodes, depth to 6 | `x_rows` in the record | `gold-v3-before-drift-regold` | Seeded pool, `tags.seeded`, ship7 kit, `models-held` |
| N600 | `W/sampler-pool-dag-nodes-train50-600s/out/nodes_s0/`, gold side `W/sampler-node-export-train50/gold-sig.jsonl` | 50, in `W/kits/sampler-pool-dag-nodes-train50-final-8be414670/draw.json` | 600 s, 142,726 nodes and 124,986 forms in all, about 2,850 nodes a task | No. The bank holds none, and the export has none. [Item 5](#items) rebuilds them | `gold-v3-cuts-final-round52`, `G/gold-v3-combined-cut/view-final/` | Plain pool, worker path, `models-final` (`live_priors.pkl` 7abf6c639111f01b), DAG steer `relR4_o` (3015d409597fff42), `choice5_o` as shipped, the old choice steer, wheel c87cf482a |
| H | `W/sampler-pool-fold-hour-3600s/out/`, arms `hour_s0`, `hour_s1` | 13 of the fold, 26 runs, read only | 3,600 s, median 14,738 nodes at the last write, 2,781 at 600 s | No, rebuilt | `gold-v3-extended-cut`, `W/sampler-extended-cut/points-with-ramp.json` | `models-coverf`, worker path |
| B | `W/sampler-pool-extended-text-pass1-600s/out-all37/`, arms `base_s0`, `base_s1` | 37, 74 runs, read only | 600 s, about 2,800 nodes | No, rebuilt | `G/gold-v3-extended-cut/view-pass1/points-eval.json` | `models-base`, worker path |

Exclusions from every fit and tune row: `W/held/tasks.txt` (37), `W/held/ramp-fold.txt` (22), `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/arm/eval-tasks.txt` (99). R120 holds 21 fold tasks, and its 20-task folder holds 1. S120 holds 20 fold tasks, and its manifest doesn't exclude them. Drop them by the list, not by the manifests.

The hand score has one model file in the three kits read, sha256 2ec93ed1.

N600's priors and steers were fit on its tasks. So a fit on N600 tests on the 37 or the 22 only, and a number on N600 is a tune number.

## Facts that set the design

These were read on samples, and each sample is named.

### Fit rows

| Source | Positives | Depth of positives | Bias |
|---|---|---|---|
| R120 | 3,584 cover events on 970 tasks: DET 2,106 (2,043 at depth 1), INIT 785, RULE 693 (35 at depth 3 or more). Median 3 a task, 17 tasks have none | Mostly 1 and 2 | Positives are what a search reached, so they skew to short forms |
| S120 | About 7.1 seeded tables a task on 21 tasks: DET 2.9, INIT 3.0, RULE 1.3. About 6,500 in all | To 5 and more | A seeded node's clause is gold's text |
| N600 | 947 gold forms, 1,165 tables on 50 tasks. By row hash, 728 nodes on 225 forms; recorded covers give 213 forms, with 13 on row hash only and 1 recorded only. 27 forms have no key. 450 forms are at depth 7 or more. Tasks differ a lot: 48131b3c has 9 nodes on gold | Deep pools | Priors and steers fit on these tasks, and the pools hold the old choice steer |

Seeded against found, on 21 tasks with both pools, 149 seeded tables and 97 found tables:

- 73 tables are in both pools, which is 49% of seeded and 75% of found. A table feature has the same value on such a node in both pools, because it reads the same rows.
- 60 of those 73 have the same text after names, and most of them are DET domains.
- Seeded INIT is 5 times as frequent as found INIT. Its median is 7 atoms against 3, and 48 rows against 10.
- Seeded RULE is 2 times as frequent as found RULE. Its median is 4 atoms against 3, and 164 rows against 56.
- Seeded and found both have a median of 1 alternative. Junk has 2.
- So table rows don't differ between a seeded and a found node, and form shape does. Seeded shape is gold's writing. The pool's negatives also differ: in S120 they read gold's forms, and they reach depth 6.

Choice of fit rows: all three sets, each pool as one group.

- R120 gives found positives and plain negatives.
- S120 gives positives that don't depend on search reach, and the INIT and RULE forms that R120 lacks. Form shape columns are empty on every row of an S120 pool, seeded or not. A mask on seeded rows alone would mark them as gold.
- N600 gives the negative mix of a long pool and the tune read. It is the only source near the read's pool sizes, and on the worker path.
- hop1 rows are not used. Their junk is drawn on gold's own prefix, and they have no form shape.

### Labels

- Run's tags are exact against the run's revision. On 13 sampled R120 tasks, 7,929 nodes, `tags.kind` gold is 53 nodes, and order-free key and row hash give the same 53. The training run goes through `superdag_search.py`, which installs the order-free `table_key` before it computes gold keys, so the gold key fault on `kaggle_worker.py` doesn't reach R120.
- The tied-column fault is a fault of the worker path: `kaggle_worker.py` computes gold keys before `source()` installs the key.
- Newer gold text adds few positives on R120. The union with `view-final`, `view-full` of the extended cut and the cheapest view gives 57 nodes against 53 on those 13 tasks.
- **A second row hash fault, Ident columns.** An `Ident` column's values are session ids. On the sets below, every rebuilt node that differs from its bank node, apart from one run, has an `Ident` column and equal row counts:

| Bank | Nodes read | Nodes with Ident | Differ, all with Ident |
|---|---|---|---|
| `base_s0 135a2760` | 1,929 | 181 | 162 |
| `hour_s1 b2862040` | 1,642 | 124 | 108 |
| `nodes_s0 1efba499` (N600) | 1,370 | 51 | 38 |

So about 80 to 90% of Ident tables can't match a row hash made in another session. Gold tables with Ident are 45 of 218 on the 13, 566 of 1,624 on the 37, 180 of 1,165 on N600. 30 of 178 forms on the 13 and 474 of 1,331 on the 37 have only such tables. So a row hash label from a Mac replay misses those forms in pod banks, and a read that counts "no table" by row hash counts too many. Recorded cover events are not affected, since they use one session's key. The rank rows of `sampler-scope-joint-read` and the export's `gold` field are affected.

- **A fault of one run.** On `hour_s0 d23f8c26`, 209 of 3,421 nodes have other row counts on replay. The clause `(DET &f112 (ex_input (:E *E) (:P *P) (:Col *Col)))` has 9 rows in the bank at draw 199, and 108 on replay and in later forms with the same text. The three forms checked all sit in visit 4, draws 169 to 232, and their children inherit the table. The visit's scope doesn't change the replay. The cause is not known. `hour_s1 b2862040`, `base_s0 135a2760` and `nodes_s0 1efba499` have 0 such nodes in the samples, and R120 has 0 in a sample of 2,334 nodes.
- Mac runtime ba0754492 agrees with the pod's wheel c87cf482a on rows: on R120 records, 80 of 80 classified differences are Ident columns with equal counts.

### Traps of `x_rows`

Sample: 13 R120 tasks, 7,929 nodes.

An `x_rows` entry is `[[kind, index], rows, row count, {DET slot: rows}, model, extents]`. Kind 1 is train, kind 2 is test, and `[0, 0]` is one table for all examples.

| Fact | Share of nodes |
|---|---|
| Repeated entries of one example | 42.8% |
| A DET slot in an entry | 66.7% |
| Entries `[0, 0]` only | 31.3% |
| An `Example` column | 15.7% |
| `Example` column and more than one `[0, 0]` entry | 5.7% |
| A capped entry, row count over the rows kept | 3.3% |
| An `Offset` column | 1.2% |

- Repeated entries of one example are alternatives of a DET choice. The hand reader `tr[e] = rows` in `nodefeat.py` and `out[e] = c` in `outfeat.py` keep the last alternative only.
- The hand reader treats any kind but 1 as test, so it reads no train rows on `[0, 0]` tables. Its median cost of .02 ms shows this.
- `nodefeat.widths` omits `Offset`, so `columns` gives None on those tables.
- A table with an `Example` column holds each example's rows in one entry. A reader that drops the column, or skips the split by example, makes tables look equal that hold other cells on other examples.

### Cost

Mac under load, 3,300 nodes of R120: hand features .93 ms mean, q99 13.9 ms, max 275 ms. Model call .45 ms. JSON read 1.22 ms a node.

Replay of a form with its ancestors: 5.7 to 10 ms a form, RSS 353 MiB after 20 s, on H, B and N600.

A worker on a pod makes 4.1 nodes per second at the hour, so 240 ms per node. A pod is about 3 times slower than the Mac.

## Decisions

### Budget

The score must run when a node is born, in `Policy.add`, and a scope draw then reads stored scores. So the cost is per new node.

- Budget: features and model together at most 8 ms mean per node on the Mac under load, about 24 ms on a pod, which is 10% of a worker's time per node. q99 at most 60 ms. Item 3 measures this and stops on a miss.
- No feature reads other nodes, so no pool work is added, and a node keeps one score from birth.

### Normal form of a table

`read_table(table_types, x_rows, n_train, n_test)` gives, for each world, for each example, a set of typed rows.

1. Widths: `Position`, `Box`, `Offset` are 4 cells each. Every other type is 1.
2. A Position's cell is `(v[0], v[2])`, as `nodefeat.py` reads it. Check this and the meaning of a Box in item 3, on `input` and `ex_input` tables.
3. A world is the set of entries with one DET assignment, keyed by the sorted values of `e[3]`. With no slots there is one world.
4. Entries of kind 1 and 2 go to their example.
5. A `[0, 0]` entry with an `Example` column is split by that column. A value under `n_train` is that train example, and another value is test example `value - n_train`. Item 3 checks this against test input colors. The column is then dropped from the rows.
6. A `[0, 0]` entry with no `Example` column is the same rows on every example.
7. At most 8 worlds are read, the 8 with the least content hash, and the count of worlds is a feature. Content hash reads rows only.
8. `Ident` values are never read as values. A feature reads only which rows share an id.
9. Test outputs are never loaded. The loader removes `output` from each `test` item and asserts that no feature code receives it.

Each fact is computed per world and per train example, then given as the mean over examples and the minimum over examples, then as the greatest over worlds. A column fact is the greatest over columns of its type, with the mean beside it where the group needs it. Maximum, mean and minimum read no order, of entries, of columns or of examples.

Cell facts use boolean masks of grid size in numpy.

### Feature groups

| Group | Facts | About |
|---|---|---|
| Table | Count per column type, log rows per example (mean, min, max), empty on any train, on all train, one row, capped, worlds, alternatives per example, constant columns, distinct share per column, a Position column that is a key, Position determines Color, Ident classes per example and class sizes, rows equal on all train examples | 45 |
| Pairs | Per Position column: cells over area, share in input foreground, in output foreground, precision, recall and IoU against changed cells, against output foreground, against input foreground; is a color class of the input, of the output; lies in one output color; share of unchanged cells; connected parts; shape among input objects, output objects, moved objects. Paint of Position with Color: fixed, broken, stale, wrong after paint, exact, per-pair best and worst, conflicts, out of bounds, a fixed color map. Fill by one color | 55 |
| Output cells | Color histogram against the output's and against changed cells, the cell set at any offset inside the output, row count equal to changed count or output foreground count, a constant ratio of rows to those counts over train examples, Box extents equal to the output size, `Nat` values among heights, widths, counts of colors and objects of the output, Color values among output colors, new colors, the output background | 30 |
| Test input | Log rows on test, rows per area on test against the train range, empty on test with rows on train, colors inside the test input's colors, cells out of bounds, foreground share on test less the share on train, is a color class on test, shape among test input objects | 15 |
| Depth | Form depth at birth, count of forms read, kind | 3 |
| Form shape, as a set | Atoms, NOT atoms, OR branches, comparisons, ALL and IF, labels, labels with 2 or more sites, head columns, counts of `input`, `ex_input`, `ex_output`, reads of forms, reads of ports by port name, INIT pattern name, counts of the 80 most frequent lib relations and of the others | 100 |

Form shape parses `clause` to a tree, removes `*` and `^`, and maps labels to their site counts. `&fN` becomes "a form" and `&fN.port` becomes that port. N is never read. Label names are never read. The list of 80 relations comes from R120 and N600 pools only.

Left out on purpose: `link_*`, which read parent tables and aren't in the director's list. Also `age`, `uses`, `n_clauses`, `n_readers`, `token`, `draw`, `scope`, `tags`, `score`, hash values, `node.depth` after a merge.

Feature sets: **T** is all groups but form shape. **TS** is all groups.

### Labels

- A node is positive when its table equals a table of a form of a right program, OUT excepted.
- R120: `tags.kind` gold, or a content key match on the union of `points-train.json`, `G/gold-v3-combined-cut/view-final/`, `G/gold-v3-extended-cut/view-full/`.
- S120: `tags.seeded`, or `tags.kind` gold, or a content key match on the same union.
- N600, H, B: a session key match. One process replays the node's form and the gold forms in one session, so no row hash fault applies. N600 reads `view-final`. H reads `points-with-ramp.json`. B reads `view-pass1/points-eval.json`.
- Content key: the order-free key of `superdag_search.table_key`, computed from `x_rows`, with each Ident value first replaced by the hash of the set of its rows without Ident columns. `label_check.py` has `order_free`, which gives the engine's key on 1,024 of 1,044 gold tables. Capped tables are most of the rest.
- A negative whose plain form equals a positive's plain form has weight 0 in the fit. Plain form is the table with its Example, constant and repeated columns dropped. These nodes restate a right table, so they aren't clean negatives.
- Label noise that stays: a table of a right program that no revision holds counts as a negative. This can't be measured here.

### Model and objective

The draw takes the top 5 of `score - uses + Gumbel`, which is a softmax draw on `e^score` without replacement. So the objective is the log chance of a softmax pick, per positive, against the pool's negatives.

For a pool g with negatives N, positives P, and weight `w_p`:

`L_g = - sum over p of w_p log( e^{s_p} / (e^{s_p} + l_g sum over n in N of e^{s_n}) )`

- `l_g = (14,700 / n_g)^a`, with `a` in {0, 1}. With `a` = 1 a pool of 660 nodes trains as if it had 14,700, so the loss keeps pressing where a positive is already at the top of a small pool.
- A positive competes with negatives only, so a pool's many positives don't cancel.
- `w_p = c_k / m_gk`, where `m_gk` is the count of positives of class k in pool g. So a task counts once per class it has, and a task with many positives doesn't lead the fit. N600's tasks differ a lot in this. `c_k` makes the four classes equal in total: DET at depth 1, DET at depth 2 or more, INIT, RULE. Otherwise DET domains at depth 1 hold 57% of R120's positives.
- Booster: softmax boosting as in `F/features-relation-pick-rank-context-rows-heldout37/features_rel_fit.py`, a Newton step per round with `HistGradientBoostingRegressor(max_iter=1)` on gradient over hessian. The venvs have no LightGBM.
- Settings: 300 rounds, 15 leaves, step .08, `min_samples_leaf` 40, L2 1, 64 bins, no start score.
- A tree fits all positives, the top 256 negatives of a pool by current score, and 1 in 6 of the others at weight 6.

AUC isn't read for a choice. It is printed for the record.

### Score to chance

The draw stays the hand score's draw: `Policy.scope` with `key = s - uses - log(-log r)`, 5 scored picks and 1 least-used pick, ancestors added, cap 96 forms, `USES` 1. The only change is `s = t * model(node)`. `t` is chosen on tune from {.5, .75, 1, 1.5, 2}.

### Tune

N600 is the tune read. It is split into 5 task folds of 10 tasks. A fold's tasks leave every source when that fold's model is fit. So a task in N600 leaves R120 and S120 too.

Arms, each with 5 folds, 150 rounds:

| Arm | Features | Sources | `a` |
|---|---|---|---|
| A1 | T | R120, S120, N600 | 0 |
| A2 | T | R120, S120, N600 | 1 |
| A3 | T | R120, N600 | better of A1, A2 |
| A4 | T | S120, N600 | better of A1, A2 |
| A5 | TS | better of A2, A3, A4 | better of A1, A2 |
| A6 | Hand's 87 features, as the hand reader computes them | as A5 | as A5 |

Tune measure: the mean over tasks of the task's median one-step chance over its ready forms at the last write, by the read of item 11, on the log scale. A task with no ready form counts for nothing. Rank of RULE reads, task by task, is beside it. The hand score on the same pools is the base. A3 and A4 show how far seeded and found rows carry to each other.

Chosen: the T arm with the highest measure. TS is fit too, for its held read. Priors and steers are in sample here for form shape, so tune can't show if TS holds on held tasks. Only the held read shows it.

### Final models

Each is fit on all rows of the chosen sources, at the rounds and `t` that tune chose.

| Model | Features | Label |
|---|---|---|
| M-T | T | True |
| M-TS | TS | True |
| C-shuffle | T | Shuffled within task: each pool's labels are permuted over its nodes, with the count held |
| C-depth | Depth group | True |
| C-hand | Hand's 87 features | True, same objective |

C-hand reads whether a gain comes from the objective or from the features.

### Read

Set H is read at its 3,600 s cut and its 600 s cut, and set B at its last write.

1. **Rank.** At the cut, each read of each ready form, with its node's rank by score and by `score - uses`, and the table's rank. Ties at their mean.
2. **Chance, static.** At the cut with `uses` at 0, the chance per opening `1 - exp(-c w)` by `solve_c`, for each read, and `p_all` for a form's reads, with ancestors counted through `reachN`, as `sampler-ready-forms.py` does.
3. **Chance, replay.** Each opening of each run is drawn again from the run's alive nodes, with the model's score, and `uses` that follow the model's own picks. 20 seeds per run. The pool is held as it was. `p_actual` is then computed as `sampler-ready-forms.py` does at every 10th opening, and at each window's start, middle and end.

A form's window is `d_ready` to `d_end`, from the run's record. The primary numbers:

- **M1**: median over the form-runs of the replay `p_actual`, the one-step chance per opening of holding all reads.
- **M2**: median over RULE reads of the absolute rank by `score - uses` at the last opening of the window. It is about 4,500 for the hand score.
- **M3**: form-runs with M1's chance at .1 or more.

Each number is given twice: on the 34 form-runs of `sampler-form-rows.tsv` with `pop` `ready_end`, which match the published read, and on the form-runs that session key labels give. Bands are 90%, from 10,000 resamples of tasks. The second seed of a task isn't independent.

Also printed: the chance by rank curve, the share of picks by kind, the share of weight in the top 10 and top 100, and DET reads apart from RULE and INIT reads. Nodes that fail the row check in item 5 are given as a count, and M1 and M2 are given with those nodes left out.

### Controls

| Control | Passes where |
|---|---|
| C-shuffle | M1 at most .0107, the flat draw, and RULE rank share at least .3. A miss is a leak or a code fault. Stop, and read no other model |
| Base reproduction | The hand score through the read's code gives M1 .00055 (.00050 to .00060), and 0 nodes with other uses on the replay of H, before any fit |
| Order check | On 2,000 nodes: shuffled atoms and branches, renamed labels, renumbered forms, entries and same-type columns in other orders give equal features, with 0 differences |
| Row check | Features from rebuilt rows equal features from record rows on 500 R120 nodes, with Ident read as above |
| Name check | No feature name holds a banned word. The top 30 features by permutation gain are printed before any held read |
| Wrong task | On N600 tune folds, A1's model with features computed on another task's pairs. Printed, with no bar |

### Bars

Stated before any fit. Bars on H are absolute, and they hold under both label sets, with the first set deciding. The hand score has M1 .00055, M2 about 4,500, M3 2 of 34. The flat draw has M1 .0107. Each read at rank 1 has .445, and at rank 100 has .0077. The figures are the published ones, on the labels of that read.

| Verdict | M1 on H | M2 on H | M3 on H | On B, gain in median chance over the hand score |
|---|---|---|---|---|
| Block removed | .1 or more | 10 or less | 20 of 34 or more | 30 times or more |
| Useful | .05 or more | 30 or less | 12 of 34 or more | 10 times or more, band over 3 times |
| Signal, not enough | .0107 or more | 300 or less | | 3 times or more |
| Weak | .0055 to .0107 | 300 to 1,000 | | |
| Closed | Under .0055 | Over 1,000 | | Under 3 times |

- A verdict needs all of its row's cells that hold a number. Otherwise the next row down applies.
- Useful also needs the 90% band's low end of M1 over .0107.
- The model read for a verdict is M-T, and M-TS beside it. If M-TS passes a higher row than M-T, the note says that form shape carries the gain and that its gain is in doubt, since priors and steers were in sample for it.

### What closes it

The work closes when M-T and M-TS both read Closed and the controls pass. It then says: per-instance facts of a node, read at birth, don't lift a read past 10 times over the hand score. A later try needs a fact that isn't per instance.

It also closes if M-T reads Weak and C-hand reads within 2 times of M-T, since then new features add nothing over the objective.

A verdict of Useful or better goes to the coordinator for a live arm, which this design doesn't build. The held pool can't show what picks would have made.

## Items

Each item ends with what to report. Items 4, 5, 6, 8, 9, 10 and 11 hold slow commands, which go to the coordinator as [Slow commands](#slow-commands) gives. Write each script so that one call does at most SECONDS of work and a rerun resumes.

1. **Start the run folder.** Make `RUN`. Copy into it `POOLG/common2.py`, `POOLG/poolrun.py`, `POOLG/aucs.py`, `flat/common.py` with `gold-sig.jsonl` and `gold-dups.jsonl`, `POOLG/gold-sig37.jsonl`, `POOLG/gold-dups37.jsonl`, and from `JOINT` the scripts of its manifest and `sampler_replay.py`. Change their hard paths to `RUN`, since `/private/tmp` doesn't survive a restart. Add `SET` (`hour` or `base`) as an argument where a script names `hour`. Write `manifest.json` by `work/naming.md`: command, commit, task sets, budget, measures, start, gold revisions, `wheel_engine`, node records with their arms and eligibility, the priors and steers of N600, and the priors of R120 and S120. Copy this file to `RUN/design.md`.
2. **Reproduce the base.** Run the picks cache, ready forms and ready read from `RUN` on H. Check M1 .00055 and 0 nodes with other uses. Then run them on B, which no read has done, and write `baseline.json` with M1, M2, M3 and the replay checks of both sets. If a B run fails the replay, report the run and leave it out. Do this before any fit.
3. **Normal form and features.** Write `features_node_read.py` ([Normal form](#normal-form-of-a-table)), `features_node_key.py` (content key), `features_node_shape.py` (form shape) and `features_node_feats.py` ([Feature groups](#feature-groups)). Check on 3 tasks: Position cell and Box meaning on `input` and `ex_input` tables, Example values on test against the test input's colors. Print each fact's share of empty values on 1,000 R120 nodes. Run the order check and the name check. Measure ms per node on 2,000 R120 nodes, mean and q99. If the mean is over 8 ms or q99 over 60 ms, cut the costliest group first, and report what was cut. Report the rate, which sets the ETAs of items 5 and 6.
4. **Labels of R120 and S120.** `features_node_labels.py` replays each task's gold revisions in one session on the Mac and writes the content keys of its tables, then marks nodes. One process per 20 tasks, as processes grow from task to task. Report positives by source, kind and depth, nodes that tags alone miss, and tags that the content key misses. A tag that the key misses is a fault: stop and report it.
5. **Rebuild rows of N600, H and B.** `features_node_rebuild.py SET ARM TASK SECONDS`, one process per run, reads the bank, replays each form with its ancestors in depth order (the code path of `DESIGN/scratch/rebuild_rate.py`), and replays the run's gold forms in the same session, which gives the session key label. It uses the kit of its set: `kits/sampler-pool-dag-nodes-train50-final-8be414670` with `models-final`, `kits/sampler-pool-fold-hour-8be414670` with `models-coverf`, `kits/sampler-pool-extended-text-pass1-8be414670` with `models-base`. It writes a row per node: node id, form id, row check, label, features. The row check has the values `equal`, `ident` (Ident column, equal counts), `tied`, `other counts`, `no table`. Rows aren't kept. Report the row check by run. Report positives by session key against row hash and recorded covers, and the new count of reads with no table.
6. **Features of R120 and S120.** `features_node_matrix.py` streams the records and writes per-task feature rows with labels. On S120 pools it leaves form shape empty on all rows. It writes features as uint8 by bin edges that the fit tasks fix, so a fit holds them in about 300 MiB.
7. **Row check and plain-form weights.** Run the row check on 500 R120 nodes. Mark weight 0 on negatives by plain form. Report the count of such nodes per source.
8. **Booster.** `features_node_fit.py` per [Model and objective](#model-and-objective), with `--features`, `--sources`, `--a`, `--fold`, `--label`. Run one fold of A1 at 20 rounds to check that the loss falls and to measure seconds per round. Report the rate.
9. **Tune.** Run arms A1 to A6 and the wrong task control, then choose the arm, rounds and `t` as [Tune](#tune) says. Write `tune.json`. This reads no held row.
10. **Final fits.** Fit the 5 final models. Write each with its sha256, features, sources, rounds, `t`, and the banned-name and permutation-gain prints. Check the cost of one scored node with the final model on 500 nodes: features and one-row call together.
11. **Held reads, once each, in this order: C-shuffle, C-depth, C-hand, M-T, M-TS.** `features_node_read_held.py MODEL` scores H and B, and runs [Read](#read). Before each read it writes a ledger line with model sha256, time and sets, and it refuses a model that has a line. It writes the rows and a line of results after. If C-shuffle misses its bar, stop.
12. **Report.** Write `results-section.md` for `work/results.md`: the finding, the verdict by [Bars](#bars), tables of M1, M2, M3 per model on both label sets and both sets, the row check, the labels' change against the published read, the prediction against the result, and the limits. Name the measures by their entries in `work/measures.md`.

## Slow commands

Rates are measured on the Mac under load, 4 processes where a step can use them. Items 5 and 6 carry the 8 ms budget for features, and item 3 replaces it with the measured rate.

| Item | Work | Rate | CPU | Wall | Memory |
|---|---|---|---|---|---|
| 2 | Picks cache and ready forms on B | Each under 30 s per call at H's rate, 74 runs | About 30 min | 8 min | 1 GiB a process |
| 4 | Gold replays on 1,899 tasks | 1.2 s a task on 3 revisions | 38 min | 10 min | 1.5 GiB a process |
| 5 | N600, 124,986 forms, 142,726 nodes | 10 ms a form, 8 ms a node | 40 min | 10 min | 1.5 GiB a process |
| 5 | H, 382,616 nodes | Same | 109 min | 27 min | 1.5 GiB a process |
| 5 | B, about 205,000 nodes | Same | 58 min | 15 min | 1.5 GiB a process |
| 6 | R120 and S120, about 1.27 million nodes | 9.2 ms a node, JSON included | 3.2 h | 49 min | 500 MiB a process |
| 9 | 30 fits of 150 rounds | About 1.5 s a round on 2 threads, from the relation read's 1 s a round per million rows | 1.9 h on 2 threads each | 56 min with 2 at once | 4 GiB a process |
| 10 | 5 fits of 300 rounds | About 2 s a round on 2 threads | 50 min on 2 threads each | 25 min with 2 at once | 4 GiB a process |
| 11 | 5 models, 20 seeds a run on H and B | About .5 ms an opening | 25 min | 7 min | 2 GiB a process |

Total wall about 3.5 h at 4 processes. No pod is needed. If the Mac can't give 4 processes, the fit steps can move to a pod through devops-worker at about 3 times the wall, with 30 GiB. The engine replays stay on the Mac, as their runtime is there.

## What could make the read wrong

1. **Fit and read pools differ.** R120 and S120 are small pools on older priors, N600 has 50 tasks with 728 positive nodes by row hash, and H has 14,700 nodes on `models-coverf`. A new choice steer landed after N600 ran, so a live arm's pool can differ from each of these. The top of an hour pool may hold junk that no fit row shows. The `l_g` term corrects size and not kind.
2. **Priors and steers were in sample on every fit task.** Form shape on those tasks looks more like gold than on a held task. R120's manifest gives 8% against 45% for covered DET forms that differ from gold text. So tune can praise TS, and M-TS may fall on held tasks.
3. **Seeded rows.** S120 positives include long forms that a search rarely reaches. A model may spend rank on them. A3 and A4 read this on tune.
4. **Fixed pool.** The replay holds the pool as it was. A better pick changes what the pool holds, so the chance is one step, and a read loses 1 nat per use. A live arm can read lower or higher.
5. **Reads with no table stay out of reach.** Most uncovered forms on these tasks wait on a read that has no table, so a rank gain acts only on ready forms. Session key labels will lower that count by an amount not known yet. So the published 34 and the new set can differ, and the base can move.
6. **Rebuilt rows aren't always the run's rows.** `hour_s0 d23f8c26` has 6% of nodes with other counts in the sample, for a cause not known. The live score reads the table the search had, and the read scores the rebuilt table. The row check counts these nodes, and the read gives the numbers without them.
7. **Few and tied units.** 25 RULE pairs on 13 tasks, and two seeds of one task. Five models are read on held tasks. A band that clears a bar by a little isn't a pass of the next step.
8. **Unknown right programs.** A table of a right program that no gold revision holds is a negative in the fit and a competitor in the rank.
9. **Cost.** The budget is measured on recorded nodes on the Mac. Tables with many worlds can run far over the mean, and a live arm must read the worker's rate.
