# Set pick: the scope as the unit of the pick

## Result

The joint pick clears the bar on both seeds. On the bundle jobs' own openings, at the bundle's scope size (6 nodes), its exposure is 18.5% and 18.4% (mean of 5 Gumbel draws), against 14.6% and 14.3% for the recorded bundle picks and 14.8% and 14.8% for the replayed shipped pick. The bar is 14.5%.

Most of the gain is on gold forms with one read, and not on complete sets of two or more reads. The exposure of forms with two or more reads stays under 1.1% for every pick. The mechanism is this:

1. The first node's shape tells the pick which shapes are this task's gold reads.
2. The other 5 nodes then more often hold the covering node of some single-read form.

The pure set pick (shape alone, with the shipped score only to break ties) drops exposure to about 5%.

## Design

The pick makes the scope one node at a time. Each node after the first depends on the nodes already in the scope.

1. The first node is the top node by the shipped key: shipped score - uses + Gumbel. This is the first pick that `Policy.scope` makes.
2. Each further node x is the top node, among the nodes not yet picked, by

   shipped key(x) + beta * tau(x | scope),   with tau(x | scope) = log mean over s in the scope of lift(shape(s), shape(x)) * f(s, x).

3. The pick stops at k nodes. There is no least-used slot. The uses penalty is in the shipped key.

Definitions:

- **Shape** of a table, at four levels, finest first:
  - L0: (kind, sorted column types, key labels)
  - L1: (kind, sorted column types)
  - L2: (kind, set of column types)
  - L3: (kind, number of columns)

  Key labels is the count of `^` labels in an INIT's key section, 0 for an INIT with no key section, and `x` for any other kind. Ident is one of the column types.
- **lift(a, b)** = P(shape b among the co-reads of a table of shape a) / P(shape b among all co-reads). The counts come from the fit. Each level is smoothed toward the next coarser level with 2 pseudo-counts, and L3 is smoothed toward 1. A shape that never appears as a gold co-read is shrunk by the anchor's evidence: lift_L = lift_{L+1} * 2 / (count of anchor + 2).
- **f(s, x)** is the Ident factor. A table's Ident source is the union of the sources of its parents that have an Ident column. Where no parent has one, the table is its own source.
  - f = 1.00 where both tables have an Ident column and their sources meet.
  - f = 0.84 where both have one and their sources are disjoint.
  - f = 1 in every other case.

  The pick makes no join, and it does not read Ident values (the member digests).
- **beta** = 0.5. It was chosen on the training tasks by a 5-fold cross-fit before the replay on the 37 was run (table below). At beta = 1, the tilt is the Bayes update of the shipped log odds by the co-read lift. The cross-fit puts 0.25 to 1 within 0.2 points of each other.

DAG invariance: the shape reads the column types as a sorted multiset, the form kind, and a count over the key section. The Ident source reads the parents graph. Node ids are used only as identities. The Gumbel key is continuous, so ties do not occur and id order breaks none. The pick reads no written atom order, atom index or last-atom fact.

### How this differs from the earlier node-level reads

- **Node pair score** (`features-node-pair-score-corpus320tasks-seed1-120s-ship7`, results.md "Node pair score"). That read measured the AUC of a pair of seeded gold tables that one gold form reads. Kind, types, sizes, clause words and lineage gave +.166 over the two node scores. It scored one pair alone, among gold tables only. It had no junk pool, no scope, no condition on the earlier picks and no search step. The set pick turns pair co-occurrence into a sequential pick over a real pool. The real pool is mostly junk. The pick is measured by exposure at real openings, with real uses.
- **Relation pick conditioned on the task, and the value join feasible set** (`features-relation-pick-feasible-by-value-join-heldout37`, `features-dag-conversion-heldout37`). These reads are inside a clause: the relation of the next atom, in bits per pick. They do not choose which tables enter a scope.
- **Scope block on the hour runs** (`sampler-scope-joint-read`). That read gives the AUC of a form's open reads against other tables, one node at a time.
- **Node score refit, and every rank model so far.** Each scores a node by "is this table gold", and its score does not depend on the other picks. In the set pick, the score of node x changes with the nodes already in the scope.

## Fit

- **Data:** the 50 N600 training tasks.
  - Gold table types come from `features-node-score-refit-loop/gold-sig-n600.jsonl`.
  - Kinds and key sections come from the gold text in `sampler-worker/kits/sampler-pool-dag-nodes-train50-final-8be414670/points-eval.json`. The reads of that file equal the reads of gold-sig on all 50 tasks.
  - View-final's gold text is not used for these tasks. Its forms differ from gold-sig's on some of them (for example 1d398264), so its form indices do not match the tables.
