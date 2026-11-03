# Node score arms on the worker path: design

Reader: the Sonnet agent that builds the kit, and the coordinator who runs its slow commands.

## Goal

Run three scope-pick scores on the worker path, two seeds each, on the 37 held-out tasks and the 13 fold tasks, at 600 s:

| Arm | Score of a node | Source |
|---|---|---|
| bundle | Today's ship score: the hand model `policy/policy_model.pkl` (sha256 2ec93ed1), through today's code | The kit `search-wrapper-kit-e8c1b7882` |
| mt | M-T: `0.5 * sum(m.predict(x))`, x = the 153 table facts of `names_T()` | `F/final-models/mt.json`, `F/fit-out/mt-fall.state.pkl` (sha256 916864da) |
| depth | C-depth: `0.5 * sum(m.predict(x))`, x = `dp_form_depth`, `dp_form_reads`, `dp_kind` | `F/final-models/cdepth.json`, `F/fit-out/cdepth-fall.state.pkl` (sha256 d9be3226) |

The measures are forms covered and Ident-only forms covered. The chance per opening at the top ranks goes beside them.

## Paths

- `F` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-rank-model-train-read-hour13-heldout37/`
- `SW` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/`
- `BASEKIT` = `SW/kits/search-wrapper-kit-e8c1b7882.tar.gz`, sha256 starts `4853a24a9291f7dd39f03f0b`. Its jobs: `SW/kits/search-wrapper-jobs-heldout50-2seeds-600s.txt`, 100 lines.
- `ENGPY` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python`. Python 3.13, sklearn 1.6.1, scipy. The Mac runtime path is `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-ba0754492/py313-path`.
- `PLAIN` = `/Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python -I`, for scripts that read records and need no engine.
- `RUN` = the run folder that the coordinator names, under `SW/runs/`. Proposed names: kit `search-node-score-kit-e8c1b7882`, stage 1 run `search-node-score-parity-2tasks-300s-e8c1b7882`, stage 2 run `search-node-score-arms-heldout50-2seeds-600s-e8c1b7882`.

## Rules

1. Every Bash call is one command under `timeout 30`. No background commands, no sleep, no polling. A slow command goes to the coordinator with its ETA.
2. Write no test files. A check is a command or script that prints counts.
3. The bundle path runs today's statements. Every new behavior is under a setting that the bundle lines leave unset. The only changes that reach the bundle path add record lines and bank fields. They change no pick.
4. DAG invariance. No new code reads written atom order, atom index, the last atom, or `*` and `^` marks. The new feature inputs are table rows, the form's DAG depth, its count of read atoms and its kind. Today's least-used pick breaks ties by node id. This design keeps that code as it is.
5. Test outputs never reach feature code. The worker drops them before `make_policy`, and `TaskCtx` drops them again.

## Today's scope pick

1. `kaggle_worker.main` calls `superdag.make_policy(ARC_POLICY, task)`. `run3600.sh` sets `ARC_POLICY=$KIT/policy` and `POLICY_MODEL=$KIT/policy/policy_model.pkl`. On an exception, the worker prints `uniform policy:` and uses `UniformPolicy`.
2. `make_policy` puts the folder on `sys.path`, imports `policy` and returns `policy.Policy(task)`.
3. `Pool.add_form` makes each new `Node` and calls `policy.add(node)`. `add` scores a node once: `Policy.feats(node)` gives a dict of 87 facts, the dict goes into a float32 row in the order of `names` with NaN where a fact is missing, and the score is `model.decision_function(row)`. The model is the fold whose trained set lacks `task_key(task)`. All 50 kit tasks take fold 0.
4. After `add`, the worker sets `node.rows = None`. So features must be computed in `add`, at birth.
5. A later `add` of the same node, at a merge or a new reader, returns at once.
6. `superdag_search.next_slot` calls `picked_scope`, which calls `Pool.scope`, which calls `policy.scope(6, pool.rng)`. `scope` takes the top 5 of `score - USES*uses - log(-log(r))`, with `USES` 1, and 1 pick of least uses, ties by node id. Each pick's uses go up by 1. `Pool.scope` adds ancestors up to 96 forms.
7. `kaggle_worker.write_bank` pickles `vars(policy)` without the names in `POLICY_FIXED = ('names', 'ix', 'model', 'pairs', 'scope')`. `read_bank` puts the saved state back after the new process makes its Policy.

The master copy `SW/poolsearch/` is older than the kit. It lacks the order-free `table_key` and the `scoped` field. Build from `BASEKIT`, not from master.

## The setting and the file format

### Settings

| Variable | Value | Effect |
|---|---|---|
| `NODE_SCORE` | Path of a node score file | `policy.Policy` becomes the node score class. Unset: today's class |
| `NODE_SCORE_CHECK` | `1` | With `NODE_SCORE`, the policy also scores each node with the hand model at `POLICY_MODEL`, and compares scores and picks. For the parity check only |
| `NODE_SCORE_DUMP` | Path of a JSONL file | With `NODE_SCORE`, the policy writes each scored node's row and score. For the Mac node check only |

A job line sets `NODE_SCORE=$PWD/scores/mt.npz`. The job lines run from the kit's top folder, as `SEARCH_GOLD2=$PWD/...` does today. `run3600.sh` needs no change, since `env` passes the job line's variables through.

### Node score file

One `.npz` file, read with `numpy.load(path, allow_pickle=False)`. The pod needs numpy only to read it.

| Key | Type | Content |
|---|---|---|
| `card` | 0-d str | JSON: `format` (`node-score-trees-1`), `name`, `features` (`H`, `T` or `D`), `names` (input order), `t`, `source` (path), `source_sha256`, `folds` (a list, one list of trained task keys per fold) |
| `kK_roots` | int64 [trees] | Index of each tree's root in the flat arrays of fold K |
| `kK_feat` | int32 [nodes] | Feature index of a split |
| `kK_thr` | float64 | `num_threshold` |
| `kK_mgl` | uint8 | `missing_go_to_left` |
| `kK_leaf` | uint8 | `is_leaf` |
| `kK_left`, `kK_right` | int32 | Child index, absolute in the flat arrays |
| `kK_val` | float64 | Leaf value |
| `kK_tbase` | float64 [trees] | Value added with each tree's leaf |
| `kK_base0` | 0-d float64 | Start value of the sum |

Score of a row x, for fold K. This gives sklearn's float order, so the result is equal bit for bit:

1. Round each fact to float32, then to a Python float. NaN stays NaN. This is the cast that today's `add` and the fit rows make.
2. `s = base0`.
3. For each tree m in order: walk from `roots[m]`. At a split, if x[feat] is NaN, go left when `mgl`, else right. Otherwise go left when `x[feat] <= thr`. At the leaf, `s += tbase[m] + val[leaf]`.
4. Score = `t * s`.

Hold the arrays as Python lists at load, so the walk does no numpy scalar work.

What the converter writes per source:

| Source | `base0` | `tbase` | `t` | `folds` |
|---|---|---|---|---|
| Hand model, `HistGradientBoostingClassifier` per fold | `_baseline_prediction` | 0 for every tree | 1.0 | The two trained sets of the bundle |
| M-T and C-depth, `(models, rounds)` with 150 `HistGradientBoostingRegressor` | 0.0 | each model's `_baseline_prediction` | The card's `t` | One fold, trained set empty |

Sklearn adds `0 + baseline`, then the tree's value, per call. Features-worker's score adds the 150 calls in order from 0. Steps 2 and 3 do the same adds in the same order.

### The sklearn question

1. The repo doesn't record the pod venv's sklearn version.
2. The pod has a sklearn that loads 1.6.1 tree pickles. The hand model and the `models-final` steer pickles are 1.6.1. The 100 jobs of `search-wrapper-heldout50-2seeds-600s-e8c1b7882` have no `uniform policy` line and no `steers off` line.
3. sklearn needs scipy, so the pod has scipy too. `features_node_feats.py` imports `scipy.ndimage`. Stage 1 confirms this on the pod.
4. `forest.py` itself needs sklearn objects, since `Forest(models)` reads `m._predictors`. The kit avoids sklearn for the new scores only if the arrays are saved on the Mac and the pod reads only the arrays. This design does that.
5. The kit doesn't need to carry sklearn. The pod still uses its own sklearn for the steers and for `NODE_SCORE_CHECK`, as today.
6. `Forest.predict_one` adds the leaf values with numpy's `sum`, so its float order differs from sklearn's. The walk above replaces it.

## Code changes

### New: `kit/policy/nodescore.py`

`policy_class(Hand, hand_bundle)` gives a subclass `NodeScorePolicy(Hand)`.

`__init__(self, task)`:

1. Load the file of `NODE_SCORE`. Choose the fold by today's rule, with `Hand`'s module function `task_key`.
2. Set `self.names` and `self.ix` from the card. Put a `Scorer` object in `self.model`. It holds the tree lists, `t`, the features, the task context, the pool once bound, and the check model. `model` is in `POLICY_FIXED`, so none of this goes into the bank.
3. Set the attributes that today's class pickles: `nodes = {}`, `score = {}`, `uses = {}`, `ids = []`, `score2 = {}`, `b2 = None`.
4. Set `ns_errors = 0`, `ns_ms = []` (ms per scored node), and, with the check, `ns_alt = {}` and `ns_check = dict(nodes=0, differ=0, max_abs=0.0, openings=0, open_differ=0)`.
5. For `H`: `self.pairs = [Pair(...)]`, as today. For `T`: put `F`'s modules' folder on `sys.path`, import `features_node_feats as FE`, and store `FE.TaskCtx(task)` in the Scorer. Check that the card's names equal `FE.names_T()`. For `D`: import nothing. Check that the names equal `['dp_form_depth', 'dp_form_reads', 'dp_kind']`.
6. With `NODE_SCORE_CHECK`, load the hand bundle with `hand_bundle()` and choose its fold as today.
7. Print one line: `node score: name=<name> features=<H|T|D> sha256_8=<file hash> t=<t> fold=<K> trees=<n> check=<0|1>`.

A failure in `__init__` must raise. The worker then prints `uniform policy:`, and the read marks the job invalid.

`bind(self, pool)`: store the pool in the Scorer.

`add(self, node)`:

1. If `node.id` is in `score`, return.
2. Start a timer with `time.perf_counter()`.
3. Make the row:
   - `H`: `d = Hand.feats(self, node)`, as today's `add` does.
   - `T`: `form = pool.forms[node.form]`, then `d = FE.node_features(node.table_types, node.rows, node.clause, form.kind, form.depth, form.reads, ctx, with_shape=False)`.
   - `D`: `form = pool.forms[node.form]`, then `d = {'dp_form_depth': form.depth, 'dp_form_reads': form.reads, 'dp_kind': {'DET': 0, 'RULE': 1, 'INIT': 2}.get(form.kind, 3)}`.
   - `x = [d.get(n, nan) for n in names]`.
4. On an exception in step 3, use an all-NaN row, add 1 to `ns_errors`, and print the first 3 errors.
5. `score[node.id] = walk(x)`.
6. With the check, `ns_alt[node.id] = hand.decision_function(row)`, with the row made as today. Compare it with the score bit for bit, and update `ns_check`.
7. `uses[node.id] = 0`, `ids.append(node.id)`, and append the timer's ms to `ns_ms`.
8. With `NODE_SCORE_DUMP`, append `{node, x, score}` to the dump file, with null for NaN.

`Form.depth` is the depth at birth. `Form.reads` is `len(run.reads)` at the clause. `Pool.add_form` stores the form in `pool.forms` before it calls `add`.

`scope(self, k, rng)`:

1. Without the check, do nothing new: inherit `Hand.scope`.
2. With the check:
   1. Save `rng.getstate()`.
   2. Compute the picks from `ns_alt`, `uses` and `ids` with a copy of the rng in that state. Use a function that repeats `Hand.scope`'s statements and changes no uses.
   3. Call `Hand.scope(self, k, rng)` for the real picks.
   4. Compare the two lists, and update `ns_check['openings']` and `ns_check['open_differ']`.

### `kit/policy/policy.py`

Append this, and change nothing above it:

```python
HandPolicy = Policy
if os.environ.get('NODE_SCORE'):
    import nodescore
    Policy = nodescore.policy_class(HandPolicy, bundle)
