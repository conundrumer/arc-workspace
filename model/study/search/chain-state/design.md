# Chain state: a search that conditions its next scope on what it just built

## Walk

This section defines the walk that the bits side and the search side both use. It is form-level only. The walk of atoms inside a form stays as `features_dag_order.py` has it.

### Inputs

- `F`: the gold forms of one task, without `OUT`.
- `reads(f)`: the forms of `F` that form `f` names (`parent_ids` of `FormDag`). Input, train pairs and domains are base relations, and they are not forms. A form whose `reads` is empty is a root form.
- `kind(f)`: INIT, RULE, DET or RIGID_DET.
- `key(f)`: the content key of `FormDag.content_keys()`.

### State

At step `t` the state is:

- `S`: the set of placed forms. `S` is closed under `reads`, so it is a prefix of some linear extension.
- `C = (c_1, ..., c_m)`: the chain, a stack of placed forms. Each `c_{i+1}` reads `c_i`. The head `h` is `c_m`. When `m = 0`, there is no head.
- `R`: the ready set, the forms not in `S` whose reads are all in `S`.

The start state is `S` empty, `C` empty, so `R` holds the root forms.

### Step

1. Draw one form `f` from `R` (see "Choice").
2. Give the step its mode:
   - EXTEND, when `m > 0` and `f` reads `h`.
   - BACKTRACK(d), when `f` does not read `h` and some `c_j` with `j < m` is in `reads(f)`. Take the largest such `j`. The distance is `d = m - j`.
   - JUMP, in all other cases. A root form is always a JUMP.
3. Change the chain:
   - EXTEND: push `f`.
   - BACKTRACK(d): cut `C` to `c_1 ... c_j`, then push `f`.
   - JUMP: set `C = (f)`.
4. Add `f` to `S`. Stop when `S = F`.

A sibling of the head, that is, a second ready form that reads `c_{m-1}`, is BACKTRACK(1). A form that reads two chains takes its mode from the chain element nearest the head.

### Choice

A cell is a pair (mode, kind of `f`). The modes are EXTEND, BACKTRACK(d) in the bands 1, 2 and 3+, and JUMP. So there are 5 x 4 = 20 cells.

The model is `P_theta(cell | state)`, a softmax over all 20 cells. Its features are the head's kind, the band of `m`, and the count of root forms on the chain. Every feature is a function of the DAG, the kinds and the walk so far. The model is normalized over all cells, also the cells that `R` doesn't hold at that step. If it were normalized over the forms of `R` only, every walk would have total chance 1 for every `theta`, and the fit would have nothing to learn.

The walk draws one step in two parts:

1. Draw a cell among the cells that `R` holds, with chance proportional to `P_theta(cell | state)`.
2. Draw a form uniformly among the forms of `R` in that cell.

- Init `theta_0`: weight `log lambda` on the EXTEND cells, 0 on all else.
  - With `lambda = 1`, the walk is uniform over the cells that `R` holds. `FormDag.random_order` (uniform over the forms of `R`) can also serve as the proposal of round 0, with the weight of "Sum over walks" computed against it.
  - With `lambda` very large, the walk extends whenever it can. That is close to the depth-first post-order, with no "deepest parent first" rule needed. When a form has two parents on two chains, the walk places the second chain by a BACKTRACK or a JUMP, and the form then comes as an EXTEND of its last parent.
- Later rounds: `theta` is the fit of the round before (see "Sum over walks").

### Why the walk is order-free

1. The draw at each step is over `R`, and `R` comes from `S` and `reads` only.
2. The chance of each form in `R` comes from `phi` and `theta` only, and `phi` reads the DAG, the kinds and the steps already taken.
3. So the distribution over walks is a function of the DAG, the kinds and `theta`. No written line order, atom order or atom index enters.
4. A seed only draws one sample from that distribution. The seed's generator must be keyed by the sorted content keys, as `random_order` keys it, and the ready set must be sorted by content key before the draw. Then two programs with the same DAG and content, in two written orders, give the same walk for each seed.
5. Two forms with equal content keys are equal forms, so a statistic does not change when they swap. The tie on the `&rN` name in `FormDag.tie` touches only those pairs.

"Deepest parent first" is order-free when its ties are broken by content key, since depth is a DAG fact. This walk does not need that rule.

### Sum over walks

The fit treats the order as hidden and sums over the linear extensions:

`P(G) = sum over walks w of prod_t P_theta(cell_t | state_t) / n_t`, where `n_t` is the count of forms of `R` in the cell taken at step `t`.