- **What the fit counts:** 947 gold forms. Of these, 417 have 2 or more reads, and they give 1,236 ordered pairs of co-read forms. A form with several tables counts each table pair with weight 1 / (tables of q1 x tables of q2). There are 284 distinct L0 shapes, 276 L1 shapes, 196 L2 shapes and 23 L3 shapes. Ident pairs among co-reads: 114 with the same source, 0 with disjoint sources. Among all form pairs: 2,212 with the same source, 22 with disjoint sources.
- **Left out:** the 37 held-out tasks and the 22 ramp tasks. `fit.py` asserts that none of them is in the fit. The 99 evaluation tasks are also absent from N600.
- **S120 corpus (920 pools) is not in the fit.** 822 of its 879 eligible tasks have a run gold count that differs from view-final, and its run gold (`gold-v3-before-drift-regold`, `points-corpus.json`) was not found. With that gold file, S120 could add the shapes of seeded and covered gold tables for about 900 more tasks.

Beta, on synthetic openings of the 50 N600 banks. There are 120 openings per job, spread evenly over the draws. The uses come from a run of the shipped pick over those openings. Covering nodes are tables equal to a gold table of gold-sig. Each task is scored by the fold model that left it out.

| pick | exposure | 1-read forms | 2+ read forms |
|---|---|---|---|
| shipped | 8.5% | 7.5% | 1.1% |
| joint, beta 0.25 | 10.4% | 9.0% | 1.4% |
| joint, beta 0.5 | 10.5% | 9.3% | 1.1% |
| joint, beta 1 | 10.3% | 9.5% | 0.8% |
| joint, beta 2 | 8.6% | 8.1% | 0.5% |
| joint, beta 4 | 6.6% | 6.1% | 0.5% |
| set only (shipped key breaks ties) | 4.7% | 4.3% | 0.4% |

## Offline exposure on the 37

**Replay.** At each recorded opening of the round 1 jobs:

- The pool is the bank's nodes born before the opening. These are the ids below the policy's node count, and, for a pick that the bank does not keep, below that process's saved nodes.
- The uses are those of the job's own earlier picks that the policy held.
- The scope size is that of the recorded pick (6).

All picks at an opening use the same Gumbel draws. Exposure is as `read.md` defines it: the picked nodes hold, for each read of a gold form not yet covered, a kept covering node whose cover time is before the opening.

**Check against read.md.**

- The recorded picks give read.md's figures exactly: 14.57, 14.28, 5.91, 4.66, 19.79 and 18.52.
- The replayed shipped pick on the bundle jobs gives 14.81 and 14.78 (mean of 5 draws; one draw 15.26 and 15.16).
- The replayed refit pick on the refit-coin openings gives 5.69 and 4.41 (one draw 5.23 and 3.70).

All are within 1 point. The largest single-draw gap, 0.96 on refit s1, is draw noise: that cell's 5 draws span 3.94 to 4.95. The replayed scopes' width check matches the logged visit forms on 15,694 of 15,694 kept openings.

**Exposure, mean of 5 Gumbel draws per opening** (range over the draws in brackets). The bar is the joint pick above 14.5%, at the bundle's scope size.

| jobs | openings | recorded | shipped | refit | joint (beta 0.5) | bar |
|---|---|---|---|---|---|---|
| bundle s0 | 4,339 | 14.57 | 14.81 [14.20, 15.33] | | **18.54** [18.02, 18.92] | clears |
| bundle s1 | 4,335 | 14.28 | 14.78 [14.21, 15.27] | | **18.40** [17.72, 18.73] | clears |
| refit s0, all | 4,007 | 12.70 | 18.76 | 5.55 | 22.42 | |
| refit s1, all | 4,160 | 11.59 | 18.63 | 4.43 | 22.36 | |
| refit s0, refit coin | 2,046 | 5.91 | 18.78 | 5.69 | 22.30 | |
| refit s1, refit coin | 2,081 | 4.66 | 19.05 | 4.41 | 22.75 | |

On the refit jobs, the shipped and joint picks are replayed on pools that the refit arm grew. The bar reads the bundle rows.

Breakdown on the bundle jobs (one draw, the beta values side by side):

| | shipped | joint 0.25 | joint 0.5 | joint 1 | set only |
|---|---|---|---|---|---|
| exposure s0 / s1 | 15.3 / 15.2 | 18.8 / 18.4 | 19.2 / 18.7 | 18.6 / 17.8 | 5.1 / 4.8 |
| forms with 2+ reads exposed, s0 / s1 | 0.2 / 0.6 | 0.3 / 0.9 | 0.3 / 1.0 | 0.3 / 1.2 | 0.0 / 0.0 |
| Ident-only forms exposed, s0 / s1 | 3.6 / 3.2 | 4.3 / 3.8 | 4.4 / 3.8 | 4.2 / 3.8 | 1.0 / 1.1 |

Other figures for the joint pick at beta 0.5, against the shipped pick, on the bundle jobs:

- **Tasks:** exposure goes up on 24 tasks and down on 4 on s0, and up on 18 and down on 8 on s1.
- **Exposed forms per opening:** 0.227 against 0.182 on s0, and 0.243 against 0.194 on s1.
- **Scope width:** 7.7 and 7.8 forms against 8.6 and 8.7, with 4.0 and 3.9 distinct shapes against 4.9. The joint pick does not widen the scope as the refit coin did (13.6 forms).