```

### `kit/policy/fe/`

Copy these files from `F` byte for byte, and record their sha256 in the kit manifest: `features_node_feats.py` (b81a558e), `features_node_read.py` (15b0cc50), `features_node_shape.py` (92e2ac6c), `vocab.json` (91276916).

### `kit/scores/`

Put `ship.npz`, `mt.npz` and `depth.npz` here, made by the converter.

### `kit/model/study/sampler/superdag_search.py`

1. `pool_init`: after `POOL[:] = [self]`, add `getattr(self.policy, 'bind', lambda pool: None)(self)`. Today's class has no `bind`.
2. `picked_scope`: after `self.scope()` returns, call `self.event(dict(event='picks', picks=list(self.picks), n=len(self.policy.ids), draw=self.draws))`. Each scope call is one opening, and this includes a scope that a visit then refuses.

### `kit/model/study/sampler/kaggle_worker.py`

1. At module level: `PROC = '%x-%x' % (os.getpid(), time.time_ns())`, and `PICKS = [0]`. A process started by `execv` imports the module again, so it gets a new `PROC`.
2. `event`: the `cover` line gets `node=x['node']` and `proc=PROC`. A new `picks` event writes `{proc, seq, draw, n, picks, time}` to `<out>.picks`, with `seq = PICKS[0]`, and then `PICKS[0] += 1`. Open the file beside `.cover`.
3. `read_bank`: on success, `pool.lineage = state.get('lineage', [])`. On every other path, `pool.lineage = []`.
4. In `main`, after `read_bank`: `pool.lineage.append(dict(proc=PROC, draws0=pool.draws, nodes0=len(pool.nodes), nodes1=len(pool.nodes), picks1=0))`.
5. `write_bank`: before the pickle, `pool.lineage[-1].update(nodes1=len(pool.nodes), picks1=PICKS[0])`, and add `lineage=pool.lineage` to the state.

`poolrun.py` and the other bank readers read keys by name, so the added key breaks none of them.

## The node features and their cost

### Inputs at the node

| Input | Live value | Value in the fit and held read rows |
|---|---|---|
| `types` | `node.table_types`, `[str(t) for t in tb['types']]` | The same, from the rebuilt table |
| `x_rows` | `node.rows`, `S.rows_with_models(tb, S.X_ROWS_CAP)`, cap 2000 | The same, from rebuilt rows |
| `clause` | `node.clause`, the form's text | The same |
| `kind` | `form.kind` | N600, H, B: `fo.kind`. R120, S120: from the clause text, which gives the same kind |
| `form_depth` | `form.depth` | `fo.depth` |
| `form_reads` | `form.reads` | N600, H, B: `fo.reads`. S120: the count of `(&fN` atoms in the clause |
| `ctx` | `FE.TaskCtx(task)`, made once in `__init__` | The same |

`form.reads` counts every atom that reads a relation, `input` too. The `(&fN` count counts only reads of forms. The two differ on 1,124 of the 2,075 forms of the bank `dagb_s0/135a2760` of the wrapper run. The held read scored rows with `fo.reads`, so the kit uses `form.reads`. Features-worker must confirm this. It matters most for depth, where it is one of the 3 inputs.

The kit calls `node_features` with `with_shape=False` for `T`. That skips form shape, which `names_T()` doesn't read. The Mac node check compares with the rebuild's call, which has `with_shape=True`.

### Cost per node

These figures are Features-worker's, measured on the Mac on R120 nodes, for features and model together:

| Score | Mean | q99 | Source |
|---|---|---|---|
| Ship, today | about 1.4 ms (features .93, model .45) | features 13.9 | `features-node-rank-model-design/design.md`, Cost |
| M-T, forest | 1.41 ms | 9.22 | `F/final-models/mt.json` `cost` |
| Depth | not measured; no table read, one walk of 150 trees | | |

1. The cost lands in `Pool.add_form`, inside `Pool.take`, inside `try_clause`. The worker counts it in `search:seconds take` and `search:seconds new`.
2. A visit ends at `SEARCH_VISIT_SECONDS` (4 s) and the job ends at 600 s. So a costlier score gives fewer tries per job. It doesn't stall the worker.
3. A pod is about 3 times slower than the Mac. M-T is then about 4 ms mean and 28 ms q99 on the pod.
4. A 600 s job makes about 2,800 nodes, so a node takes about 210 ms of worker time. M-T and depth take about 2% of it, about the same as today's score.
5. The walk of this design replaces `Forest.predict_one`, so its cost is not measured. The runs record it in `ns_ms`. Stage 1 gates on Features-worker's budget: mean at most 24 ms and q99 at most 60 ms on the pod.
6. `T` and `D` keep no link state. Their bank `policy.nodes` stays empty.

## Checks before the launch

### Converter check (Mac, `ENGPY`)

The converter is `search_node_score_make.py SOURCE KIND NAME OUT ROWS`. It writes the file and prints the check.

- Inputs: the hand bundle, `mt-fall.state.pkl`, `cdepth-fall.state.pkl`, with their sha256 checked against the values in [Goal](#goal). Rows: 2,000 rows taken from 4 part files of `F/base-rows/`. Use the `H` matrix for ship, and the columns of `X` by name for M-T and depth. Add 200 more rows with 30% of the entries set to NaN, from a fixed seed.
- Compare: the walk against the reference. For ship, the reference is `clf.decision_function(row)` for each fold. For M-T and depth, it is `t * sum(m.predict(row) for m in models)`.
- Pass: every row is equal bit for bit, the card's names equal `names_T()` or `names_depth()`, no tree has a categorical split, and every model has one tree per iteration.

### Parity check: ship under the new path

This uses the ship model, so it needs no new feature code. The parity script is `search_node_score_parity.py OUT`. It reads each job's final bank and log.

| Item | Pass |
|---|---|
| Marker | The log has the `node score:` line, with `name=ship`, `fold=0`, `check=1` |
| Fallbacks | No `uniform policy`, `steers off` or `bank not written` line |
| Nodes | `ns_check['nodes']` at least 500, `differ` 0 |
| Picks | `ns_check['openings']` at least 50, `open_differ` 0 |
| Errors | `ns_errors` 0 |
| Cost | Mean and q99 of `ns_ms`, printed |

All jobs pass, or the launch waits. On a fail, the script prints the first differing node's two scores and both pick lists.

These items prove the same picks pick for pick:

1. Every node's score from the new path equals the hand model's score bit for bit.
2. Both picks come from today's `scope` statements, run on the same `uses`, `ids` and rng state.

### Node check: M-T and depth at the node (Mac)

The node check script is `search_node_score_nodecheck.py OUT`, run on `ENGPY`. Each job ran with `NODE_SCORE_DUMP`, and with `ARC_RECORD` for node records.

1. For each dumped node in the final bank: read its record's `table_types`, `x_rows` and `clause`, and its bank form's `kind`, `depth` and `reads`.
2. Compute `FE.node_features(...)` with `with_shape=True`, as `F/features_node_rebuild.py` lines 180 to 183 do. For depth, read the 3 facts from the form.
3. Compare: the row against the dumped row, with NaN equal to NaN. The reference score on the dumped row against the bank's `policy.score`.
4. Pass: 0 rows differ and 0 scores differ, on at least 300 nodes per job. If rows differ, print the names of the differing facts. A JSON round trip of `x_rows` can turn tuples into lists, so one fact class may differ for that cause alone. Report it before you change anything.

## Measures

### Definitions from gold's text

For task t, gold is the `gold_sexp` of t in the kit's `points-eval.json` (`gold-v3-cuts-final-round52`, view-final after round 55).

- **Gold forms** of t: the non-empty lines of gold that don't start with `(OUT`, numbered from 0 in text order. A cover line's `gold` is this number.
- **Kind** of form g: the first word of its line, without `(`. DET is `DET` or `RIGID_DET`. Every other kind is non-DET.
- **Reads** of form g: the gold forms whose `&rN` names occur in g's line after its head name. This is the code of `F/features_node_rebuild.py` lines 107 to 111.
- **Ident-only form**:
  1. Replay gold's forms of t in one session, as `superdag.gold_keys` does: `run.scope(forms)` with `run.collect` on.
  2. Form g's tables are the parsed tables of `relation_tables(run.collect[g])`.
  3. Form g is Ident-only when it has at least one table, and each of its tables has at least one column whose type, as `str`, is `Ident`.

  Port names don't name types: `:Id` is a label, and `:Key` can hold an Ident. So gold's text decides this only through the replay. The script `search_node_score_gold_ident.py` writes `gold-ident-only-kit50.json` with `{task: {ident_only: [g], no_table: [g], forms: N}}`. It runs on the Mac runtime with `ARCLOG_IDENT_SOURCE=value`. Column types don't depend on the Ident source, so the runtime's version doesn't change the set. On other gold revisions, Features-worker counted 30 of 178 forms on the 13 and 474 of 1,331 on the 37 with only Ident tables.

### Forms covered

1. A job counts when its `work/<t>.log` has an `end:` line. Count the others as open, as `SW/search_wrapper_report.py` does.
2. `covered(job)` is the set of `gold` values over all lines of `work/<t>.out.jsonl.cover`.
3. Count it all, DET, non-DET, and Ident-only, where Ident-only is `covered ∩ ident_only(t)`.
4. Per arm and task set, the figure is the mean over the 2 seeds of the sum over tasks.
5. Δ for an arm is that figure less the bundle's figure, in the same batch. Its 90% band comes from 10,000 resamples of tasks, each resample taking a task's mean over seeds for both arms.

All cover lines count, with lines from a process that died before its bank write. This is the old report's rule, so the bundle figure compares with older runs on the same gold. `gold_keys` gives a key its first form only, so a form whose table equals an earlier form's table is never counted.

### Chance per opening at the top ranks

Inputs per job: the final bank (`forms`, `nodes`, `draws`, `policy.score`, `policy.uses`, `lineage`), `.picks`, `.cover`, and gold.

1. **Kept picks.** For lineage entry i, keep the `.picks` lines with `proc` equal to its `proc` and `seq < picks1`. Put them in lineage order, then in `seq` order. The j-th kept line is opening j.
2. **Uses check.** Count each node over the kept picks. The count must equal the bank's `policy.uses` for every node. A job that fails this is left out of this measure and counted.
3. **Kept covers.** Keep the cover lines with `proc` equal to entry i's `proc` and `nodes0 ≤ node < nodes1`. `own[q]` is the set of kept nodes of gold form q. `first[q]` is the least `age` over `own[q]`.
4. **Reach.** Bank form f reaches q when f or one of its ancestors, by `forms[f].parents`, holds a node of `own[q]`. Node i reaches q when its form does.
5. **Ready form-run.** Form h with reads R, all of R with `first`. `d_ready = max over R of first[q]`. `d_end = first[h]` if h has kept covers, else the bank's `draws`. A form-run is ready when `d_end > d_ready`.
6. **Openings of h.** The kept picks with `d_ready ≤ draw < d_end`.
7. **Chance at opening j.**
   1. Let n be the line's `n` and `u` the uses before j.
   2. `x = score[:n] - u[:n]` and `w = exp(x - max x)`.
   3. `c = solve_c(w)`, the race form of 5 scored picks.
   4. The least-used pick is the line's 6th pick, if it has one. Drop the reads it reaches.
   5. `p_j = p_all(masses, c, 0)` over the reads left, where masses come from `need_masses` over the nodes that reach them.
   6. Copy `solve_c`, `p_all` and `need_masses` from `F/sampler-ready-forms.py`. With no read left, `p_j = 1`.
8. **Held at opening j.** All of R are reached by the forms of the line's picks.
9. **Rank of read q at the window's last opening.** `1 + |{i < n : x_i > max over own[q] of x}|`.

Per arm and task set:

- **C1**: the median over ready form-runs of the mean of `p_j` over the form-run's openings. This is Features-worker's M1, with labels from the run's own session keys, at every opening.
- **C1-held**: the median over ready form-runs of the share of openings that held R.
- **C3**: the share of ready form-runs with that mean at .1 or more.
- **R-RULE**: the median rank of RULE reads at the window's last opening.
- **n**: the counts of ready form-runs, of jobs left out by the uses check, and of form-runs with no opening.

The pools of the arms differ, so these figures aren't paired by form. Give each with its n.

### Validity of a job

A job is read when its log has `end:`, has no `uniform policy` or `steers off` line, and has the `node score:` line with the arm's name (none for the bundle). Its `ns_errors` must be at most .1% of its nodes. Print per arm: deaths and kills from `supervisor.log`, the mean and q99 of `ns_ms`, and `search:seconds take` per kept node.

## Job lines

Make each bundle line from a line of `BASEKIT`'s jobs file. Change `ARCLOG_IDENT_SOURCE=type` to `ARCLOG_IDENT_SOURCE=value`, and the arm `dagb` to `bundle` and `dagbf` to `bundlef`. Each `mt` and `depth` line is its bundle line with `NODE_SCORE=$PWD/scores/<name>.npz` added before `./run3600.sh`, and its arm renamed.

```
SAME_POD=135a2760 ARCLOG_IDENT_SOURCE=value P_DAG=1 ARC_SESSION_SHARE=.9 SEARCH_LIMIT_SHARE=.65 ONE_REPAIR=30 CHOOSE_LIFT=0 SEARCH_LOG_VISITS=1 SEARCH_GOLD2=$PWD/points-round50.json ./run3600.sh 135a2760 bundle_s0 models-final 600
SAME_POD=135a2760 ARCLOG_IDENT_SOURCE=value P_DAG=1 ARC_SEED_BASE=1000 ARC_SESSION_SHARE=.9 SEARCH_LIMIT_SHARE=.65 ONE_REPAIR=30 CHOOSE_LIFT=0 SEARCH_LOG_VISITS=1 SEARCH_GOLD2=$PWD/points-round50.json NODE_SCORE=$PWD/scores/mt.npz ./run3600.sh 135a2760 mt_s1 models-final 600
SAME_POD=74dd1130 ARCLOG_IDENT_SOURCE=value P_DAG=1 ARC_SESSION_SHARE=.9 SEARCH_LIMIT_SHARE=.65 ONE_REPAIR=30 CHOOSE_LIFT=0 SEARCH_LOG_VISITS=1 SEARCH_GOLD2=$PWD/points-round50.json NODE_SCORE=$PWD/scores/depth.npz ./run3600.sh 74dd1130 depthf_s0 models-finalf 600
```

| Arm | Tasks | Models | Seed base | Lines |
|---|---|---|---|---|
| `bundle_s0`, `bundle_s1` | the 37 | `models-final` | 0, 1000 | 74 |
| `bundlef_s0`, `bundlef_s1` | the 13 | `models-finalf` | 0, 1000 | 26 |
| `mt_s0`, `mt_s1`, `mtf_s0`, `mtf_s1` | as the bundle | as the bundle | as the bundle | 100 |
| `depth_s0`, `depth_s1`, `depthf_s0`, `depthf_s1` | as the bundle | as the bundle | as the bundle | 100 |

Stage 2 has 300 lines, in task order, with the 6 lines of a task together. `SAME_POD` keeps a task's lines on one pod, so the arms of a task share a pod's load. The budget is about 50 CPU h at 600 s a line, 3 times the wrapper run.

Stage 1 has 6 lines at 300 s:

- 4 parity lines: `135a2760` with `models-final` and `74dd1130` with `models-finalf`, seeds 0 and 1000. Each takes `NODE_SCORE=$PWD/scores/ship.npz NODE_SCORE_CHECK=1`. Arms `parity_s0`, `parity_s1`, `parityf_s0`, `parityf_s1`.
- 1 `mt` line and 1 `depth` line on `135a2760`, seed 0. These confirm the imports, scipy, the marker and the cost on the pod.

The Mac check has 3 jobs at 120 s on `135a2760`, run with `PY=ENGPY` and `EXTRA_PATH` set to the Mac runtime path. One is the ship parity job. The other two are `mt` and `depth` with `NODE_SCORE_DUMP=<out>/dump.jsonl` and `ARC_RECORD=<out>/rec`.

## Prediction and decision rule

This is the text for the run manifest. Write it before stage 2 starts, with `date -u`.

```json
"prediction": {
  "written": "<date -u>, before any stage 2 job",
  "basis": "Features-worker's held read on the fixed pools of B (37 tasks, session labels): median chance per opening over 124 ready form-runs, hand .00373, C-depth .0182 (4.88x, band 1.12 to 22.6), M-T .0418 (11.2x, band 3.19 to 46.4) (F/read-out/*.results.txt). On H at 600 s: C-depth 6.85x, M-T 9.4x. The same read gives forms that the hand score covered a median chance of .542, M-T .272, C-depth .137. So a live arm can lose some forms that the hand score finds now. The read holds the pool fixed, and live picks change the pool.",
  "forms_covered_37": "M-T minus bundle, mean of two seeds: +3 to +25. Depth minus bundle: -12 to +10.",
  "forms_covered_13": "M-T: -4 to +6. Depth: -6 to +4.",
  "det_37": "both arms within 4 of the bundle",
  "ident_only_37": "M-T: 0 to +6. Depth: -3 to +3.",
  "chance_per_opening": "live C1: M-T 3 times the bundle's or more; depth 1.5 to 5 times",
  "cost": "M-T and depth: search:seconds take per kept node within 10% of the bundle's; ns_ms mean under 24 ms on the pod",
  "right_on_test": "0 to 1 task for each arm"
},
"decision_rule": {
  "written": "<date -u>, before any stage 2 job",
  "measure": "D = (mean over seeds of forms covered, summed over the 37 tasks) for the arm, less the same for the bundle of this run. Band: 90%, 10,000 task resamples, paired by task. D13, DET D and Ident-only D likewise. Only valid jobs count, and a task counts only where all 6 of its jobs are valid.",
  "rules": [
    "1. The bundle takes M-T when the low end of D's band is above 0, D13 is -3 or more, and DET D is -3 or more.",
    "2. If depth meets rule 1 too, and the band of M-T's D less depth's D holds 0, the bundle takes depth in place of M-T. Depth needs no table facts and no scipy, and the note says that M-T's table facts gave no live gain over depth.",
    "3. An arm whose band has its high end below 0 is worse, and is dropped.",
    "4. An arm that meets no rule above, with a band low end above 0 for Ident-only D, goes to the coordinator for a second batch. No change to the bundle.",
    "5. Otherwise the bundle stays as it is. If the arm's live C1 is 3 times the bundle's or more, the block is past the scope pick, in the search's kind or clauses. If live C1 is under 3 times the bundle's, the fixed-pool read didn't carry to live pools. Either note goes to Features-worker."
  ]
}
```

Other manifest fields: `name`, `alias`, `kit`, `kit_sha256_24`, `jobs`, `commit` (the base kit, with the changes of [Code changes](#code-changes)), `wheel_engine` (commit e8c1b7882, sha256 `bcb74793501090b9ffed3e356777288de608271feede3fe86a8fce5b94483c87`, pod), `gold` (`kit/points-eval.json`, sha256_8 `6478ea4e`), `task_set`, `budget`, `arms`, `node_score_files` (each file's sha256, its source's sha256, its card's `t` and names count), `measures`, `parity` (the stage 1 run's name and result), `node_records: none`, `training_eligible` (the 37 are held out, and the 13 are a fold under `models-finalf`; the run feeds no fit), `start`.

## Steps for the Sonnet agent

Steps 1 to 7 come before the launch, in this order. Steps 8 and 9 can run while stage 2 runs.

1. **Unpack the base kit.** Extract `BASEKIT` into a new scratchpad folder.
   - Check: the tar's sha256 starts `4853a24a9291f7dd39f03f0b`, and `kit/policy/policy_model.pkl` starts `2ec93ed1`.
2. **Converter and score files.** Write `search_node_score_make.py` by [Node score file](#node-score-file), and run it on `ENGPY` for ship, mt and depth into `kit/scores/`. Each run is one call under 30 s.
   - Check: the converter check passes for all three. Print each file's sha256.
3. **Policy code.** Write `kit/policy/nodescore.py`, append the dispatch to `kit/policy/policy.py`, and copy `F`'s modules into `kit/policy/fe/`.
   - Check: on `ENGPY`, with `PYTHONPATH` set to the kit's policy folder and the Mac runtime, for each file: import `policy`, make `Policy(task)` for `135a2760` with test outputs removed, and print the marker. Without `NODE_SCORE`, `policy.Policy is policy.HandPolicy`. `diff` of `policy.py` against the base kit shows only the appended lines.
4. **Worker and wrapper edits.** Edit `superdag_search.py` and `kaggle_worker.py` by [Code changes](#code-changes).
   - Check: `python -m py_compile` on both files. `diff` against the base kit shows only the listed changes. `grep` shows `NODE_SCORE` read in `policy.py` and `nodescore.py` only.
5. **Mac check, a slow command.** Give the coordinator the 3 Mac jobs of [Job lines](#job-lines), at most 3 processes at once through `/Users/davidlu/code/arc-workspace/scripts/run_heavy.py`. ETA about 3 min wall, 2.9 GiB a process at most. Then run the parity script and the node check script on the output.
   - Check: the parity job passes [Parity check](#parity-check-ship-under-the-new-path). The `mt` and `depth` jobs pass [Node check](#node-check-m-t-and-depth-at-the-node-mac). Each job's `.picks` and `.cover` lines have `proc`, and its bank has `lineage`. The uses check of [Chance per opening](#chance-per-opening-at-the-top-ranks) gives 0 differing nodes. Stop on any fail.
6. **Jobs and kit.** Write the stage 1 and stage 2 job files, the kit `manifest.json` (by `work/naming.md`, listing every file the jobs read, with the new files), and the tar.
   - Check: stage 2 has 300 lines and 50 tasks, with 6 lines per task. Its bundle lines differ from the base file only in `value` and the arm names. Its `mt` and `depth` lines differ from their bundle lines only in `NODE_SCORE` and the arm name. Stage 1 has 6 lines.
7. **Stage 1 on the pod, a slow command.** Give the coordinator the kit and the stage 1 jobs. ETA about 6 min wall on 6 CPUs. Then run the parity script on the pulled output.
   - Check: the 4 parity jobs pass. The `mt` and `depth` jobs have the marker, no fallback line, `ns_errors` 0, `ns_ms` mean at most 24 ms and q99 at most 60 ms. On a pass, tell the coordinator at once: stage 2 can launch. Write the manifest's `prediction` and `decision_rule` with `date -u` before the launch.
8. **Ident-only forms.** Write `search_node_score_gold_ident.py SECONDS`, which resumes per task. Run it on the Mac runtime. ETA about 1 min for 50 tasks at 1.2 s a task, so give it to the coordinator.
   - Check: 50 tasks in the file. Print per task set the count of gold forms, of Ident-only forms, and of forms with no table.
9. **Read script.** Write `search_node_score_read.py OUT IDENT_FILE` by [Measures](#measures). It streams per job, resumes, and prints the tables per arm and task set, the paired bands, and the verdict by the rule.
   - Check: on the stage 1 output and on the Mac check output, it prints every measure. On stage 1's parity jobs, C1 and forms covered come out with no job left out by the uses check.

## What the design can't settle

1. **The meaning of `dp_form_reads`.** The fit mixed two meanings: `form.reads` on N600 and the count of `(&fN` atoms on S120. The kit uses `form.reads`, the held read's meaning. Features-worker must confirm. Depth has this as one of its 3 inputs, so its live score depends on the choice.
2. **The pod's sklearn version.** The repo doesn't record it. Stage 1's parity jobs compare the pod's hand `decision_function` with the walk on 1.6.1 arrays. A difference there shows a version effect. It isn't a fault of the new path.
3. **Fit rows and live rows.** The fit and the held read used rebuilt rows from a Mac session without `ARCLOG_IDENT_SOURCE=value`. The features read only which rows share an Ident, so a value-based Ident changes them only where it changes which rows share one. This design can't measure that before the run.
4. **Live pools.** The offline gains hold the pool fixed. Picks change the pool, so forms covered can move either way. This is why the rule rests on forms covered.
