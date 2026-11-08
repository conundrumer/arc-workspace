# A learned model of gold's next production: experiment design

Superseded. The writer's learned model now writes the next query, token by token: the [Writer spec](../../../../work/lm/data-study/sampler/sampler-worker/proposer-inventory/writer-spec.md) gives it, and [Training instances](../../../../docs/sample-build/training-instances.md) its training data. `R` below is stale, so the figures that cite it no longer hold.

The question: can one learned model, which reads the whole search state, rank gold's next production above the other candidates? The search state is the task examples, the tables built so far with their contents, and a candidate next production. If it can, a plain best-first search driven by that model replaces the node score, the scope pick and the proposer's factorisation.

This record is a design. Nothing is built. Each fact cites its source. Each estimate says that it is an estimate and shows its arithmetic.

Paths:
- `U` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/`
- `K` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943/`
- `R` = `/Users/davidlu/code/arc-workspace/work/results.md`
- `F` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/`
- `X` = `F/features-learned-next-production-design/`, this folder. The `probe-*.json` files and the `probe_*.py` scripts that wrote them are here.

Terms:
- **Table**: one relation of the union AND-OR graph, as a pool node's table is (docstring of `/Users/davidlu/code/arc-workspace/model/study/gold/reads/union/gold_union_graph.py`). Two tables are equal when their merge keys are equal.
- **Production**: one form identity of the union. It is an AND over the tables it reads, and the tables it makes are its heads (same docstring).
- **Reach**: a gold table is reached when a pool node's table equals it (the task's definition). The records count a gold form as "covered" under the same test. This design uses "reach" for both.
- **Enabled**: a production is enabled in a state when each table it reads is built and at least one of its heads is not built.

## What the model replaces

- **Node score and scope pick.** `Policy.scope` takes three quarters of a scope's picks by weight e^(score − uses), and the rest are the oldest nodes among the least used (`K/policy/policy.py` lines 1-5). The score is `policy_model.pkl` (sha prefix bac5114e, equal to `features-worker/policy/policy_model.pkl`).
- **Visits.** A visit is one (scope, kind) best-first clause search. It runs until PATIENCE tries in a row give no new node, or VISIT_SECONDS pass (`K/model/study/sampler/superdag_search.py` lines 13-17).
- **Proposer factorisation.** The kind and the stop come from corpus counts. A RULE's or DET's atoms come from the Drawer, and an INIT takes a component, then ports, each with a body and a head (`K/model/study/sampler/live.py` lines 20-25). The relation pick is steered by `relsteer.Scorer` (`relsteer.py` lines 1-12), applied at `sample2_col.py:2428`. The choice pick (columns, values, operators, stop) has its own steer (`K/model/study/sampler/README.md`, "Proposal").

## Sets

| Set | File | Role |
|---|---|---|
| ramp 22 | `.../sampler-worker/held/ramp-fold.txt` | read first |
| the 37 | `.../sampler-worker/held/tasks.txt` | read second, after the ramp 22 |
| the 99 | `.../sampler-worker/held/leave_out.txt` (holds the 37) | never in a fit or a tune |
| training | the other 989 tasks of `U/case-counts.jsonl` (`X/probe-sizes.json`) | fits and tunes |

No task of the ramp 22 or the 99 enters a fit, a tune, a choice of features or a choice of option. Each fit script asserts this.

The proposer's priors and steers have the ramp in their fit rows (`R` "M2 on the ramp"). So on the ramp, the proposer-bits baseline below is not held out, and the learned model is.

## Labels from the union AND-OR graph

### The graph

Per set, `U/graph-tables-SET.jsonl` gives one line per table, `U/graph-prods-SET.jsonl` gives one line per production (`heads`, `reads`, `bits`, `depth`), and `U/graph-tasks-SET.jsonl` gives the goal options, the least-bits path and the minimax path. Roots are productions that read no table. The goal is an OR over options, and each option is the set of tables that a kept case's OUT line reads (`gold_union_graph.py` docstring).

- Ramp 22: 22 tasks, 445 tables, 1,282 productions (line counts of the graph files).
- The 37: 36 tasks in the graph so far, 1,343 tables, 3,270 productions, 487 OR tables, 7 tasks with no path (`U/supervision-37.json`). b10624e5 is set aside: one read passed the 300 s watchdog at 768 cases (`U/union-37.manifest.json`).
- Training: the union is still streaming. 730 of 989 training tasks are in `union-training-*.jsonl`, and there is no training graph file yet (`X/probe-sizes.json`).

Gold tables per depth (`X/probe-depths-ramp.json`, `X/probe-depths-37.json`; `depth` of `graph-tables`):

| Set | depth 0 | depth 1 | depth 2 | depth 3 | depth 4 | depth 5+ |
|---|---|---|---|---|---|---|
| ramp 22: tables (OR tables) | 79 (15) | 59 (19) | 52 (19) | 47 (25) | 53 (27) | 155 (55) |
| ramp 22: median production bits, p90 | 6.51, 17.22 | 9.50, 22.96 | 14.54, 49.96 | 13.98, 27.45 | 18.14, 48.45 | 20.02, 33.80 |
| the 37: tables (OR tables) | 123 (16) | 78 (31) | 74 (33) | 85 (42) | 83 (44) | 900 (321) |
| the 37: median production bits, p90 | 9.00, 26.06 | 11.48, 23.35 | 14.52, 41.00 | 16.64, 28.77 | 17.02, 32.64 | 20.28, 57.82 |

The bits columns use the production's own depth. On the 37, 1,323 of 3,270 productions have no bits (`X/probe-depths-37.json`). 19 tables of the 37 are `kit_unreachable`: no pool node can equal them (2 at depth 0, 17 at depth 5+).

### What a state is

A state is a set of built tables of one task. It is not a sequence. A state is valid when each of its tables is made by some production whose reads are all in the state. Base relations such as `input` are always present, and they aren't graph tables.

The positives of a state are its enabled productions. Every production of the union comes from a kept case whose OUT rows equal the pinned program's on train and test inputs (`U/design.md`, "Cases"). So every enabled production is a valid next step of some correct program.

States come from walks over the graph:
1. Start at the empty state.
2. List the enabled productions. Record the state and that list as one step.
3. Take one enabled production at random and add its heads to the state.
4. Stop when every table of some goal option is built, or when nothing is enabled.

A walk's order only makes states. The model never sees it: there is no "last built", no step index and no order of the tables. Two walk types:
- Union walk: step 3 picks from all enabled productions.
- Path walk: step 3 picks only from the productions of the least-bits path, and step 2 still lists every enabled union production. These states are the states of one cheap program.

Measured on the held sets, 8 walks a task (`X/probe-steps-ramp.json`, `X/probe-steps-37.json`). These are read-only counts for sizing:

| Set | Walk | Walks reaching the goal | Steps | Steps per walk, median | Positives per step: median, mean, p90, max |
|---|---|---|---|---|---|
| ramp 22 | union | 176 of 176 | 2,418 | 14 | 4, 6.97, 13, 147 |
| ramp 22 | path | 160 of 176 | 1,432 | 9 | 4, 6.44, 9, 114 |
| the 37 | union | 232 of 288 | 8,202 | 29 | 5, 6.93, 13, 119 |
| the 37 | path | 152 of 232 | 5,736 | 24 | 5, 7.14, 16, 60 |

On the 37, the 56 union walks that don't reach the goal are the 7 tasks with no path, 8 walks each. Why some path walks stop before the goal isn't read. A path from `tree_path` is an upper bound with `exact` false (`gold_union_graph.py` docstring), which may be one cause.

Live states hold many tables that no gold program makes. A 600 s pool holds 2,700 to 4,000 nodes at the end (`R` line 281), and an R120 pool has a median of 661 nodes (`F/features-node-rank-model-train-read-hour13-heldout37/design.md` line 37). Gold-only states don't look like that. So the fit states are of two types:
- **Gold states**: from walks, as above.
- **Mixed states**: a gold state plus distractor tables. A distractor is a node of a saved training-task pool whose table equals no union table of its task. Distractors change no label: positives are still the enabled union productions. A mixed state teaches the model to ignore tables that gold doesn't read.

### Negatives

A candidate is a production that is not enabled-and-gold in the state. A candidate whose table equals a built table, or whose reads aren't all built, is removed by rule before scoring, as the search removes a try that gives only known nodes (`superdag_search.py` lines 17-19). A negative whose table equals a union table of the task is relabelled as a positive, because reach is by table equality.

| Negative | How it is made | What it teaches | Risk |
|---|---|---|---|
| Proposer draws | The proposer's clause search at the state, with scopes taken from the state's tables. Each distinct table that equals no union table is a negative. | The ranking that a live search needs, among the clauses the generator actually gives. These are the hardest negatives in the live distribution. | A draw can be a step of a correct program that no case holds. The union design keeps search-found right programs apart (`search-programs.jsonl`, `U/design.md`, "Search programs"). Those productions are neither positive nor negative. This file isn't in `U` yet. |
| Productions of other tasks | A training production of another task. Its reads are mapped to built tables of equal column types, and it is kept only when it makes a non-empty table. | Whether the model reads the task examples: the production is plausible in form and wrong for this task. | Easy when the column types rarely match. A count of type-valid transplants per step is pending. |
| Perturbed gold productions | One change to an enabled gold production: one relation replaced by another of equal column types, one read redirected to another built table of equal type, one constant or operator changed, or one atom dropped. Kept only when the table differs from every union table. | Sensitivity to content: a near miss differs from gold in one decision, which is where the proposer loses its bits (relation pick, `R` "Where the proposal loses gold clauses"). | A perturbation that gives an equal table is a positive and is relabelled. |

Enabled gold productions and gold productions with reads not built are not used as negatives. Readiness is a rule, so the model doesn't learn it.

### Scoring a step with several positives

A step has a median of 4 to 5 positives (table above). The search needs any one of them. The model gives each candidate c a score s(c), and the step's loss is the marginal log likelihood of the positive set:

loss = −log( Σ over positives p of e^s(p) / Σ over all candidates c of e^s(c) )

The loss doesn't force one positive above another, so it doesn't penalise the model for preferring a production of a different case. The offline rank is the rank of the best-ranked positive (below).

## Input representations

The rule for every option: no part of the model may depend on text order or binder marks. No atom index, no last atom, no position in a body, no form's place in gold's text, no slot or token number, no label name, no `*` or `^`.

What each option can see:

| Option | Table contents | Grids | DAG of the state | Candidate's text | Order-free |
|---|---|---|---|---|---|
| A. Hand features, boosted trees | as summary facts: columns, rows per example, Ident columns, cells that agree with the output, distinct values | as task facts (grid and pair facts of the fit-union report) | as facts: depth, reads, ancestors, kinds below | as counts: atoms, relations used, operators, kinds, reads per kind | yes, by construction: each fact is a count or a set |
| B. Set and graph network | rows of each table, up to a cap a table, as a set | each grid as an image, by a small convolutional encoder | as edges: production to read table, production to head | as a graph: atoms and labels are nodes, edges carry the column name. Labels are anonymous nodes, and binder marks are dropped. | yes, if every pooling is a sum, mean or max over sets |
| C. Sequence model over arclog text with grids | only rows that are written into the text, up to a cap | as text: one row per line, cells separated by spaces | through the labels that the text reads | as text | only with a canonical text (below); otherwise it breaks the rule |

Option A can't see a pattern in the cells beyond its facts, nor which relation a candidate reads beyond the relation's counted facts. The fit-union facts (`F/features-search-finds-kinds/fit-union/report.md`, "Fits per depth") separate tables that the current search reaches from tables it doesn't, at AUC .86 to .95 on R120. That target is the current search's bias. Those facts are a start for A, and that fit isn't a model of gold.

Option B can see cell content and the state's structure. It can't see rows past the row cap, and it has no knowledge of relation meanings beyond what it learns from about 10^3 tasks.

Option C can see everything that is written into its text, and it is the only option that could also generate candidates. Its limits:
- Context. Ramp task JSON files are 991 to 12,736 bytes, median 2,796 (`data/tasks/<task>.json`). With one token per cell, the grids are up to about 6,000 tokens. Table contents at about 30 tables of tens of rows don't fit beside them, so contents are capped hard or left out.
- Canonical text. The union identity drops the form's own label and replaces each read by the read's identity, but it keeps atom order and variable names. Forms that are equal only under relabelling stay apart (`U/design.md`, "Forms and tables"). A canonical text needs these steps:
  1. Drop binder marks (`*`, `^`). A label's binding is a fact of the atom set.
  2. Replace each label by a placeholder, and give each atom a key from its relation, its columns and the keys of the atoms that share its labels. Refine the keys in rounds until they don't change.
  3. Sort atoms by key, and rename labels in order of first use in the sorted atoms.
  4. Name each form by its canonical text and its reads' names, and write forms sorted by (depth, kind, name).
  Where step 2 leaves two atoms with equal keys that aren't symmetric, a tie broken by text order breaks the rule. Those forms must be counted, or a full graph canonical labelling must be used. Random reordering of atoms and labels during training doesn't meet the rule, because the model can still depend on the order it is given.

## Metrics

### Offline: rank of gold among the candidates

Per step, all candidates are scored, and the measure is the rank of the best-ranked positive (1 is best). Report:
- the share of steps with a positive at rank 1 and in the top 10;
- the median of log2(rank), which is in bits;
- each with a 95% task bootstrap interval, per depth of the best positive. Each depth row gives the median production bits beside it.

Folds are by task. Ramp 22 first, then the 37, and each is a read of a model fit on training only.

Baselines on the same candidates:
- uniform over candidates;
- the proposer's bits for the candidate, from `graph-prods` for gold productions and from the draw's own logq for drawn negatives (`sample2_col.py` docstring, logp and logq_full). Bits are missing for 1,323 of 3,270 productions on the 37, so on the 37 this baseline is read on productions with bits only;
- the shipped node score of the candidate's table.

Two counts per step, apart from the rank:
- **Generator ceiling**: the share of steps where the generator's candidates hold at least one positive. The scorer can't fix a step where this is 0. On 6 held tasks, 0 of 33 uncovered form-runs were proposed and dropped, 18 got 9,395 right tries and no gold table, and 15 had no right visit (`R` "Proposed and dropped, or never proposed"). There the block was generation.
- **Rank with gold added**: the rank when the positives are added to the generator's candidates. This measures the scorer alone.

### Live: reach per depth under a plain best-first search

The search:
1. The pool starts with the base relations.
2. Each round, the generator gives candidates from the pool. The model scores each against the whole pool, and the candidates go into one priority queue.
3. The search pops the best candidate and builds its table. A table whose key is new becomes a pool node.
4. Each round, the top 256 of the queue are scored again against the current pool, because the pool has changed since they were scored.
5. The search stops at the budget.

There are no scopes, no visits, no use penalty and no least-used pick.

Reach at depth d is the number of union tables at depth d that equal a pool node's table, over the number of union tables at depth d (`graph-tables` `depth`, 5+ pooled). Tables read past by a reached table, and `kit_unreachable` tables, are counted beside, not left out. Equality is by merge key with Ident values by member digest (`ARCLOG_IDENT_SOURCE=value`, `R` "Ident source type and value").

Budget: 600 s a task, read at 60, 300 and 600 s, 2 seeds, CPU equal to the bundle job. Arms:
- the bundle, from the rows that exist (below);
- best-first with the proposer's bits as the score, on the same generator, so that the model's part is apart from the search's part;
- best-first with the model.

The bundle on the union graph's tables (`U/reach-ramp.jsonl`, `U/reach-37.jsonl`, summed in `X/probe-reach-ramp.json` and `X/probe-reach-37.json`). Each cell is reached / tables, + read past:

| Job, 600 s | Set | depth 0 | depth 1 | depth 2 | depth 3 | depth 4 | depth 5+ |
|---|---|---|---|---|---|---|---|
| r1 bundle_s0 | ramp 22 | 68/79 +5 | 33/59 +8 | 15/52 +3 | 2/47 | 0/53 | 0/155 |
| r1 bundle_s1 | ramp 22 | 69/79 +4 | 37/59 +5 | 11/52 +4 | 3/47 | 0/53 | 0/155 |
| r1 bundle_s0 | the 37 (36 in the graph) | 88/123 +14 | 37/78 +12 | 18/74 +11 | 4/85 +16 | 2/83 +17 | 6/900 +100 |
| r1 bundle_s1 | the 37 (36 in the graph) | 84/123 +17 | 36/78 +12 | 19/74 +12 | 5/85 +15 | 3/83 +18 | 9/900 +121 |

Median production bits per depth are in the gold-tables table above. Soak seeds 2 to 4 in `reach-ramp.jsonl` have 0 reached at every depth on 1 to 19 tasks, so they look like missing records and aren't a baseline. The fit-union report gives other denominators (ramp depth 0: 84, "Reach rate per depth"), because it uses the pin's tables. This design uses the union graph's tables.

### What the earlier learned models say about offline and live

| Model | Offline | Live | Gap |
|---|---|---|---|
| Node rank model M-T (`R` "Node rank model, held read") | chance per opening of holding all of a form's reads, 11.2 times the node score's on H (.0219 against .0020) | chance at rank 1 rose 3.3 times (.069 against .021), and forms reached fell from 175.5 to 152.0, −23.5 (−36.0 to −11.5) | a sharper pick changes how the pool grows. Offline chance on a fixed pool didn't predict reach. |
| Node score refit, round 1 (`R` line 2757) | read about as M-T | forms reached −9.0 (−14.5 to −4.0) | its scopes were wider and held new nodes. Openings whose scope holds all reads of an unreached gold form fell to 5.9% and 4.7%, against 14.6% and 14.3% for the bundle. |
| Derived-pick model M2 (`R` "Derived-pick model M2 in the pool", "Why M2's bits don't become forms live") | +1.87 bits a form on C forms | a tie at 600 s. Under live scopes the gain was +1.16 bits against +1.83 offline on the same 24 forms. | about 60% of the offline bits are left live, and an opening gets about 2^5 tries for a clause of 2^17, so 1 to 2 bits move about .25 forms |
| Tower value (`R` "Value of a partial tower") | AUC .80 on exposed nodes of the 37, +.10 over the node score | not run | the rank of a reaching node's ancestors wasn't clearly higher. The line stopped because the node rank model had lost forms live. |
| Tower proposal (`R` "A tower-conditioned proposal") | +.27 bits a form (−.06 to +.56) for M3, and the state added about .1 bit | not run | none measured |

What these imply for this design:
- In 3 of 3 live reads, an offline gain didn't become reach. The live read on the ramp 22 is the result, and the offline rank is a diagnostic. The live read runs whatever the offline read gives, unless the offline rank is below the proposer-bits baseline.
- Two of the losses came from breadth: the pick narrowed onto what it ranked high and exposed fewer of gold's reads. A plain best-first search has no breadth term. So the live arms also need the proposer-bits arm on the same search, and the read must report pool size and node count per depth, so that a narrow pool can be seen.
- M2 lost about 40% of its offline bits under live states. Here the offline states are walk states, and live states are pools. The mixed states are there to make that gap smaller. The read reports the offline rank on states taken from the live run's own pools, beside the rank on walk states.
- A gain of 1 to 2 bits doesn't move reach (M2). The size that matters is the gap between gold's clause and an opening's tries, a median of 10 to 13 bits (`R` "Why M2's bits don't become forms live"). The offline rank is reported in bits so that it can be set against that gap.

## Data size

| Count | Ramp 22 (held, read only) | The 37 (held, read only) | Training |
|---|---|---|---|
| Tasks | 22 | 36 in the graph of 37 | 989; 730 in the streamed union |
| Union tables (graph) | 445 | 1,343 | pending (no training graph) |
| Productions (graph) | 1,282 | 3,270 | pending |
| Union identities (`case-counts.jsonl`) | 1,161 | 6,218 | 93,179 |
| Steps, 8 union walks a task | 2,418 | 8,202 | estimate 110,000 to 200,000 |
| (step, positive) pairs, 8 union walks | 16,855 | 56,825 | estimate 0.8 to 1.4 million |
| Positives per step, median and mean | 4, 6.97 | 5, 6.93 | pending |
| Candidates per step | pending | pending | pending; about 55 by the plan below |

Sources: graph line counts, `U/supervision-37.json`, `X/probe-sizes.json`, `X/probe-steps-*.json`.

The training estimates use these steps:
1. Graph tables per union identity are .38 on the ramp (445 / 1,161) and .22 on the 37 (1,343 / 6,218). On 93,179 training identities, that gives about 20,000 to 36,000 training tables.
2. A union walk takes about .68 to .76 steps per table of its task: ramp 2,418 / (8 × 445), the 37 8,202 / (8 × 1,343).
3. 8 walks over 20,000 to 36,000 tables at .7 steps per table give 110,000 to 200,000 steps.
4. At about 7 positives per step, that is 0.8 to 1.4 million (step, positive) pairs.

Steps within one task share most of their tables. So the sample size for generalisation is the task count, about 989, and not the step count.

Candidates per step, by the plan: the positives (mean about 7), 32 proposer draws, 8 transplants from other tasks and 8 perturbations, so about 55. The distinct-negative yield after removal of equal tables is pending.

Still pending:
- the training graph (`graph-*-training.jsonl`) and its supervision counts;
- the 37's last task, b10624e5;
- negatives per step after removal of equal tables, and the share of transplants that are type-valid;
- the share of proposer draws whose table equals a union table, which sets the generator ceiling.

## Cost and time per option

Machines:
- The Mac has 14 CPUs, about 11 GiB free for jobs, and no GPU.
- A pod CPU costs $0.055 a vCPU-hour.
- GPU prices are from the Runpod catalog, read 2026-11-02 with `list-gpu-types`, on-demand per GPU-hour (`X/gpu-prices-20261102.json`): RTX 4090, 24 GB, $0.34 community and $0.89 secure; L40S, 48 GB, $0.79 and $1.09; H100 SXM, 80 GB, $2.69 and $3.99. No project record has a measured GPU throughput, so every GPU time below is an estimate on an assumed throughput.

### Data, shared by all options

- Proposer negatives. A 600 s job makes 178,762 to 192,490 tries (`R` "Derived-pick model M2 in the pool"), so about 300 tries a job-second. The record doesn't give the vCPUs that a job used. The estimate:
  1. 110,000 to 200,000 steps times 32 draws is 3.5 to 6.4 million tries.
  2. At 300 tries a job-second, that is 3.3 to 5.9 job-hours.
  3. Doubled for the replay of each state into a decoder, it is about 7 to 12 job-hours.
  4. Transplants and perturbations need a table build each, which adds about half: about 10 to 18 job-hours.
  - On the Mac at 10 jobs at once, that is about 1 to 2 hours, if a job fits in about 1 GiB. That memory figure isn't measured.
  - On a pod, at one vCPU a job, it is about $0.55 to $1.00.
- Gold states. Each union table is built once a task, and the walks reuse them. The union is already replayed for the merge, so this cost is small next to the negatives. It isn't measured.

### Fits

| Option | Fit rows | Mac | Pod |
|---|---|---|---|
| A. Hand features, boosted trees | about 6 to 11 million (step, candidate) rows, from 110,000 to 200,000 steps times about 55 candidates. Features cost about 2 ms a node for M-T facts on a pod (`R` "Node score path") and 3.98 ms a node to add with the shipped features (`features-worker/policy/check.log`). | features: 3.3 to 12 CPU-hours, so about 0.5 to 1 hour on 14 CPUs. The fit is minutes. The matrix at 11 million × 100 × 4 bytes is 4.4 GB, which fits in 11 GiB, so it is the largest that fits. | about $0.20 to $0.70 of CPU |
| B. Set and graph network, about 1 million parameters | the same steps. Each state is encoded once, and each candidate by a light head. | estimate: 5 ms a state and 0.2 ms a candidate, for forward and backward, on CPU. That is 550 to 1,000 s for states plus 1,200 to 2,200 s for candidates, so 30 to 55 minutes an epoch, and 10 to 18 hours for 20 epochs. | RTX 4090: estimate under 1 hour a fit, $0.34 to $0.89 |
| C. Sequence model, about 50 million parameters | 110,000 to 200,000 states at about 10,000 tokens: 1.1 to 2 × 10^9 tokens an epoch. Candidates are scored by a head on the state's encoding. | not practical: at about 1 TFLOP/s on CPU, one epoch is about 4 to 7 days | 6 × 5 × 10^7 × 1.1 to 2 × 10^9 is 3.3 to 6 × 10^17 FLOPs an epoch. At an assumed 40 TFLOP/s on an RTX 4090, that is 2.3 to 4.2 hours an epoch, and 10 epochs cost about $8 to $37. At an assumed 300 TFLOP/s on an H100 SXM, it is 0.3 to 0.6 hours an epoch, and 10 epochs cost about $8 to $22. |

The live read is the same for every option. The bundle arm's rows exist, so 2 arms run: 22 tasks × 2 seeds × 2 arms × 600 s is about 14.7 job-hours. On the Mac at 10 jobs at once, that is about 1.5 hours. On a pod at one vCPU a job, it is about $0.80. For B and C on the Mac, the model's own time a candidate enters the live search's CPU budget. For C, that time isn't known.

## What the policy model's fit says about the minimum data

The fit (`work/lm/data-study/features-worker/policy/train_policy.py`):
- One row is one pool node of `sampler/runs/superdag1`. The label is `tags.kind == 'gold'` (line 26).
- Folds are 2, by task parity. Each fold is `HistGradientBoostingClassifier(max_iter=150, max_depth=5, min_samples_leaf=10, class_weight='balanced')` (lines 37-42).
- `train.log`: 22 tasks, 6,594 nodes, 68 gold, 87 features. The folds are 11 tasks with 31 gold and 11 tasks with 37 gold. That model is `policy_model.pkl` (sha prefix bac5114e), which is the kit's.
- `train_base.log`: 34 tasks, 9,731 nodes, 107 gold, 57 features. That model is `policy_model_base.pkl` (sha prefix 41d4a93f).
- `R` line 1583 gives "107 of 8,807 plain, 0 gold among 924 to 994 Ident nodes" for `policy_model.pkl` on 22 tasks. 9,731 − 924 = 8,807, so that count matches the 34-task base log and not the kit model's log. Which count belongs to the kit's model is open. The kit's own log says 68.

What the fit saw:
- No gold Ident table. In the 22 fit tasks, 0 of 606 Ident nodes equal a gold table, and all 111 gold Ident tables have no pool node (`R` line 2745). Its low score for Ident comes from no positive label.

How it reads on held tasks (`R` "Node rank model, held read"):
- Chance per opening of holding all of a form's reads on H: .0020 for the shipped score, .0085 for shuffled labels, .0103 for depth alone.
- Ident tables on H: median rank 6,603, none in the top 100, and a chance of about 2e-08 per opening.
- Records after that read state it as a condition: the shipped node score ranks the right program's intermediates below a shuffled draw (for example `R` line 1539).

Live, the shipped score doesn't hurt the search: the sharper picks M-T and depth alone reached fewer forms (`R` "Node rank model, held read", live table).

Fits with more data, on the same held read:
- M-T: about 3,584 R120 reach events on 970 tasks, plus about 6,500 seeded tables, plus 728 N600 nodes (`F/features-node-rank-model-train-read-hour13-heldout37/design.md`, "Fit rows"). It read .0219, 11.2 times the shipped score.
- Round 1: 8,029 positives on 884 tasks, 4.4 times the rows. It read .0195, about as M-T (`R` "Node rank model, held read", round 1 table).

What this says about the minimum data:
- About 100 positives (68 to 107) from 22 to 34 tasks, 11 to 17 a fold, gave a held rank below a shuffled draw.
- About 10^4 positives from about 900 to 1,000 tasks gave about 11 times the shipped score, and 4.4 times more rows added nothing.
- So, for hand features and trees, the offline rank stops rising somewhere at or below about 10^4 positives on about 10^3 tasks. Between 10^2 positives on 22 to 34 tasks and 10^4 on 10^3 tasks, there is no data point.
- The 107-positive fit doesn't measure a minimum. It also lacked every positive of one table type (Ident), so count and label reach are confounded in it. What it shows is that the labels must hold each kind of table, and the fit must span many tasks.
- The union gives about 0.8 to 1.4 million (step, positive) pairs on 989 tasks (estimate above), with every gold table of every kept case as a positive. That is well past both the 10^2 and the 10^4 marks in pairs. The task count, 989, is the same as M-T's. For option C, the parameter count rises about 50 times over B, and the task count doesn't rise, so C is the option that the task count limits most.

## Order of work

1. Build the training graph and gold states, and count candidates per step. This needs the training union to finish.
2. Option A, offline, on the ramp 22, against the three baselines. Report the generator ceiling and the rank with gold added.
3. Live on the ramp 22, with the three arms above. This runs unless the offline rank is below the proposer-bits baseline.
4. The 37, read beside the ramp 22 and never alone.
5. Option B only if A's live read on the ramp 22 isn't below the proposer-bits arm. Option C only if B gains over A offline on the ramp 22.

## Open questions for the director

| Question | Default |
|---|---|
| Which generator gives the candidates: the proposer's draws, a library of training productions instantiated on the state's tables by column type, or a generative model? | The proposer's draws for the first experiment, so that the scorer is read alone, with the generator ceiling reported apart. |
| States: gold states only, or gold and mixed states? | Both, half and half. |
| Positives: all enabled union productions, or the least-bits path's only? | All enabled union productions, with the marginal-likelihood loss. |
| Search-found right programs: positives or left out? | Left out of both positives and negatives. |
| Does the model read test inputs? | Yes, test inputs only, as `live.py` gives a task with no test outputs. No gold-side fact enters. |
| Gate from offline to live | The live read on the ramp 22 runs unless the offline rank is below the proposer-bits baseline. |
| Live budget | 600 s a task, read at 60, 300 and 600 s, 2 seeds, CPU equal to the bundle. |
| Option C's canonical text, where atom keys tie and the atoms aren't symmetric | Count those forms, and use a full graph canonical labelling before C runs. |
