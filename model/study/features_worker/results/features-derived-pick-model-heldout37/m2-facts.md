# M2 facts: the exact definition of each feature at a pick

Reader: Sampler-worker, who builds the live switch. This file stands alone.

`X` is `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37`. The code that computes every fact is `X/feats.py` (`Scope`, `option_facts`, `gate_facts`, `drawn_state`). The model is `X/m2-export.pkl` (version `m2-cal-1`), plain numbers. `X/m2_export_use.py` scores a pick from it in plain Python, and its `main` checks that against `hook.Model` on `X/fit-cal`.

Build order is not a fact of this model. The model has no recency rank and no fact of the fid order (`rec` and `newest` are dropped). A fid enters only as the key of a form, never by its value or its rank.

## Pick

At an atom start (phase `root` or `root2`) that reaches the steer block, with `opts` the options, `ws` their weights before the steer and `rf` the kit's factors:

- D: the options with `fr.KIND[o] == 'relation'` and `ws > 0`. `n_D` is their count. The model scores only these.
- B: all other options, NOT and comparisons included.
- `T_D = Σ_D ws`, `T_B = Σ_B ws`, `T = T_D + T_B`, `Z_B = Σ_B ws·rf`, `e_o = exp(s_o)`, `E = Σ_D e_o`.
- M2: `ws'[o] = T·σ·e_o/E` for `o` in D, and `ws'[b] = T·(1−σ)·ws[b]·rf[b]/Z_B` for `b` in B. Where `E == 0`, B gets `T`. Where `Z_B == 0`, B keeps `ws`. `alt` takes the same lines with its own `ws`, and the same `s` and `σ`.
- `s_o = Σ_i beta_i · (x_i − mean_i)/scale_i` over the option's raw facts `x` (the logit). `σ = sigmoid((Σ_i coef_i · (g_i − gmean_i)/gscale_i + intercept)·temp + bias)` over the pick's raw gate facts `g`. `temp` is 1 and `bias` is 0: the gate is calibrated without them.

## rel_off picks

At INIT bodies (`rel_off`) the kit's `rf` is 1 for every option. This is checked three ways:

1. `hook.arm_weights` (B lines): `bt·w[i]·rf[i]/ZB` with `rf = 1` is `bt·w[i]/T_B`, which is P's own shape inside B scaled to `T·(1−σ)`. So B keeps P's shape at rel_off picks.
2. Training rows: at the 9,012 rel_off rows, 0 of 70,966 options have `rf != 1`, and `Z_B == T_B` exactly.
3. `job3.py`, arm `M2s`, asserts `rf == 1` at every rel_off pick it passes.

So at rel_off picks today's code leaves P's weights as they are, M1 and M2 replace the D shares there (M2 also moves mass between D and B), and the arm `M2s` leaves them. The live hook may run `M2s` only. `job3.py --arms off,M1,M2,M2s` walks both ways, and `read3.py` reports both.

## Where each input comes from

Sources in the table below:

- `dag` is `o['dag']` of the option dicts of `rel_row` (fields `readers`, `depth`, `defined`, `base`, `method`, `sibling`, `path`) and `dag_info(forms, i)`. These are filled only where `rel_dag_fill` runs, so not at rel_off picks (no `rel_row` is built there). The same graph can still be built at any pick, since `dag_info` reads the program's forms and `rel_dag_src`.
- `opt` is the other fields of the option dict: `tok`, `kind`, `name` (program name, `&grp` or `&grp.j`), `types` (the declared column types, `decl_types`), `p`.
- `key` is the token key of the atoms drawn so far in the body (`self.p_key` in the drawer, the `key` argument of `atom` and `rel_factors`). It is available at every pick, rel_off included.
- `scope_types` is the label types in scope (`self.p_scope`, the `scope_types` argument of `rel_factors`). Available at every pick.
- `state` is the drawer's head kind, `self.place`, `n.phase`. Available at every pick.
- `new` needs code that today's steer does not have.

No fact reads `pre`, the clause prefix as `rel_prefix` renders it (`body_atoms` text). Every fact of the drawn atoms is built from the tokens in `key`, so none needs `rel_prefix`, and none changes at rel_off picks. The definition used (training and read alike, `feats.drawn_state`): take the tokens of `key`. A token with `fr.KIND[t] == 'relation'` and a name `&r<digits>` is a drawn derived relation; map its name through `prog_names` (and `pg.written` for the head) to `(head, j)`, `j` None for a head relation, so the drawn set is a set of `(head, j)` and `n_d` is the count of such tokens. A token whose kind is `lib relation`, `relation macro` or `fact relation` is a drawn builtin, and `n_b` is their count. At INIT port and key bodies `key` holds the atoms drawn so far in that body, so the same definition gives the INIT body's atoms so far. `rel_dag_fill` builds `pre_bases` from `key` in the same way, at head level.

## Option facts (the logit)

`base` is the option's `(head, j)`, `f` its form (fid `h_fid(head)`), `S` the scope. The scope is the program's forms (their texts), closed under ancestors. A form's parents are the `&fN` refs in its text other than its own head, kept if in `S`. Depth is 1 + the largest parent depth (1 for a root). `H` is the head kind (DET, INIT, RULE; RIGID_DET counts as DET). A fact that is 0 is left out of the sparse dict.