Limits of the replay:

- The replay is open loop. Each opening uses the pool and the uses of the recorded run. A live joint arm grows a different pool, and its own picks set its uses.
- The fit is 50 tasks.
- Covers after the last bank save are not usable, as read.md says. This makes all exposures lower bounds by the same amount.

## Cost per opening at the worker

- **Pick:** k - 1 = 5 vector passes over the pool (lift lookup by shape id, plus the Ident factor over the Ident nodes). A lift row of n_shapes values is cached once for each anchor shape.
- **Measured offline:** the full replay ran 16,841 openings in 17.1 s, which is 1.0 ms per opening. That covers 2 policy picks, 4 joint picks and 7 exposure tests. The 5-draw replay ran in 48.5 s, which is 2.9 ms per opening for about 13 picks and tests. So one joint pick is at most about 0.3 ms.
- **At the worker:** the round 1 logs give 19,150 to 19,320 s of search per arm over about 4,300 openings, which is about 4.5 s per opening. The joint pick adds under 0.01% of that, even at 10 times the offline time on the pod CPU.
- **Per node, at birth:** one shape key (string work on the clause and table types) and one Ident source (a set union over the parents). There is no table read and no engine call.
- **Memory:** the model is 0.15 MB of counts. The lift cache is under 1 MB per job.

## Prediction and arm

**Prediction for a two-seed 600 s arm on the 37**, against a bundle control in the same run, under the pass rule of `search_refit_read.py`. The rule: on both seeds, forms covered are not below the bundle's by more than the noise band (5 in round 1), and Ident-only forms are above the bundle's.

- **Live exposure:** 17% to 19% (bundle 14.5%).
- **Forms covered, joint - bundle:** +4 per seed (-3 to +9). The reasoning:
  1. Round 1 had about 1.2 first covers per 1,000 right tries, and about 32 tries per opening.
  2. About 175 more right openings per seed give about +5.6k right tries.
  3. Those tries give about +7 first covers.
  4. Narrower scopes can lose a few forms that need no held reads.

  Chance that this condition holds on both seeds: 0.8.
- **Ident-only forms:** +1 per seed (-2 to +3), against bundle 9 and 6 in round 1. Ident-only exposure rises about 20% (3.6 to 4.4, and 3.2 to 3.8). Chance that this condition holds on both seeds: 0.4.
- **Pass:** chance 0.35. If it fails, the likely cause is the Ident-only condition, not forms covered.

**Arm's job design.**

- **Kit:** the round 1 kit `0729e4943`, unchanged, with no NODE_SCORE. The joint pick goes in as a scope rule file through `SEARCH_SCOPE_RULE` (`picks(pool, k, rng)` in `superdag_search.load_rule`), with `model.json` from this folder (the fit on all 50 N600 tasks) and beta 0.5. The rule:
  - draws its Gumbel from `rng.random()`, as `Policy.scope` does;
  - reads `pool.policy.score` and `pool.policy.uses`, and the node's `table_types`, `clause` and `parents`, and the form's `kind`;
  - adds 1 to `pool.policy.uses` for each pick, so the bank's uses check holds;
  - on any exception, returns nothing (the policy's pick is then used) and counts the event.
- **Arms:** `bundle_s0`, `bundle_s1`, `joint_s0` and `joint_s1`, with seeds 0 and 1000, on the 37 held-out tasks, 600 s. That is 148 jobs. The ramp 22 can be left out, as no rule reads them.
- **Read:** `search_refit_read.py`, with the joint arm in the place of the refit arm. The script names its arms `bundle` and `refit`, so the arm name must be a parameter or must map to `refit`. Add read.md's exposure count (`replay.py`, or analyze.py's right-scope count) to the read, so that the live exposure can be compared with the prediction above.
- **Smoke before the run:** 2 tasks, 60 s, both arms. Pass where the parity script's uses check holds, the rule's exception count is 0, and the picks lines carry the rule's name.

## Files

All files are in `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick/`.

| file | what it holds |
|---|---|
| `prediction.txt` | the prediction, written before the exposure was computed |
| `shapes.py` | shape levels and the Ident source |
| `picks.py` | the shipped, refit and joint picks, and the lift |
| `fit.py` | the fit; writes `model.json`, and `model-f0..4.json` for the cross-fit |
| `tune.py` | beta on the N600 banks; `tune.jsonl` (in-fit) and `tune-cross.jsonl` (cross-fit) |
| `prep.py`, `lineage.py` | the node facts per job (`prep/`) |
| `replay.py` | the replay on the 37; `replay.jsonl` (one draw), `replay-draws.jsonl` (5 draws), `replay-ident.jsonl` (Ident-only count, same draws as `replay.jsonl`) |
| `width.py` | scope width and its check against the visit forms; `width.jsonl` |
| `s120.py` | the S120 alignment check; `s120.jsonl` |

Each script streams one job at a time and resumes. `python -I <script> report` prints the tables.
