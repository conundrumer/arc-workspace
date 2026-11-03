# Derived pick model: which scope relation gold's clause reads

Reader: the agent that builds and runs this job. This file stands alone.

`X` is `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37`. `REC` is `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22`. `SW` is `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker`. `KIT` is `SW/kits/sampler-pool-tiekey-value-0729e4943`, and `KS` is `KIT/model/study/sampler`.

## Question

At an atom start under a real scope, the proposal puts most of the derived mass on scope relations that gold's clause does not read. The shipped relation score (`KS/relsteer.py:174`, applied at `KS/sample2_col.py:2428`) ranks gold's relation only about .57 bits above an even split among the derived options. Can a model that ranks the derived options by DAG and table facts give that mass back?

The answer is the bits saved a form, at read-atom picks and at builtin picks, on the 37 held tasks, under the recorded scopes, for C forms and covered forms, with 95% task-bootstrap intervals, against the shipped relation score. The message also says what the model reaches against the S − DB gap (median 3.9 bits for C, 2.6 for covered) and against a line of .78 bits a form.

## Rules

- Each Bash call is one command under `timeout 30`. A slower command goes back to the director with its exact command and an ETA from a measured rate. Do not run it.
- No background commands. Do not poll a task's output.
- At most 4 processes on this Mac, each through `/Users/davidlu/code/arc-workspace/scripts/run_heavy.py`. Memory is tight.
- Write only in `X`. Do not commit.
- Do not read `feat-exp/private/`, `feat-exp/case-cache*/`, `feat-exp/out/`, `feat-exp/stream/`, `*.building`, `judgetool/dataset-contexts/`, `dataset-export-receipts/`, `operator/private`, or any `inform-key/` folder.
- No row from the 37 (`SW/held/tasks.txt`), the ramp 22 (`SW/held/ramp-fold.txt`) or the 99 (`SW/held/leave_out.txt`) enters a fit or a choice of the fit. Every training script asserts this.
- **No part of the model depends on lexical order or binder marks.** The model never reads: the atom index (`p_k`), the last atom (`p_last`), an atom's position in a body, a form's place in gold's text, a slot or token number (`&rN`), a label name, or `*` and `^`. "Atoms drawn so far" enters as sets and counts. Build order enters only as a rank among the scope's forms (below).

## Training data

### Sources

Both sources are recorded scopes of non-held runs: the fids of each visit with `resume` false and a non-empty fid list, sorted by `(depth, fid)` as `REC/job.py:scope_of` sorts them, with repeated fid sets dropped.

| source | run | tasks | gold text | scopes |
|---|---|---|---|---|
| N600 | `SW/sampler-pool-dag-nodes-train50-600s/out/nodes_s0/<task>/work/`: `.bank` (`load_bank`), `.visits` | 50 | `SW/kits/sampler-pool-dag-nodes-train50-final-8be414670/points-eval.json` | 6,677 distinct, median 9 forms |
| C120 | `SW/sampler-cover-clauses-train-120s-c87cf482a/out/` (991 tasks) and `SW/sampler-cover-clauses-train20-120s-c87cf482a/out/` (20 tasks): `<task>.nodes.jsonl.zst` (form texts: the head `&fK` gives the fid), `<task>.events.jsonl` (`event: visit`) | 989 after the held tasks are taken out | view-final, `/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-combined-cut/view-final/<task>/pairs.jsonl.gz`, first line's `gold_sexp` | about 34 a task, median 7 forms |

All 50 N600 tasks are also in C120. A task is one unit for the folds, whichever source it comes from. The task file of a session: the N600 job's `work/<task>.task.json`, else `/Users/davidlu/code/arc-workspace/data/tasks/<task>.json` (the kit holds 123 tasks only). `X/probe/common.py` has `NCtx`, `CCtx` and both session patches; start from it.

### Pairs

A pair is a recorded scope and a gold form `q` such that:

