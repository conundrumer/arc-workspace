# Scope loss, class C: the cause of the relation-pick gap, and the absent read relations

`REC` is `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22`. `KIT` is `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943/model/study/sampler`.

## Method

`cause/mass.py` runs `job.py`'s own code (opening, scope, target, R's inputs) and walks each measured form once, in its written order, with `or_q.walk_order`, over the recorded scope (S) and over gold's ancestors (R). At each atom start (phases `root` and `root2`) it logs every option's final weight (the steered weight that the pick reads), P's share, the relation steer's factor, the option's class (derived, lib, op), and for a derived option whether its table equals a relation of one of gold's ancestors of the form (merge key). The gold option's relation-steer features are kept. Outputs: `cause/mass.jsonl` (42 C forms), `cause/mass-covered.jsonl` (43 covered forms). `cause/split.py` reads them and writes `cause/split.tsv`. `cause/rec.py` (records only) writes `cause/rec.tsv`.

The walk totals equal the recorded S and R totals on the forms with one order (for example `142ca369 g3`: S 6.94, R 1.95). A form with several orders has one order here, so its totals differ from the records.

Split of each pick's S bits: `dilution` = -log2(1 - the share of the derived options whose table equals no relation of gold's ancestors). This is the bits that removing those options alone gives back. `reweight` = S bits - dilution - R bits: the change in the weights of the options that both walks hold.

## Question 1: what the relation pick conditions on

### The scope that R reads holds one form

- R's scope is gold's ancestors of the form: median 1 form (`cause/rec.tsv`, `anc_n`). At a pick of R, the median count of derived options is 1.
- At a pick of S, the median count of derived options is 9 (C) and 7 (covered). Of these, 7 (C) and 5 (covered) have a table that equals no relation of gold's ancestors. Median 1 equals an ancestor's relation, and that one is the gold relation.

### The non-ancestor relations take the mass, and that is the whole gap

Sums over forms, bits (`cause/split.py`):

| set | gold option | S - R gap | dilution by non-ancestor options | reweight |
|---|---|---|---|---|
| C, 42 forms | derived (read atom) | 89.3 | 85.4 | 3.9 |
| C | lib (builtin) | 94.0 | 92.4 | 1.6 |
| C | op | 7.7 | 29.8 | -22.1 |
| covered, 43 forms | derived | 69.0 | 66.0 | 3.0 |
| covered | lib | 68.7 | 53.8 | 14.9 |
| covered | op | 16.1 | 16.3 | -0.2 |

Derived options that no table map could place (INIT sub-relations whose table did not parse) hold a median share of 0.004 at a pick (mean 0.02). Counted as non-ancestor, they add 5.6 bits (C derived) and 7.8 bits (C lib) to the dilution column.

Shares at the pick, medians:

| set, gold option | gold share S / R | non-ancestor derived share in S | derived options S / R |
|---|---|---|---|
| C, derived | 0.132 / 0.625 | 0.707 | 9 / 1 |
| C, lib | 0.085 / 0.293 | 0.616 | 9 / 1 |
| covered, derived | 0.135 / 0.542 | 0.598 | 7 / 1 |
| covered, lib | 0.165 / 0.754 | 0.606 | 7 / 1 |

So the relation-pick gap is about what the extra forms' share predicts, and not more. In sum, the weights of the options that S and R both hold keep their ratios. Per form, the reweight term (derived plus lib) spreads around 0: quartiles -1.51, 0.43, 1.29 bits (C), -0.34, 0.49, 1.53 (covered). Per form, the gap correlates with the dilution at r 0.35 (C) and 0.44 (covered).

The C forms against the covered forms: the median per-form dilution (derived plus lib) is 3.97 bits (C) against 2.71 (covered), and the gap in these walks is 4.32 against 3.54. The C scopes hold more non-ancestor relations (7 against 5 at a pick) and larger scopes (8 against 6 forms). That accounts for the extra bit of C.

The gap does not track log2 of the scope's form count (r 0.05 C, -0.08 covered). The mass that a non-ancestor option takes varies by option: an INIT form gives several relations, and the steer's per-option factor varies.

### What the relation pick reads

At an atom start the final weight of an option is the product of:

1. P, the count prior (`KIT/sample2_col.py` 2187-2200). A builtin has its corpus count. Each derived relation has `(c['rel']['declared'] + port_rel) / nrel + ALPHA` (line 2197): P holds the derived total fixed and splits it evenly over the `nrel` derived options.
2. The structural weights (`struct_rel`, lines 1808-1831): `w ** 0.83 * exp(z)`, with z from the option's kind, its column types against the label types in scope, arity and repeat. `live.set_steers` sets the recency terms to 0 (`KIT/live.py` 348-349), so the slot order is not read.
3. The tilt (`tilt_root`, line 2276), from the tilt table of the point group. `Run.steer` sets the group from the deepest form of the scope (`KIT/live.py` 1194-1198): S and R had different groups on 8 of 42 C forms (S `RULE depth 3+`, R `RULE depth 2`) and 4 of 43 covered forms. This term is inside the reweight column.
4. The relation steer (`models-tk/relR4_o.pkl`, a tree model; mask `all_nogrp`, so it does not read the point group). Its factor is `exp(beta * d - logp)` (`KIT/relsteer.py` 174; applied at `KIT/sample2_col.py` 2428-2430), with `beta` 1. The `- logp` takes P's share back out, so the final weight of each option is about `exp(d)`, one score per option with no sum over the options. The model reads row-level features: P's share (`logp`, 198 splits), the rank of the option by P (`d5_prank`, 110), the mass of its kind (`d5_kind_mass`, 168), its log share against the top (`d5_dlogp`, 128), its rank and share within its kind (`f4_*`), its depth against the deepest derived option (`e3_*`, `f4_depth_*`, `dag.depth_step`), and the count of label types in scope (`c_nscope`). An INIT body has no relation steer (`rel_off`, `KIT/live.py` 1200).

