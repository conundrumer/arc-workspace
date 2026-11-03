# Tower read: design

## Question
Gold programs are walked in an order that comes from the read DAG. At each step of that walk, this read measures the bits that the next form's outcome costs, where the outcome is its head shape and its read pattern on the tower. It compares these costs:

- the proposal: `Sampler.clause` of the `models-kr` bundle, with the forms present as its scope;
- tower models fit on training programs' walks, which condition on DAG facts of the forms present and on what the walk built last, without the chain state and with it.

The deliverable is the bits per form that a tower-conditioned proposal with the state saves against the proposal, with a 95% interval by task, and where on the tower the saving is: roots, chain steps, joins, top joins. It also reports the share of steps in each state, under two meanings of "extends", and a shuffled-state control.

## Record
- Record folder `R` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-heldout37-ramp22/`. Write only there.
- When the read is done, copy `R` to `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-tower-read-heldout37-ramp22/`. If your brief doesn't allow that write, hand the `cp -R` command back.
- The deliverable is `R/results.md`, with the tables of [Read](#read) and the verdict.

## Pins
Every script checks these pins at start and exits on a mismatch. `R/manifest.json` records them with the predictions.

| Pin | Value |
|---|---|
| Kit | `KIT=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-keyident-value-199853802`. Sampler folder `$KIT/model/study/sampler`. sha256 of `live.py sample2_col.py search.py superdag.py superdag_search.py live_try.py or_q.py`, concatenated in that order, starts `a5873bf24e00` |
| Engine | `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path`, `arclog/arclog.abi3.so` sha256 `b41ccf9c0567b923f04771d7b5e479172d94f30fa09e4a9b181713ec19e043a3` |
| Python | `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python -u`. Don't use `-I` |
| Models, the 37 | `$KIT/models-kr`: `live_priors.pkl` 3c859731e9d875ce, `relR4_o.pkl` 3015d409597fff42, `choice5_o.pkl` 686949ea5cc5a89f, `tilt_v1.json` ca858276d4713e92 (16 hex digits of sha256) |
| Models, the ramp | `$KIT/models-krf`: `live_priors.pkl` 7406dc3e810f5211 (the 22 ramp tasks left out), the same three steer files |
| Settings | `P_DAG=1 ORDER_FREE=col,tie,key ARCLOG_IDENT_SOURCE=value RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`. `KEY_IDENT` and `STEER_COVER` unset. Every other variable at the kit's default. This is the `dagj` control arm of the kit's manifest |
| Held gold | `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/live-gold-r1/points-eval.json`, sha256 starts `af855438abe27a5b`. The Ident-only list `gold-ident-only-refit.json` beside it, sha256 starts `08ec1bc4d836c650`. The kit's own `points-eval.json` is not used |
| Task sets | `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held/tasks.txt` (37) and `held/ramp-fold.txt` (22). Held task JSON: `$KIT/data/tasks/<task>.json` |
| Corpus gold | `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-view-final-2149/<stem>/pairs.jsonl.gz`, first row's `gold_sexp`. Stems: all, less `features-worker/arm/eval-tasks.txt` (99), less the 22 ramp tasks: 989. Corpus pin sha256 `6dc26bdd984b7c66` |
| Corpus shapes | `IB=/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-ident-block-read-heldout37-ramp22`, `$IB/corpus/rows-*.jsonl`: one row per corpus form with `stem, g, kind, shape, holds`, 21,181 rows, from a replay on the same engine. Read only. No corpus replay is needed |
| Shared code | `$IB/ib_lib.py` (parse, shapes, replay, `p_kind_of`, `jeffreys`, `draw_seed`, streaming helpers). `DAGO=/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-order-census-heldout37/features_dag_order.py`, sha256 starts `676309d44cc28c71`: `ProgramDag`, `content_keys`, `tie`, `random_order`. Both imported by path, read only |
| Walk | `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/chain-state/walk.md`, "Walk" section, round 0 |

- `models-kr` is `7dafa0ce` plus `key_rel`. With `KEY_IDENT` unset, `key_rel` has no effect. So this bundle differs from `models-tk` by `col` in `ORDER_FREE`, its `COL_TYPE` table and `choice5_o`. Name this in `results.md`.
- `relR4_o.pkl` has the ramp tasks in its train rows, so the ramp read is held out for the priors only. Name this in `results.md`.
- `tw_lib.py` sets `ib_lib`'s `KIT`, `SAMPLER_DIR`, `MODELS`, `MODEL_SHAS`, `SAMPLER_SHA` and `SETTINGS_ENV` to the values above and its `R` to `$IB`, so that `ib_lib.pins()` checks this kit and `$IB/corpus-pin.json`, then calls `ib_lib.setup()`. It also checks that `KEY_IDENT` is unset and that `features_dag_order.py` matches its pin. `probe_cost.py` in this design's folder shows the import.

## Definitions

### Forms and reads
- A program's forms are its non-empty lines that don't start with `(OUT`. `dag = ProgramDag(forms)`. A form's key is its head; `reads(f) = dag.parent_ids[f]`; `kind(f) = dag.kinds[f]`. A root form reads no form.
- A form's text index `g` (the g-th form) serves only to join a form to its shape row. No fact, choice or seed reads it.
- `depth(f)` = `dag.depths[f]`. `holds(f)`: some table of f has a column type that contains `Ident` (the corpus rows' `holds`).

### The walk
`walk(forms, seed, theta=None)` in `tw_lib.py` implements the "Walk" section of `walk.md` at round 0, with `lambda = 1`, and returns its step records. When `theta` is given, it uses `P_theta`, so later rounds of the search side's fit swap in with no other change.

1. The state at step t is the placed set S, the chain `C = (c_1, ..., c_m)` and the ready set R. At the start, S and C are empty.
2. R is sorted by `dag.tie`. Each form r in R gets its mode against C:
    - EXTEND, when m > 0 and r reads the head `h = c_m`;
    - else BACKTRACK(d), when r reads some `c_j`, j < m: the largest such j, `d = m - j`, banded `BT1`, `BT2`, `BT3+`;
    - else JUMP.
3. The cells are the pairs (mode band, kind) that R holds, sorted. Draw one cell with `rng.randrange`, then one form of that cell with `rng.randrange`. The generator is `random.Random('%d|%s' % (seed, short(''.join(sorted(dag.content[k] for k in keys)), 16)))`, as `ProgramDag.random_order` keys it.
4. EXTEND pushes f. BACKTRACK(d) cuts C to `c_1 ... c_j` and pushes f. JUMP sets `C = (f)`.
5. The head after every step is the form just placed.

`probe_cost.py` holds a draft of steps 1 to 4. Its walk of 135a2760, seed 0, has 37 steps.

### Step record
One row per step, with the columns of `walk.md`: `task, seed, round (0), t, key_f, key_h ('' with no head), m (before the step), mode, d, kind_h, kind_f, nR, R_modes (counts in R by mode band), n_reads, n_root_reads, logw`. `logw` is `sum_t log2(Z_t)`, with `Z_t` = (cells that R holds) / 20, the same on each row of a walk. The read adds `g`, `walk_bits` = `log2(cells in R) + log2(forms in the cell)` (the bits of the walk's own choice), the facts, the place and the outcome below.

### State
- The state at step t is `prev` = the mode of step t − 1, `START` at t = 0.
- Meaning A, "extends the form just built": `prev = EXTEND`.
- Meaning B, "reads a form on the current chain": `prev` is EXTEND or a BACKTRACK band.
- Full: `prev` with its band: EXTEND, BT1, BT2, BT3+, JUMP, START.
- The shares of steps in each state are counted over steps t ≥ 1, by set.

### Outcome
The outcome of step t is `Y = (shape, pattern)` of the form f that the walk placed.

- `shape` = `ib_lib.shape_tabs`: `kind|I|K`, as in the Ident read.
- `pattern(f, state)` counts f's reads by their place on the tower at step t. It is a function of the read set and the state only, so it applies to gold's form and to a drawn clause alike:
    - `mode6`: EXTEND, BT1, BT2, BT3+, JUMP0 (reads no form), JUMP+ (reads forms, none on C). This is walk.md's mode, with JUMP split.
    - `stack_more`: reads of further chain elements, past the one that set the mode: 0, 1+.
    - `open`: reads of forms off C that no form of S reads: 0, 1, 2+.
    - `inner`: reads of forms off C that some form of S reads: 0, 1, 2+.
    - `roots`: reads of root forms, anywhere: 0, 1+.
- The pattern space has 216 values. A drawn clause's read set is the set of scope heads among `NAME.findall(clause.text)`. `clause_of` writes scope forms by their written heads.

### Place of a form
For gold's form f, by the whole program's DAG:

| Place | Rule |
|---|---|
| root | f reads no form |
| chain step | f reads one form |
| join | f reads two or more forms, and some form reads f |
| top join | f reads two or more forms, and no form reads f |

Each table by place is also split by f's own mode: EXTEND, BACKTRACK, JUMP.

### Tower facts
Each fact reads S as a DAG, the kinds, `holds`, and the walk so far. No fact reads R, which holds gold's future, nor text order, atom order, a place in a body, binder marks or `&rN` numbers.

| Group | Fact | Values |
|---|---|---|
| set (S as a DAG) | `n_present` | 0, 1-2, 3-5, 6-11, 12+ |
| | `n_open`: forms of S that no form of S reads | 0, 1, 2, 3-4, 5+ |
| | `ident_open`: an open form holds Ident | 0, 1 |
| | `maxdepth`: largest depth in S | -, 0, 1, 2, 3-5, 6+ |
| last built (the head h) | `h_kind` | RULE, DET, INIT, other, none |
| | `h_ident`: h holds Ident | 0, 1 |
| | `h_nreads` | 0, 1, 2+ |
| | `h_depth` | 0, 1, 2, 3-5, 6+ |
| chain state | `prev` | as in [State](#state) |
| | `m_band`: chain length before the step | 0, 1, 2, 3-4, 5+ |
| | `chain_roots`: root forms on C | 0, 1, 2+ |

## Rates

### Tower models
Each model is `P(Y | x) = P(shape | x) · P(pattern | kind, I≥1, x)`, with I≥1 read from the shape.

Each factor is a count table along a backoff chain of cells, with each level smoothed toward the next coarser one:
`p_l(y | c) = (n_l(c, y) + alpha · p_{l+1}(y | c')) / (n_l(c) + alpha)`. The last level is `()`, smoothed toward `(n(y) + .5) / (N + .5 V)`. V is the corpus shapes plus `<unseen>` for the shape factor, and the 216 patterns for the pattern factor.

| Model | Shape chain (finest first) |
|---|---|
| M0, set | (n_present, n_open, ident_open, maxdepth) → (n_open, ident_open) → (ident_open) → () |
| M1, set and last built | (h_kind, h_ident, h_nreads, h_depth, n_present, n_open, ident_open, maxdepth) → (h_kind, h_ident, h_nreads, n_open, ident_open) → (h_kind, h_ident, ident_open) → (ident_open) → () |
| M2A | each M1 level with `prev = EXTEND` put first, then (state) → () |
| M2B | the same with `prev ∈ {EXTEND, BT}` |
| M2M | the same with `prev` in full |
| M3 | the same with (prev, m_band, chain_roots), then (prev) → () |

- The pattern chain of each model is its shape chain with (kind, I≥1) put first at each level, then (kind) → ().
- M2A, M2B and M2M split every M1 cell by the state, so the state's gain is M1 − M2 on the same chain.
- `alpha` per model and factor is chosen from {0.5, 2, 8, 32, 128} by 5-fold cross-validation over corpus stems, with the fold `int(sha1(stem)[:8], 16) % 5`, on corpus walks only.
- Fit rows: the corpus walks, seeds 0 to 3, every step. That is about 989 × 4 × 21 ≈ 84,000 steps. Seeds give equal weight.
- Forms of kind OTHER keep their rows in the fit. They are left out of every bits figure on held tasks and counted.
- Held tasks never enter a fit: `tw_fit.py` asserts that no fit stem is in the 99 eval tasks or the ramp, and records the count of stems that it fit on.

### The proposal's rate
The rate is exact for the kind and sampled within the kind, as in the Ident read.

- Scope at step t: the forms of S. Batch 0 gives them in the walk's order. Batch b ≥ 1 gives them in `dag.random_order(b, keys=S)`. So the rate is an average over valid orders of the set.
- `P_kind` = `ib_lib.p_kind_of(sampler, texts, kind)`. A gold kind that the scope doesn't admit, or that is outside `KIND_TOK`, gets `P_kind = 0`. Such a step is counted and left out of the bits.
- Draws: `sampler.clause(sess, seed, time.monotonic() + 20, d, texts, kind)` with gold's kind, on `live.Sampler(models)`. A `None` counts as a try with no outcome. Draw seed i of step t is `int(sha1(f'{task} {key_f} {i}').hexdigest()[:12], 16)`.
- For each draw, take its within-kind shape `(I, K)` with `shape_of(kind, c.text, c.tables)` and its pattern at the step's state. Count `h_joint` (gold's `(I, K)` and pattern), `h_shape` and `h_pattern`, over n tries.
- `p_prop(Y) = P_kind · (h_joint + .5) / (n + 1)`. The shape part is `P_kind · (h_shape + .5) / (n + 1)`, and the pattern part is the joint over the shape part.
- Stopping rule, per step: draw in batches of 32. Stop when `h_joint ≥ 8`, at n = 128, or at 45 CPU s for the step.
- Where `h_joint = 0`, `p_prop` is an upper bound of a rate the read can't see. Then the proposal's bits are a lower bound and the saving at that step is a lower bound. The read counts these steps and gives the saving with them left out too.

### Cost measured on one task
`probe_cost.py` in this design's folder, on 135a2760 under the pins, walk seed 0, 24 draws a step (not part of the read):

- Setup (imports, Sampler, session): 1.3 s.
- Step 12, a RULE at a 12-form scope: .13 CPU s a draw, 3.2 s wall for 24 draws, scope replay included.
- Step 30, an INIT at a 30-form scope: .38 CPU s a draw, 9.2 s wall.
- So a step costs about 5 s (32 draws at a small scope) to 45 s (the cap). The mean is about 20 s. The held steps are about 1,770: 1,429 forms on the 37 and 343 on the ramp.

## Steps read
- The proposal reads the walk of seed 0 only.
- Pass 1, per task: up to 12 steps. Group the steps by stratum (place, f's mode as EXTEND, BACKTRACK or JUMP), shuffle each stratum with `random.Random(f'{task} pass1')`, and take steps from the strata in turn. That is about 690 steps.
- Pass 2: the other steps, about 1,080.
- Each done step has weight (steps in its task's stratum) / (done steps in that stratum). Tables give raw counts beside weighted figures.
- The tower models read every step of every held walk, seeds 0 to 15, at no draw cost. The comparison with the proposal uses seed 0 and the done steps, with the weights.

## Files
All scripts are in `R`. Each script streams: it appends one JSON line per unit as soon as the unit exists, flushes, prints `[done/total, s a unit, ETA]`, and skips the units already in its output on a rerun.

| File | Does |
|---|---|
| `tw_lib.py` | Pins as in [Pins](#pins), `setup()`, `walk()`, `pattern()`, `place()`, `facts()`, the model chains, the backoff tables and their scoring, `bootstrap_tasks()` |
| `tw_env.sh` | `tw_env.sh CPUS SCRIPT ARGS`: exports the settings and `PY`, unsets `KEY_IDENT` and `STEER_COVER`, and runs `/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus CPUS --need soon` on `$PY -u R/SCRIPT ARGS` (`.py`) or `bash R/SCRIPT ARGS` (`.sh`). `tw_env.sh check` prints the pins and exits 1 on a mismatch |
| `tw_shapes.py --task T` | Replays the held gold program once on its set's models, checks the Ident-only forms against the pinned list (C1 of the Ident read), and writes `R/shapes/T.json`: `g, key, kind, shape, holds` per form |
| `tw_shapes_all.sh P` | `tw_shapes.py` on the 59 held tasks, P at a time, through `xargs -P P` |
| `tw_walks.py --set corpus\|held --seeds K [--limit N]` | No engine. Walks each program for seeds 0 to K−1. Appends to `R/walks/<set>.jsonl` one line per step: the step record, `g`, facts, place, shape, pattern, `walk_bits`, and one `{"rec": "walk", task, seed, steps}` line per walk. Corpus shapes come from `$IB/corpus/rows-*.jsonl`, held shapes from `R/shapes/` |
| `tw_fit.py` | Fits M0, M1, M2A, M2B, M2M, M3 on corpus walks with the CV choice of alpha, and the fit-shuffled M2A and M2B (the state permuted within each corpus walk, seeded). Writes `R/fit.json` (alphas, CV bits per model, fit stems). Then scores every held step of every seed and appends `R/tower/<task>.jsonl`: per step, `task, seed, t, key_f`, bits of each factor of each model, and the read-time-shuffled bits of M2A and M2B (20 permutations of `prev` within the task's steps of that seed, mean) |
| `tw_held.py --task T --pass 1\|2 [--steps t,t] [--max-draws N] [--out DIR]` | One task per process. Models: `models-kr` for the 37, `models-krf` for the ramp. Reads `R/shapes/T.json`, walks seed 0, runs [The proposal's rate](#the-proposals-rate) at each picked step not done. Appends to `R/held/T.jsonl` one line per step: `task, set, pass, t, key_f, g, kind, shape, pattern, place, mode, prev, p_kind, admitted, n, h_joint, h_shape, h_pattern, none, batches, cpu, outcomes` (counts of every drawn `(I, K)` and pattern), `drops`. It exits with 75 when its RSS passes 3 GiB after a step |
| `tw_held_all.sh PASS P` | Runs `tw_held.py --task T --pass PASS` for the 59 tasks, P at a time, through `xargs -P P`. Each task reruns while the exit code is 75 |
| `tw_check.py` | The checks of [Checks](#checks), each under 30 s |
| `tw_read.py` | Reads `R/walks`, `R/tower`, `R/held` and `R/fit.json`, and writes `R/tables.json` and `R/results.md` |

## Checks
- **K1, the walk reads only the DAG**: on 20 corpus stems, write the program's forms in `dag.random_order(7)` and walk both texts with seeds 0 to 3. The sequences of content keys and modes are equal.
- **K2, the walk's invariants**: on the same walks, the order is a linear extension. At each step, each `c_{i+1}` reads `c_i`, the head is the form placed last, and the mode recomputed from the chain before the step equals the record's.
- **K3, the pattern on both sides**: on 135a2760 at step 30, `pattern()` of gold's form, from its text through the draw path (heads in `NAME.findall`), equals the walk's record. For 5 drawn clauses, every scope head that the text names is in S.
- **K4, held shapes**: `tw_shapes.py` stops a task where the replay's Ident-only forms differ from the pinned list.
- **K5, held out**: `tw_fit.py` asserts that no fit stem is in `eval-tasks.txt` or `ramp-fold.txt`.
- **K6, order stability of the proposal**: on 2 steps of 135a2760, the joint rate from batch 0 (walk order) and from batches 1 to 3 (random orders) have overlapping Jeffreys intervals.
- **Data check**, printed first by `tw_read.py`: walks by set and seed, steps by kind, steps left out (OTHER kind, `P_kind = 0`), held steps done by pass against the lists, steps with `h_joint = 0`.

## Controls
- **Shuffled state, at read time**: M2A and M2B scored with `prev` permuted within each task's steps. The gain over M1 goes to 0 or below.
- **Shuffled state, at fit time**: M2A and M2B fit with `prev` permuted within each corpus walk, scored with the true `prev`. Bits within .03 of M1.
- **Walk seeds**: tower bits per form on the held sets over seeds 0 to 15: mean and spread over seeds.
- **In sample against held**: each model's 5-fold CV bits on the corpus beside its bits on the held sets.
- **Walk choice bits**: the mean `walk_bits` per step, the cost of the order that neither side pays, as context.

## Read
`tw_read.py` writes these tables to `R/results.md`, with the 37 and the ramp apart. "Bits" are bits per form, as a weighted mean over done steps. Each interval is the 2.5% and 97.5% points of 2,000 bootstrap draws over tasks.

**Table 1, bits per form** (the deliverable): rows proposal, M0, M1, M2A, M2B, M2M, M3. Columns: bits (mean, median), shape part, pattern part, saving against the proposal with its interval, and the same over steps with `h_joint ≥ 1`.

**Table 2, the state**: M1 − M2A, M1 − M2B, M1 − M2M, M2M − M3, each with its interval, and both shuffled controls beside them.

**Table 3, share of steps in each state** (t ≥ 1, seed 0, and mean over seeds 0 to 15 with the spread): EXTEND, BT1, BT2, BT3+, JUMP0, JUMP+; meaning A; meaning B. The same on the corpus walks. Below it, the transition table `P(mode_t | prev)`.

**Table 4, by place**: rows root, chain step, join, top join, each also split by f's mode. Columns: steps (done, total), proposal bits, M1, M2A, M2B bits, saving of M2A against the proposal with its interval, and the share of all saved bits.

**Table 5, by outcome**: the proposal's and M2A's median bits for the 10 commonest gold `mode6` values and the 10 commonest shapes.

**Table 6, context**: alpha per model and factor, CV bits on the corpus, mean `walk_bits`, steps left out, steps with `h_joint = 0`.

### Rule for the verdict
`tw_read.py` prints, for the 37, then for the ramp as a second, weak read:

- **Saving**: the M2A and M2B savings against the proposal, with intervals. "A tower-conditioned proposal saves" holds where the M2A interval is above 0.
- **State**: "the state carries information" holds where the M1 − M2A interval (or M1 − M2B) is above 0, the gain is .05 bits or more, and the read-time-shuffled gain is 0 or below. It names the meaning, A or B, with the larger gain.
- **Source**: the shares of the M2A saving that come from set facts (proposal − M0), from the last built (M0 − M1) and from the state (M1 − M2A).
- **Where**: the places that hold half or more of the saved bits, and the place with the largest saving per form.

## Predictions
Written before any count of this read, except the one probe walk.

- State shares on the 37 (t ≥ 1, seed 0): EXTEND 45 to 60%, BACKTRACK 8 to 18%, JUMP 25 to 40%, JUMP0 (roots) 12 to 20%. Meaning A 45 to 60%, meaning B 60 to 75%. The ramp: EXTEND 40 to 55%, JUMP 30 to 45%.
- Transitions: `P(EXTEND | prev = EXTEND)` 55 to 70%, `P(EXTEND | prev = JUMP)` 35 to 55%.
- Bits per form on the 37: proposal mean 5 to 7, median 4 to 6. M0 3.6 to 4.6. M1 3.4 to 4.3. M2A 3.2 to 4.1. M2B .03 to .1 bits above M2A.
- Saving of M2A against the proposal on the 37: 1.5 to 3 bits per form, interval above 0. 60% or more of it is in the pattern part.
- Source: the set facts carry 75% or more of the saving. The last built carries .1 to .4 bits. The state carries .05 to .25 bits, with an interval above 0 on the 37 and including 0 on the ramp. M3 adds 0 to .15 bits over M2M.
- By place, saving of M2A: root 2 to 4 bits; chain step 1 to 2.5; join .5 to 1.5; top join 0 to 1.5, the smallest. The chain steps hold the largest share of the saved bits, since they are the commonest place.
- Steps with `h_joint = 0`: 10 to 25%.
- Controls: read-time-shuffled gain −.1 to 0; fit-shuffled M2A within .03 of M1; spread of M2A bits per form over walk seeds ≤ .1; held bits ≤ CV bits + .4; mean `walk_bits` 1.5 to 2.5.
- Verdict on the 37: the saving holds and the state holds, but most of the saving comes from learned set conditioning, not from the state. The roots and the chain steps hold most of the saved bits.

## Steps and commands
Set `R`, `IB`, and `E=$R/tw_env.sh`. Run each command under `timeout 30`. Hand back each command marked "hand back", with its ETA. The smoke step's measured rate replaces the ETAs given here.

1. Write `tw_lib.py`, `tw_env.sh`, `tw_shapes.py`, `tw_shapes_all.sh`, `tw_walks.py`, `tw_fit.py`, `tw_held.py`, `tw_held_all.sh`, `tw_check.py` and `tw_read.py`, and `R/manifest.json` with the pins, this design's path and the predictions.
2. `timeout 30 bash $E check`: about 10 s (it hashes the 989 corpus programs). Every pin matches.
3. `timeout 30 bash $E 1 tw_check.py k1k2 20`: about 5 s. K1 and K2 pass.
4. `timeout 30 bash $E 1 tw_shapes.py --task 135a2760`: about 5 s. K4 passes.
5. `timeout 30 bash $E 1 tw_check.py k3 135a2760 30`: about 15 s. K3 passes.
6. Smoke: `timeout 30 bash $E 1 tw_held.py --task 135a2760 --pass 1 --steps 12,30 --max-draws 32 --out $R/smoke`: about 20 s. Rows for both steps with n = 32, `P_kind`, the counts and a rate in s a draw. A rerun writes nothing and prints "2 done".
7. `timeout 30 bash $E 1 tw_check.py k6 135a2760 12`: about 25 s. K6 passes.
8. `timeout 30 bash $E 1 tw_walks.py --set corpus --seeds 4 --limit 50`: about 5 s. It prints s a stem. If the rate × 989 is under 25 s, run step 9 inside `timeout 30`; else hand it back.
9. Corpus walks: `bash $E 1 tw_walks.py --set corpus --seeds 4`. ETA 20 to 60 s, one process.
10. Hand back. Held shapes: `bash $E 4 tw_shapes_all.sh 4`. ETA: about 4 s a task, 59 tasks, about 1 min wall at 4 processes, about 1 GB each.
11. `timeout 30 bash $E 1 tw_walks.py --set held --seeds 16`: about 10 s.
12. Fit: `bash $E 1 tw_fit.py`. ETA 30 to 90 s. Hand back if `timeout 30` stops it.
13. Hand back. Held pass 1: `bash $E 4 tw_held_all.sh 1 4`. ETA: about 690 steps at about 20 CPU s, so about 3.8 CPU h, about 60 min wall at 4 processes, about 1 GB each. The longest task is about 12 steps × 45 s = 9 min.
14. `timeout 30 bash $E 1 tw_read.py`: under 30 s. Check the data check lines and the tables.
15. Hand back. Held pass 2: `bash $E 4 tw_held_all.sh 2 4`. ETA: about 1,080 steps, about 6 CPU h, about 90 min wall at 4 processes. Without it, the pass 1 weights give the estimates.
16. `timeout 30 bash $E 1 tw_read.py` again. Then copy `R` as in [Record](#record).

## Limits to state in results.md
- The read measures the draw distribution of `Sampler.clause`, not the best-first search's order or its visit end.
- Both sides score gold's form at the step the walk gives. Neither pays for the order, which is `walk_bits` a step. The walk is the round-0 walk of `walk.md`. A refit `theta` changes the steps and asks for a rerun.
- The pattern counts reads by place on the tower. It doesn't say which form of a class f reads. The shape is the head shape, not the body.
- The proposal's bits are a lower bound at steps with `h_joint = 0`.
- `relR4_o.pkl` holds the ramp in its train rows. The corpus copy is of 21:49 on Nov 1, and the priors were fit earlier.