| fact | definition | source |
|---|---|---|
| `ar1` .. `ar4` | one-hot of `min(max(arity,1),4)`, arity the count of table columns; none if arity is 0 | `opt['types']` for the count; the table gives the same count (parity not yet checked) |
| `lmean`, `lmax` | `log1p` of the mean and of the largest row count over the table's examples (train and test) | new: replayed table (`feats.replay`, `parse_table`) |
| `share` | share of the examples where the table has at least one row | new: replayed table |
| `ct:T` | count of columns of type `T`, for the 12 listed types (`Color`, `Position`, `Nat`, `Dir`, `Axis`, `Example`, `Int`, `Box`, `Dir8`, `Ident`, `DiagDir`, `Sym`); other types add to `ct:other` | `opt['types']` (or the table's types) |
| `blank` | the table has a column with the blank label `''` | new: replayed table labels |
| `notab` | the table did not parse (past the work cap), or the option has no scope form (then it is the only fact besides `nosc`) | new |
| `tin`, `tinf` | `tin` = count of columns whose type is in `scope_types`; `tinf` = `tin`/arity | `opt['types']` and `scope_types` |
| `nosc` | `scope_types` is empty | `scope_types` |
| `dupt` | `log1p` of the count of other options in D whose sorted type list equals this one's | `opt['types']` over D |
| `dupk` | another option in D has an equal merge key (`table_key`) | new: replayed table |
| `d1` .. `d4` | one-hot of `min(depth(f),4)` | `dag['depth']` (check the offset: training depth of a root form is 1) |
| `dmax` | `depth(f)` minus the largest depth in `S` | `dag['depth']`; the largest depth is new (a max over the graph's heads) |
| `deep` | `depth(f)` equals the largest depth in `S` | as `dmax` |
| `leaf` | no form in `S` reads `f` | `dag['readers'] == 0` |
| `root` | `f` reads no form in `S` | new (the graph's `body` for `f`) |
| `lread` | `log1p` of the count of forms in `S` that read `f` | `dag['readers']` |
| `kk:KxH` | form kind `K` of `f` times head kind `H` (9 flags) | `H` is `state`; `K` is new (`strata._depths` returns kinds, `dag_info` does not pass them on) |
| `sub` | `j` is not None (a sub-relation of an INIT form, or a method) | `dag['method']` |
| `lnrel` | `log` of the count of relations (head and sub-relations) of `f` | new: from the replay (the option list of the same base would approximate it) |
| `dr_self` | `base` is in the drawn set | `key` (at `(head, j)` level) |
| `dr_sib` | another relation of the same form `f` is drawn | `key`; `dag['sibling']` is `dr_self` or `dr_sib` merged |
| `dr_anc` | `f` is a proper ancestor of a drawn form | `key` and the graph's ancestors: new |
| `dr_desc` | `f` is a proper descendant of a drawn form | as `dr_anc` |
| `dr_par` | `f` shares a parent with a drawn form | as `dr_anc` |
| `dr_key` | the merge key equals that of a drawn relation other than `base` | `key` and the replayed table: new |
| `dr_type` | the option shares a column type with a drawn derived relation | `key`, `opt['types']` of the drawn relations |
| `x_nod_leaf`, `x_nod_deep`, `x_nod_tin` | `leaf`, `deep`, `tin` when no derived atom is drawn | as those facts |
| `x_P_leaf`, `x_P_sub`, `x_P_dmax` | `leaf`, `sub`, `dmax`, for the place `P` of the pick (`RULE`, `DET`, `port`, `key`, `other`) | `state` and those facts |
| `x_r2_self`, `x_r2_leaf` | `dr_self` and `leaf` when the phase is `root2` | `n.phase` |

`dag['path']` and `dag['defined']` are not used.

## Gate facts

| fact | definition | source |
|---|---|---|
| `hk:DET`, `hk:INIT`, `hk:RULE` | head kind one-hot | `state` |
| `pl:RULE`, `pl:DET`, `pl:port`, `pl:key`, `pl:other` | place one-hot (`self.place`) | `state` |
| `r2` | phase is `root2` (an atom under NOT) | `n.phase` |
| `lnD` | `log(max(n_D, 1))` | the pick |
| `dd`, `bd`, `both` | a derived atom is drawn, a builtin atom is drawn, both | `key` |
| `nosc` | `scope_types` is empty | `scope_types` |
| `lnf` | `log(max(count of forms in S, 1))` | `dag_info` heads before the point |
| `lse` | `LSE(s) − log(n_D)` over the scores `s` of D | the logit |
| `mx` | `max(s) − LSE(s)` | the logit |

## What needs new code

- The replayed tables of the scope's forms (row counts, labels, merge key, column types): `lmean`, `lmax`, `share`, `blank`, `notab`, `dupk`, `dr_key`, `lnrel`. In the training and read code this is `feats.replay` (a `D.Run` with `run.collect`, one replay per scope, memoized by the scope's texts). These facts carry the largest weights (`share`, `tinf`, `blank`). Where the pool already holds each form's table, it can feed them.
- The graph facts that `dag_info` does not return: the largest depth, each form's parents (for `root`, ancestors, shared parents), each form's kind.
- The drawn set at `(head, j)` level from `key` (a few lines, `feats.drawn_state`).

## Limits of the training rows that matter live

- The rows come from forms with at least one derived read. An atom under NOT (`root2`) is then a read pick in 95% of the training rows (σ is near .99 there). Live, NOT atoms of clauses with no derived read look the same at the pick, so the gate over-gives D at `root2` there.
- Every training pick has at least 6 derived options with `ws > 0`.
- The gate is calibrated on the training rows by task folds. It is not tested on picks of another distribution.