- `q` reads at least one derived relation, and every relation `q` reads has a scope relation with an equal merge key (`gold_read_keys` in `X/probe/common.py`);
- the scope holds no relation equal to one of `q`'s own relations;
- `REC/job.py:build_target` gives status `mapped` (target in the scope's names, table check passed).

The visit's kind need not be `q`'s kind. The walk draws `q`'s kind.

Keep at most 6 scopes a form: the first 6 in visit time. A scope that does not replay on this kit is counted (`scope replay error`) and left out.

### Rows

Walk each pair with `or_q.walk(sampler, task, src, [g, 0], scope, target, sess, d, kind, seconds=20)`, summed over orders, as `X/probe/p2.py` does, with the pick log of `p2.py`. A row is one atom start (phases `root` and `root2`) of one order walk. It holds, for every option: its class (`derived` when `fr.KIND[o] == 'relation'`, `op` for NOT and comparisons, else `lib`), `ws` (the weight before the steer: the logged weight divided by `rf`), `rf`, and whether gold takes it; and for each derived option its fact vector (below), computed at row time by `feats.py`.

- **Row weight.** Within a pair, an order's weight is its chance share among the valid orders, `2^(low - bits_o) / sum`. Each form has total weight 1, split evenly over its kept pairs.
- **Label.** The positives of a row are the derived options with `ws > 0` whose table has the merge key of the option gold takes. The option gold takes is the scope relation that its clause reads (the target's mapped relation). Where two scope relations have equal tables, both are positives; the median count is 1.
- **Read-pick rows** (gold takes a derived option) train the rank model. **All rows** train the gate (variant M2).

### Expected counts (from the probe, below)

| source | tasks | forms with a pair | pairs, at most 6 a form | read-pick rows | all rows | derived options a read-pick row |
|---|---|---|---|---|---|---|
| N600 | 50 | about 80 | about 310 | about 510 | about 1,200 | median 8 |
| C120 | 989 | about 1,980 | about 9,900 | about 18,300 | about 40,000 | median 8 |

So about 19,000 read-pick rows with about 150,000 option rows, and about 41,000 gate rows, on about 2,000 gold forms. A pair gives about 4 rows over its orders, 1.7 to 1.9 of them read picks. Most forms are RULE and INIT; DET forms with a derived read are rare in the training pairs. Report the counts by kind and by place (body, INIT port, INIT key).

## The facts

`feats.py` is one module that `rows.py` and the read's `job3.py` both import, so that a training row and a read pick get their facts from the same code.

### Scope facts, once a scope

From the scope texts, replayed once in the walk's task session with `run.collect` (`REC/job.py:relations`, extended):

- For each scope relation `r = (head &fK, j)`, `j` None for a head relation: merge key, labels, column types, and from `parse_table(OneTable(ct, j))`: the row count of each example. A table that does not parse (past the work cap) gets `no_table = 1` and zeros for the table facts.
- The scope DAG: a form's parents are the `&fN` refs of its text (other than its head). The scope is closed under ancestors. Depth is 1 + the largest depth of its parents.

### Pick state

From the drawer at the atom start:

- the head kind (the kind the walk draws: DET, INIT, RULE; RIGID_DET counts as DET);
- `place` (`self.place`: the body of a RULE or DET, INIT `port`, INIT `key`, or other) and the phase (`root` or `root2`, an atom under NOT);
- the label types in scope: the set of `str(t)` for `t` in `self.p_scope`;
- the drawn derived set: the tokens of `self.p_key` whose name `V.name(t)` is `&r<digits>`, mapped through `prog_names` and `pg.written` to scope relations `(head, j)` (`base_of` in `X/probe/p2.py`); the drawn builtin count: tokens of `p_key` that are lib relations (`t in fr.KIND`, `fr.KIND[t] != 'relation'`, not NOT and not a comparison). Both are read as a set and a count. Check below that they equal the atoms of the order's prefix.

### Option facts, for each derived option `o` with `ws > 0`

All numeric facts are standardized on the training rows; `feats.py` writes the means and scales into `model.json`.

| group | facts |
|---|---|
| table | arity one-hot (1, 2, 3, 4+); log1p of the mean row count over examples and of the largest; the share of examples (train and test) where the table has a row; count of columns of each of the 12 most common column types in the training rows, and of other types; a blank label (`''`) present; `no_table` |
| table against the scope | count of `o`'s column types in the scope's label types, and that count over the arity; no label types in scope yet; count of other derived options with the same sorted type list (log1p); another derived option has an equal merge key |
| DAG | depth one-hot (1, 2, 3, 4+); depth minus the largest depth in the scope; the deepest in the scope; a leaf of the scope (no scope form reads it); a root (it reads no form); log1p of the count of scope forms that read it |
| kind | the form's kind (DET, INIT, RULE) crossed with the head kind (9 flags); a sub-relation of an INIT form (`j` not None); log of the count of relations of its form |
| build order | recency rank: the count of scope forms with a larger fid, over (scope forms − 1), so 0 is the newest; the newest form |
| drawn atoms | `o` is drawn; another relation of `o`'s form is drawn; `o`'s form is a proper ancestor of a drawn form; a proper descendant; shares a parent with a drawn form; its key equals a drawn relation's key (not `o` itself); shares a column type with a drawn derived relation |
| crosses | no derived atom drawn yet × (leaf, deepest, type count in scope); place one-hot × (leaf, sub-relation, depth minus largest); `root2` × (drawn, leaf) |

Build order is a search-time fact: the fid is the form's number in the pool, given when the pool kept it. The recency rank reads only the order of the scope's fids, relative to the draw now in progress, which is newer than every scope form. It does not read the fid's value or any text position.

Pick-level facts (counts drawn, place, head kind) enter the rank model only through the crosses, since a constant across a row's options cancels in the softmax.

### Gate facts, for each row (variant M2)

head kind one-hot; place one-hot; `root2`; log of the count of derived options with `ws > 0`; count of derived atoms drawn (0, 1, 2+); count of builtin atoms drawn (0, 1, 2, 3+); no label types in scope yet; log of the count of scope forms; and from the rank model's scores `s` over the row's derived options: `LSE(s) − log n_D` and `max(s) − LSE(s)`.

## The model

### Rank model (both variants)

A conditional logit over the derived options of a read-pick row: `s_o = β · x(o)`, share `p_o = exp(s_o) / Σ_j exp(s_j)` over the derived options with `ws > 0`. The loss of a row is `−log Σ_{o in positives} p_o`, times the row weight, plus `λ ‖β‖²`. Fit with `scipy.optimize.minimize(method='L-BFGS-B')` and the exact gradient. `λ` is chosen by the cross-fit below from {0.01, 0.1, 1, 10} times the weight total over 1,000.

Ablation, reported and not used unless it wins: `sklearn.ensemble.HistGradientBoostingClassifier` (max_iter 300, learning_rate 0.05, max_leaf_nodes 15, min_samples_leaf 50) on option rows labeled positive or not, with the row weight split over the row's options; `s_o` is its log odds, and the softmax is the same. The rank model used in the read is the one with fewer cross-fit bits; a tie within .05 bits a read pick goes to the logit, which the live hook can compute with a dot product.

### Gate (variant M2)

Logistic regression of "gold takes a derived option" on the gate facts, weighted by row weight, L2 with `C` from {0.1, 1, 10} by the same cross-fit. The rank scores in the gate facts are out of fold: each training row's `s` comes from the rank model fit without its task's fold. The read uses the final rank model's `s`.

### Cross-fit (the held-out check on the training source)

Five folds of training tasks, by `zlib.crc32(task.encode()) % 5`. Each fold's rows are scored by the models fit on the other four. All numbers below are weighted means over rows, in bits:

1. Read-pick rows, within the derived options: `−log2` of the positives' share under (a) an even split, (b) today's steered weights `ws · rf` normalized over the derived options, (c) the rank model. Also the share of rows where a positive has the largest score.
2. All rows, the whole pick: `−log2` of gold's share under today (`ws · rf` over all options), M1 and M2 (the arithmetic below, with the logged `ws` and `rf`). Split by read picks, builtin picks and op picks.
3. Both, by source (N600, C120) and by place.

These numbers are pick-level, from the logged weights. They are not the read's S, which sums over orders with each order's own path.

## How the score enters the pick

The hook is `Drawer.group_steer(opts, ws, rf)` (`model/study/sampler/sample2_col.py` at master `da79e6496`, called under `STEER_REL_GROUPS` at an atom start after `rel_factors`). There, `ws` are the weights before the steer, `rf` the shipped factors, and the groups are D (options with `fr.KIND[o] == 'relation'`) and B (all others, NOT and comparisons among them). The variants below are its exact arithmetic. On every training row and read pick so far, every option of KIND `relation` had `rel_name` `declared`.

Notation at one atom start: `T_D = Σ_{o in D} ws[o]`, `T_B = Σ_{b in B} ws[b]`, `T = T_D + T_B`. `e_o = exp(s_o)` where `ws[o] > 0`, else 0. `E = Σ_{o in D} e_o`. `Z_B = Σ_{b in B} ws[b] · rf[b]`.

- **Off.** Today: `ws'[o] = ws[o] · rf[o]` for all options.
- **M1, within the derived group** (fits `group_steer` as it is: replace `rf` for D):
  - `o` in D: `ws'[o] = T_D · e_o / E`.
  - `b` in B: `ws'[b] = T_B · ws[b] · rf[b] / Z_B`.
  - In `group_steer` terms: `rf[o] := e_o / ws[o]` for `o` in D with `ws[o] > 0`, and `rf[o] := 0` for `o` in D with `ws[o] == 0`. Then `group_steer` gives the lines above.
- **M2, with the gate** (a separate variant: it changes the group totals): with `σ = sigmoid(γ · z)`,
  - `o` in D: `ws'[o] = T · σ · e_o / E`.
  - `b` in B: `ws'[b] = T · (1 − σ) · ws[b] · rf[b] / Z_B`.
- In both: where `E == 0` the D lines keep `ws[o]` (and M2 gives B the total `T`); where `Z_B == 0` the B lines keep `ws[b]`. A group of one option follows the same lines.
- `alt` (the other side of the join coin) gets the same lines with its own `ws`, its own totals and its own zeros. `s`, `σ` and `rf` are the same for both, since none of them reads `ws`.
- Where: every atom start that reaches the steer block (`STEER_REL and (self.force is None or self.gq)`), both phases, INIT bodies included. In an INIT body (`rel_off`) today's `rf` is 1, so Off and `group_steer` leave the weights as P has them; M1 and M2 replace the derived shares there too. `results.md` splits the saved bits by `rel_off`.

The within-D share is the model's alone: it does not read `ws` other than its zeros. `ws` inside D is P's even split times the structural weights, the tilt and the steer-time boosts. On the 37, P alone placed gold .08 bits (C) and .19 bits (covered) over an even split among the derived options (`REC/cause/read.md`), so dropping `ws` inside D loses little and keeps the model free of the inputs of `struct_rel` and the tilt.

## The read

### Forms and walks

The forms are those of `REC/split-steer`: the rows of `REC/forms.<i>of2.jsonl` (C) and `REC/forms-covered.<i>of2.jsonl` (covered) with status `mapped` and S valid: 42 C and 43 covered. `job3.py` is `REC/split-steer/job2.py` with the switch replaced:

- It execs `REC/job.py` up to `main()`, as `job2.py` does, and gets each form's scope, target and session from `prepare`. It asserts that the target equals the recorded one.
- Before each walk it builds the scope facts of that form's scope (one replay, memoized by the scope texts).
- It patches `S.Drawer.rel_factors` to keep the kit's factors and hand 1s to the kit (as `job2.py` does) while a switch is on, and `or_q.GuidedDrawer.pick_complete` to apply the arm's lines above to `weights` and `alt`.
- It walks S per arm with the call of `REC/job.py:measure`: `or_q.walk(sampler, task, arm, [g, 0], scope, target, sess, d, kind)`, summed over orders, no other arguments. Arms: `off`, `M1`, `M2`. One JSON line a form to `X/walks-<set>.<I>of<N>.jsonl`, streamed; forms already there are skipped; a task stays in one shard (`zlib.crc32(task) % N`); `--budget S` stops after the form in progress; exit 75 when the peak RSS passes 3 GiB (run it again).
- `--check-regroup`: an extra arm `G` with `s_o := log(ws[o] · rf[o])` in M1's lines, which is `group_steer` with the kit's factors. On the forms that `REC/split-steer/walks-<set>.*of2.jsonl` hold, `G` must equal their `S_on` total within .01. Run it on the first 10 forms of each set.

### What results.md gives

`read3.py` reads the walk rows. Per form and arm: `delta = S_off − S_arm`, and the delta at read-atom relation picks, at builtin relation picks and at op picks, with `relp` of `REC/split-steer/read2.py` (extended to the op-pick place of `REC/design.md`). Then per set (C, covered) and arm (M1, M2):

| column | how |
|---|---|
| forms (tasks) | |
| saved a form, total | mean and median, each with a 95% task bootstrap (2,000 resamples, `numpy.random.default_rng(0)`, a task brings all its forms of both seeds) |
| saved at read-atom picks | the same |
| saved at builtin picks | the same |
| saved at op picks | the same (a check: M1 does not touch op picks except through the B totals, M2 does) |
| saved at `rel_off` picks | sum and forms |
| against the gap | over forms with DB: median `S_off − DB`, median `S_arm − DB`, and `Σ delta / Σ (S_off − DB)` with its interval |
| against .78 | mean saved a form minus .78, with its interval |

Plus the cross-fit tables, the training counts, the checks, and a per-form table (`forms.tsv`).

The message: `M1 saves m bits a form on C [lo, hi] (read picks a, builtin picks b) and m' on covered [lo, hi]; M2 saves ...; that closes x of the S − DB gap (median gap g → g'); against the .78 line: above, below, or within.`

## Checks (in `summary.json` and `results.md`)

1. **Off equals recorded.** On every form, `S_off.total` equals the recorded `S.total` within .005.
2. **Regroup.** `--check-regroup` as above.
3. **Walks.** Every M1 and M2 walk is valid. Count the estimates (`orders.exact` false).
4. **Order free.** On 3 forms with an exact order sum and 2 or more orders, M1's total on the target with its body atoms reversed equals M1's total within .01.
5. **Facts are sets.** A unit test in `feats.py`: the facts of a pick are equal when `p_key` is permuted and when the scope's texts are listed in another order; and they do not change when the fids are renumbered by any map that keeps their order.
6. **Drawn atoms.** On 20 training pairs, the drawn derived and builtin counts at each atom start equal the counts of the atoms of the order's prefix.
7. **No held task.** The training tasks are disjoint from the 37, the ramp 22 and the 99 (asserted in `rows.py` and `fit.py`).
8. **Row parity.** On 10 training pairs, the facts that `rows.py` stored equal those that `job3.py`'s path computes on the same pair.

## The probe

Scripts and outputs in `X/probe/`. Run with `bash REC/env.sh ../features-derived-pick-model-heldout37/probe/<script> ...`.

- `p1.py`: pairs on recorded scopes. N600, 10 tasks: 1,177 scopes, 0 replay errors, 391 mapped pairs (39 a task), 1.6 forms a task with a pair, 4.75 s a task. C120, 14 tasks: 456 scopes, 1 replay error, 252 mapped pairs (18 a task), 2.0 forms a task, 1.84 s a task.
- `p2.py`: rows. 119 pairs walked at 0.1 to 0.13 s a pair. All 4,484 derived options at the logged picks have `rel_name` `declared`; none had weight 0.
- `p3.py`: replaying a whole N600 bank, form by form with its ancestors, takes 13 ms a form (about 33 s a task) and finds about as many forms with all reads covered as the recorded scopes do (3 against 2 on `009d5c81`). Scopes built from the bank add little, so the job uses recorded scopes only.
- `p4.py`: the training picks against the read's picks (the S walks of `REC/cause/mass*.jsonl`, used only for this comparison):

| source | forms | read picks | derived options, median | gold over an even split, today's steer, median bits | gold first among derived | gold's pick bits, median | builtin picks | derived total at builtin picks, median |
|---|---|---|---|---|---|---|---|---|
| N600 | 16 | 73 | 8 | .33 | .26 | 3.40 | 78 | .68 |
| C120 | 28 | 139 | 8 | .32 | .43 | 3.04 | 143 | .68 |
| 37, C | 42 | 55 | 9 | .57 | .38 | 2.92 | 76 | .70 |
| 37, covered | 43 | 50 | 7 | .41 | .64 | 2.89 | 41 | .70 |

The training scopes come close to the real ones in the count of derived options, the size of the scope (median 9 and 7 forms, against 8 and 6) and the derived total at builtin picks. Today's steer does slightly worse on them than on the 37. One difference: 18 of the 55 read picks of the 37's C forms are in INIT bodies (`rel_off`), against 16 of 73 (N600) and 19 of 139 (C120) in the probe's rows. Report the share in the full rows.

## Cost

| stage | items | rate (measured) | one process | ETA on 4 processes | memory |
|---|---|---|---|---|---|
| `rows.py` (pairs, walks, rows), one stream a task | 989 tasks | C120 about 3.2 s a task (1.84 + 10 × .13), N600 about 5.6 s | about 55 min | about 15 min | under 1 GiB a process |
| `fit.py` (5-fold cross-fit, λ grid, gate, ablation) | about 150,000 option rows | not measured: L-BFGS on 60 features | | about 3 min, one process | under 2 GiB |
| `job3.py` (3 arms) | 85 forms | as `REC/split-steer`: most forms 1 to 3 s an arm; `dd6b8c4b g14` about 10 to 25 s an arm a seed; `f560132c g10` about 5 to 10 min an arm | | about 10 min for all but `f560132c`; its shard about 30 min | under 3 GiB (exit 75 above) |
| `read3.py` | | | seconds | | |

Streaming and resume:

- `rows.py --src n600|c120 --shard I/N [--budget S]`: one JSON line a task to `X/rows/<src>.<I>of<N>.jsonl` (one entry a pair, its rows inside), written when the task is done; tasks already there are skipped; a task that raises gets a line with `status error`. Shard by `zlib.crc32(task) % N`. Prints the rate and an ETA after each task.
- `fit.py`: reads the rows files and writes `X/fit/cv.json`, `X/fit/model.json` (feature names, means and scales, `β`, `λ`, the column-type list), `X/fit/gate.json`, `X/fit/hgb.pkl` (ablation). It takes minutes; run it once.
- `job3.py --set C|covered --shard I/N [--budget S] [--check-regroup]`: as above.

Commands to hand to the director, after a smoke test of each under 30 s (`--budget 15`):

```
bash REC/env.sh ../features-derived-pick-model-heldout37/rows.py --src c120 --shard 0/4   # and 1/4, 2/4, 3/4; about 15 min each
bash REC/env.sh ../features-derived-pick-model-heldout37/rows.py --src n600 --shard 0/1   # about 5 min
bash REC/env.sh ../features-derived-pick-model-heldout37/fit.py                          # about 3 min
bash REC/env.sh ../features-derived-pick-model-heldout37/job3.py --set C --shard 0/2      # and 1/2; f560132c sits in one of them
bash REC/env.sh ../features-derived-pick-model-heldout37/job3.py --set covered --shard 0/2 # and 1/2
bash REC/env.sh ../features-derived-pick-model-heldout37/read3.py                        # seconds
```

`REC/env.sh` runs a script relative to `REC`, so the path starts with `../features-derived-pick-model-heldout37/`.

## Limits

- The priors and the shipped steers were fit on gold that holds the training tasks, so today's numbers on the training rows are in-fit; the model's training rows see those weights only through the labels and the zero pattern of `ws`.
- C120 ran on wheel `c87cf482a` with older steers at 120 s; its pools are shallower (about 500 forms a task against about 2,400 in N600). Its scopes are replayed on this kit; a scope that does not replay is left out.
- N600 and C120 use different gold texts for the same tasks (train50 `points-eval.json` against view-final). Both are walked summed over orders, so atom order does not matter. Line counts can differ by a form.
- The read's numbers are the proposal's chance of gold's clause on one opening a form, path by path. The search's patience and seconds are not in them.
- The model is fit on forms with at least one derived read, as the read's forms are. A clause with builtins only does not enter the gate's rows.