The fit estimates the sum by sampling:

1. For each task, draw `K` walks with the choice rule under `theta`, seeds `0 ... K-1`.
2. For each walk, keep the weight `prod_t Z_t`. `Z_t` is the model's mass on the cells that `R` holds at step `t`. The weights are self-normalized over the `K` walks of the task. With another proposal `q`, such as `random_order`, the weight is `prod_t (P_theta(cell_t | state_t) / n_t) / q(f_t | state_t)`.
3. Fit `theta` again by weighted softmax regression on all steps of all walks. The weight of a step is the weight of its walk. This is one round. Run three rounds.

`K = 16` per task per round to start. For each task, compute the effective sample size of the weights. When it is below 4, double `K` for that task, up to 256. A statistic is reported as its mean over seeds with the spread over seeds.

At about 39 forms per task, one walk is about 39 steps, so 16 walks are about 600 steps per task.

### What "extends" means at run time

Both meanings are kept in each step record, so either can be read from it:

- "Reads the form just placed" is EXTEND.
- "Reads any form on the current chain" is EXTEND or BACKTRACK.

The search can observe both at run time and needs no gold for them. The search's head is the node its last new try made, and its chain is its own stack of extensions. Gold's walk only fits `theta`. The run-time state is always the search's own build history.

### Step record

One row per step: task, seed, round, `t`, `key(f)`, `key(h)` (empty with no head), `m`, mode, `d`, `kind(h)`, `kind(f)`, `|R|`, the counts in `R` by mode, the count of `reads(f)`, the count of root forms in `reads(f)`, and the walk's weight.

## Facts the design rests on

Round 1's bundle jobs on the 37, unless another run is named.

- The pick loses the reads it once had. A B form's worst read ranks a median 277 and 232 at its first ready opening and 1,607 and 920 at its last (`scope-loss/`). A covered form whose reads were ready before its cover had its worst read at a median rank of 1 to 1.5 at its first ready opening.
- 52% to 56% of the ready forms with reads are on the pick. A one-read ready form is held in 13.7% and 12.6% of the later openings, and 42% and 36% of them are never held (`frontier/`).
- Scopes almost never repeat: 0 to 3 exact repeats in about 4,000 openings (`forms-read/`). A slot's search goes on where it stopped, but a scope is opened about once, so no queue walks deep.
- One queue on the right scope finds forms fast. Best-first over the empty context takes 17 of 19 stuck roots under 18 bits, 14 within 5 CPU s. 12 of those 17 are forms the pool never built in 600 s (`search-root-direct-19-60cpus-mac/`).
- The pool leaves the empty scope. After the first 60 s, 0 of about 6,400 openings per seed reached it, and the empty slot was resumed 26 and 35 times in 59 jobs.
- Narrow scopes draw better. Each extra form in a right scope multiplies the cover chance per try by 0.57 [0.43, 0.76], and 57 of 78 covers came from scopes of 6 forms or fewer (`variety/`).
- A visit makes tens of new nodes. On 135a2760 the first visits made 23, 30, 59, 4 and 4. So a head must be chosen among them.
- A job has about 120 openings in 600 s (4,339 openings over 37 jobs in bundle s0), at about 32 tries an opening. An opening is a scarce unit.

## State

The search keeps a beam of up to `B` towers. A tower is a chain stack `C = (c_1 ... c_m)` of pool nodes, as in the walk: each `c_{i+1}`'s form reads `c_i`'s form. The head `h` is `c_m`. With `B = 1` the beam is one state machine.

What the state reads, all of it from the pool's own DAG and history:

- The head: its kind, its table (column types, row count, the L0 shape of `shapes.py`), its depth, the count of its form's reads, and the shipped node score.
- The tower: `m`, the kinds along the chain, and the count of root forms in the closure of `h`.
- The head's slot, when it has one: visits, tries, new nodes, and tries since the last new node.
- The visit that just ended: its new nodes and their tables.
- The walk features of the gold fit (head kind, band of `m`, roots on the chain), computed on the tower with the walk's definitions.

The state reads no written text order. The build order it reads is the search's own order in time, which the search made.

## What the state conditions

After each visit, the state picks one action:

- STAY: visit the head's slot again. Its queue goes on where it stopped.
- EXTEND(n): `n` is a new node of the visit that just ended. Push `n` as the new head. The new slot has:
  - scope: the closure of `n` (its form and the form's ancestors), plus `j` root forms by the shipped score. `j` is drawn from the gold fit (see below).
  - kind: drawn from `P_gold(kind | EXTEND, kind(n))`.
  - clause reads: free. A clause need not read the head. Read B took 22 of 30 cases with free reads, against 20 of 30 when each clause must read the head.
- BACKTRACK(d): cut the tower to `c_{m-d}` and open a slot on it as for EXTEND, with the kind from `P_gold(kind | BACKTRACK(d), kind(c_{m-d}))`. A form that reads two chain elements is in that scope, since the closure of the head holds them both.
- JUMP: today's `next_slot` new-scope branch: the policy's pick of `k` nodes and their ancestors, the kind by `Pool.kind`. The tower starts again from the visit's best new node.
- JUMP-EMPTY: visit the empty slot. Its queue goes on from where the first pass stopped.
- RESUME: today's resume rule, the parked slot with the best `last_rate`.

The chance of each action is a softmax of:

`logit(a) = c_a + log P_gold(mode(a), kind(a) | state after a) + log V(tower after a)`

- `P_gold` is the walk's fit. JUMP-EMPTY takes the walk's cells for a JUMP to a root form, and JUMP takes the other JUMP cells.
- `V` is the tower value (see "Fit from the search's records").
- `c_a` is one intercept per action, fit from the search's records.

When the beam is full, the tower with the lowest `V` is dropped. So the state conditions the scope, the kind and the clause's reads all at once, and the visit length comes from STAY. "Extend against go elsewhere" is a learned choice through `P_gold`, `V` and `c_a`. No step of the loop is a fixed phase.

## Fit from gold

Gold fits the topology, by the walk of `## Walk`:

1. `theta`: the softmax over the 20 cells, from the sum over walks.
2. `P_gold(kind | mode, kind(h))`: the marginal of the cells.
3. `j`: for each EXTEND and BACKTRACK step, the count of forms in `reads(f)` outside the closure of the head. This comes from the step record and the DAG. Fit `P(j | mode, kind(h), kind(f))`, with `j` in 0, 1, 2+.

The fit is order-free for the reasons in `## Walk`. It sums over the linear extensions by self-normalized importance sampling, with three rounds of refit.

Gold has no tries and no junk nodes, so it can't fit the scale of `V` or the intercepts `c_a`. Those come from the search's records.

## Fit from the search's records

### The records

These records come from each job's `work/` folder:

- `.picks`: one line per opening, with the pool size `n` and the picked node ids.
- `.visits`: one line per visit, with its `fids`, kind, `resume`, tries, new nodes and time.
- `.cover`: one line per cover event, with the gold form, the node, the draw and the time.
- `.bank`: the forms with their text, kind, depth, parents and nodes.

A visit's new nodes are the node ids from its opening's `n` to the next opening's `n`, inside one process. The bank holds the state at its last save, so nodes made after that save have no row.

### The tower value

`V(n)` scores the tower whose head is `n`. A beam keeps the towers with the highest `V`.

The label is Features-worker's tower label. Their code is in `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-value-read-heldout37-ramp22/`.

- Unit: one built node, with its ancestors through parents.
- Positive: later in the same run, a node that covers a gold form is this node or has it as an ancestor. The cover comes after the node is built.
- Horizon: the rest of the run.
- Features: taken when the node is built, from its own table and its ancestors only.
- Cover lines are expanded by `work/lm/data-study/sampler/search-worker/gold-dups/dups.json`.

The model is a cover hazard with exposure, as in the `variety/` fit:

`P(positive | n) = 1 - exp(-(alpha_self(n) + E(n) * lambda(n)))`

- `alpha_self(n)`: the logit part for "`n` itself covers". It has no exposure.
- `E(n)`: the tries in scopes that hold `n`, after `n` is built.
- `lambda(n) = exp(w . x(n))`, with `x(n)` the head and tower features of "State" and `log P_gold(EXTEND | state)`.

`V(n)` is the cover chance of the next visit's tries. For a STAY on a head that already took `E` tries with no positive, `V` falls by a gamma frailty: `lambda * a / (a + E * lambda)`, with `a` fit from the records. The frontier read shows that the cost of covers varies by a factor of 10 to 100, so `a` is small and the fall is steep. This fall sets the visit length that STAY gives, in place of a fixed patience.

What the label must give for this fit to work:

1. The node id, run, build time, and the node ids of the covers that make it positive. The fit splits the label into "`n` covers" and "a descendant covers" from these.
2. The exposure `E(n)`, or the `.picks` and `.visits` lines to compute it. A negative with `E(n) = 0` is censored, not a negative. Under today's pick most nodes have small `E(n)`. Without exposure, `V` learns where today's pick looks, and not what a tower gives when it is extended.
3. No feature from after the build. The label's rule 4 meets this.

Their label meets 3. Rules 1 and 2 need the cover node ids and the exposure in their output, or the run folders next to it. Fit on the non-held runs (N600 first), and read on the 37 and the ramp, as their rule 6 says.

### The intercepts and the gold prior on records

- `c_a`: fit by the yield of each action's visits in the records. The yield is covers per try, with the label's horizon. Today's records hold JUMP and RESUME visits, a few JUMP-EMPTY visits, and no EXTEND visits.
- A check of `P_gold` on the pool's own DAG: for each built node, whether its form reads the head of the visit before. This gives the share of the pool's builds that are an EXTEND under today's search, which is the base the arm moves.

### The recency-scope arm's records

Sampler-worker's arm opens a scope on the table just built, its ancestors and roots, for `n` openings. That is a hard-coded EXTEND with a fixed head rule (the last table built), a fixed `j` (the roots), and a STAY of `n` openings. Its records feed the fit as on-policy EXTEND data:

1. Exposure. Each head it extends has `E(n)` of `n` openings of tries. That gives `lambda` data where today's records have almost none.
2. Head choice. The head is the last table built, which no score chose. So these heads are a sample of the visit's new nodes with no selection by `V`, and the fit of `w` has no selection bias from the score.
3. Visit length. Covers by opening index `1 ... n` on one head give the hazard's fall with exposure, so they fit `a` directly.
4. The EXTEND intercept. Covers per try on its EXTEND openings, against the JUMP openings of the same jobs, give `c_EXTEND - c_JUMP`.
5. Kind. Covers by the drawn kind against the head's kind check `P_gold(kind | EXTEND, kind(h))`.

For this to work, the arm must log the head's node id and the scope's `fids` on each `picks` line, run with `SEARCH_LOG_VISITS=1`, and save the bank often enough that the heads are in it.

## Beside today's pool and pick

What the design keeps:

- `Pool`, `Slot`, `visit()`, `try_clause`, `Pool.take` and `Pool.test`.
- The policy's pick, as the JUMP action.
- `Pool.kind`, as JUMP's kind.
- The resume rule, as the RESUME action.
- The empty slot, as JUMP-EMPTY.
- The 96-form cap, and `SEARCH_HOT`. Set `B` at most `HOT`, so the beam's slots keep their runs.

What it replaces: `next_slot`'s rule, "resume with chance .3, else a new scope". The new rule is a softmax over the actions. `visit()` must return the ids of the nodes it made, so that EXTEND can take its head among them.

How it can be built: as a module like `SEARCH_SCOPE_RULE`, with `next(pool, last_visit)` in place of `next_slot`.

The init:

- The first pass is the start state: an empty beam, and a forced JUMP-EMPTY for `FIRST_PASS_SECONDS` of each kind. The first-pass arm running now is this init. After it, JUMP-EMPTY stays an action with a learned chance. Today that slot is all but left after 60 s, and the root-direct read shows it still finds forms there in seconds.
- With `c_EXTEND = c_STAY = c_BACKTRACK = c_JUMP-EMPTY = -inf`, and `c_RESUME` such that RESUME has chance .3, the rule is today's search. So each fit starts from today's search, and an arm moves away from it only by the fitted intercepts.
- The recency-scope arm is the hard-coded EXTEND. Its records start `c_EXTEND`, `a` and `w`.
- `theta_0` of the walk is the init of `P_gold`.
- The shipped node score is the init of `w`, as a feature of `x(n)`.

## The cheapest read before an arm

Two reads. The first uses records only. The second is a small run, which comes to you with its command and ETA.

### Read A: can the value choose heads within the budget?

Data: Features-worker's per-node values on round 1's bundle jobs on the 37. Add one count to their read.

- Target heads: nodes that cover a gold form `g`, where `g` has a gold child `c` whose reads are all covered at that moment. From such a node, an EXTEND can make `c`.
- Online choice: at each visit's end, extend the best new node by `V`, when its `V` is over a threshold. Set the threshold so that `E` heads per job pass, for `E` = 30 and 60. At about 120 openings per job, 60 is half the openings.
- Count: the share of target heads that are chosen.

Prediction: at `E = 60`, 40% to 60% of the target heads are chosen. The basis is that a fresh cover's read already ranks 1 to 1.5 in the pool at its first ready opening. A choice at random would take about 2% (60 of about 3,400 nodes).

Bar: under 20% at `E = 60` fails. Then the value can't afford EXTEND inside the openings a job has, and no arm runs.

### Read B: does one queue on the head's tower take the next floor?

Cases: the distinct one-read ready forms of `frontier/ready.tsv` under 18 bits, over both seeds, whose read has a node in the bank.

Each case is `root_run.py`'s search with three changes:

- scope: the gold read form and its gold ancestors,
- kind: the case form's kind,
- `SEARCH_READ_PICK` on the read form,

with a budget of 12 CPU s (three visits) and the same hit test.

Prediction: 50% to 70% are taken within 12 CPU s, with a median under 3 CPU s. The basis is root-direct (14 of 19 within 5 s) and the cost of a small context.

Result (`runs/search-chain-readB-extend-44-12cpus-mac`): with the scope of the read form, its ancestors and the roots, 20 of 30 cases under 18 bits are taken with `SEARCH_READ_PICK` and 22 of 30 without it. The median CPU to a take is under 0.6 s. The bar holds, and EXTEND reads freely. The figure is a ceiling: the head is gold's read node.

Bar: under 30% fails. Then the right head and scope don't take the next floor in an EXTEND's budget, and no arm runs.

Command and ETA: the script is `extend_run.py`, a copy of `root_run.py` with the changes above and the case list from `ready.tsv`. That needs a short build, which this design does not make. Run it as `run_heavy.py --cpus 4 <mac python> extend_run.py run --jobs 4 --budget 12`. With about 60 cases at 12 s on 4 processes, plus the load of each case, the ETA is about 5 to 10 minutes.

### The arm's gate

The projected gain per seed is the one-read ready forms with a read node in the bank (about 50 per seed), times Read A's share at `E = 60`, times Read B's share.

The cost is the JUMP openings that EXTEND takes. Round 1's curve covers 136 and 131 forms by 60 s and 180 and 175 by 600 s. With half of each minute after 60 s moved to EXTEND, the JUMP part reaches about its 330 s point, which loses about 5 to 12 forms per seed.

The arm runs when the projected gain is over that loss. At the predicted shares, the gain is 10 to 20 forms per seed, so the gate can fail on either read. The projection counts the first floor only. A form taken is a head for the floor above it, and the arm's loop rule judges that part.

## What the design can't settle

1. Transfer of the gold prior. `P_gold` is fit on gold towers, where every node is gold. The search's towers hold junk nodes. Only `V` corrects for that, and whether the product of the two orders actions well is shown only by an arm.
2. The order the fit learns. The sum over walks can settle on the walk that the model predicts best. That is a fact about gold's DAG. Whether the search builds best in that order is a separate question, which gold can't answer.
3. Off-policy data. Today's records hold almost no EXTEND visits. The recency arm gives some, with one head rule. The fit of `c_a` and `a` for a learned head rule needs the records of the first arm of this design, and a refit after it.
4. Compounding. The reads measure the first floor above a covered read. 94% to 95% of the forms not built lack an input that was never built (class A). Whether chains of EXTEND reach them is not measured.
5. Gold text in Read B. Read B's scope uses gold's read form. The pool's covering node can have other text with the same table, so Read B is a ceiling on that account.
6. The gold route. 91 of 332 covers came from a visit of another kind, and 170 of 332 came without the reads in hand. So the pool's towers can differ from gold's, and the label counts both routes, while `P_gold` knows only gold's.
7. Bits. The bits in the frontier and shallow reads are under `models-base`, and the runs use `models-tk`. The size of that difference is not measured.

## Results of the cheap reads

- Read B (`runs/search-chain-readB-extend-44-12cpus-mac`): with the scope of a ready form's read, its ancestors and the roots, 22 of 30 one-read forms under 18 bits are taken with free reads, and 20 of 30 with every clause made to read the head. The figure is a ceiling, because the head is gold's read node.
- Read A (`runs/search-chain-readA-heads-heldout37`): the tower value picks 33.9% of target heads at 60 extends a job, against 14.1% for the shipped score and 3.0% at random. 136 of the 171 heads fall in the first 60 s. After 60 s it picks 8.6% against 7.1%. So head choice is learnable only in a job's first minute.
- Arm gate: projected gain 12.4 forms per seed on all visits and 3.1 after the first minute, against 5 to 12 lost from today's pick. The gate doesn't open, and no arm runs.

