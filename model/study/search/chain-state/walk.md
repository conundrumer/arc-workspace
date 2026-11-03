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