### Which inputs differ between S and R

- The count of derived options (`nrel`): median 9 (C) and 7 (covered) in S, against 1 in R. Through P alone, the gold relation's share falls from 0.637 to 0.110 (C) and from 0.725 to 0.127 (covered).
- The steer does not tell the ancestor from the other derived options by much. Among the derived options at an S pick, gold's weight is 0.57 bits (C) and 0.41 bits (covered) above an even split, median. Under P alone it is 0.08 and 0.19 bits. Gold has the largest weight of the derived options at 21 of 55 C picks and 32 of 50 covered picks.
- The gold option's features that differ, S against R, at derived picks (37 paired C picks, median S - R): `logp` -1.88, `d5_prank` +1.58, `d5_kind_prank` +1.81, `f4_p_share_kind` -0.75, `e3_ntop` -1.00; in 17 pairs gold is no longer the deepest derived option (`e3_top` -1). These shifts sum to about 0 in the reweight column.

### Why a builtin's chance drops

- Under P, the derived total at a builtin pick is the same in S and R: 0.567 against 0.572 (C), 0.786 against 0.648 (covered). P's share of the gold builtin is the same: 0.051 against 0.049 (C).
- After the relation steer, the derived total at a builtin pick is 0.607 in S against 0.049 in R (C), and 0.677 against 0.118 (covered). The steer gives the lone derived option of R a low score, and gives each of the 7 to 9 derived options of S a score of its own. Because the final weight is `exp(d)` per option, with P's split taken out by `- logp`, the derived total grows with the count of derived options, and the builtin's share falls.
- At the builtin picks of `142ca369 g3` (k 1): R gives `input` a factor of e^3.06 and the one derived option e^-1.01, so `input` has a share of 0.83. S gives `input` e^0.61 and each of the 6 derived options about e^0.2, so `input` has 0.10 and the 5 non-ancestor options 0.61.

### Op picks

In C, the op picks (NOT and comparisons) have 29.8 bits of dilution and a reweight of -22.1 bits: in S the steer raises NOT against the other options, and that takes back most of the dilution. The op gap in these walks is 7.7 bits.

## Question 2: the 5 forms whose read relation is absent from the scope

Not a scope-construction bug. It is the form-level cover that class C counts.

- `Pool.scope` (`KIT/superdag.py` 199-213) adds each picked node's form and all its ancestor forms. A scope form is replayed from its whole text, so all its relations, sub-relations included, are in the scope. Nothing drops a sub-relation.
- `gold_keys` (`KIT/superdag.py` 369-387) maps the merge key of every relation of every gold form, INIT sub-relations included, to the gold form's index: `keys.setdefault(table_key(...)[0], i)` (line 379). `Pool.add_form` writes a cover event with `gold` = that form index when a new node's table equals any one of those keys (lines 277-280). The scope-loss design then counts a read as in scope when a covering node's form is in the scope (run folder `scope-loss/design.md`, "Covering nodes" and "In scope").
- So a gold INIT form counts as held when a scope form's table equals one of its relations, which need not be the relation that the clause reads. In all 5 forms, the held form is a different form whose table equals another relation of the gold form (`cause/absent.py`, records; `cause/absent2.py`, table replay):

| arm | task | g | clause reads | relation of q that the scope holds | scope form that holds it |
|---|---|---|---|---|---|
| bundle_s1 | 142ca369 | 2 | `&r1.exposed` (Boundary) | `&r1.0`, the key relation | `(RULE &f516 (input (:P *P) (:Col *Col)) (NOT (&f455 (:C Col))))` |
| bundle_s0 | dbff022c | 18 | `&r33.enclosed` (Enclosure) | `&r33.1` | `&f1569.2`, an INIT of Connectivity |
| bundle_s1 | dbff022c | 18 | `&r33.enclosed` | `&r33.1` | `&f448.2` (Connectivity), `&f942.3` (Order) |
| bundle_s0 | b5ca7ac4 | 22 | `&r33.maximal` (Order) | `&r33.2` | `(RULE &f1813 RarestColor)` |
| bundle_s1 | b5ca7ac4 | 22 | `&r33.maximal` | `&r33.2` | `(RULE &f747 RarestColor)`, `&f1669` |

No scope form in these 5 has gold's text up to names, and none is an INIT of gold's component. The same accounting gives 62 of the 173 covered forms the status "read relation not in the scope".

## What this read did not settle

- The walks here use one order per form (the written one). The split is in bits of that order, and a form with several orders has other totals than the records.
- The dilution is the bits that removing the non-ancestor options gives back with the other weights fixed. It is not a run with those options removed; the steer's row-level features would move. The reweight column, which is about 0 in sum, says that R's options keep their ratios in S.
- Which inputs of the tree model make the per-form reweight spread (quartiles about -1.5 to +1.3 bits) is not split here.
- For the covered builtin picks, 14.9 bits of the gap (36 forms) are reweight, not dilution. Their cause is not named.
