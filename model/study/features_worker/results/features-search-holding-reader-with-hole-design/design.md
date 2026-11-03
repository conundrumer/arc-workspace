# Search that holds a reader with a hole: design and cost

Terms. A typed hole (alias: hole) is one atom of a clause whose relation isn't chosen; its labels stay. A sketch (alias: held reader) is a clause body with one typed hole, kept before the hole's table exists. An open goal (alias: goal) is a sketch that proposals are split among, and M is the count of goals in a task. The sketch body is the sketch's atoms less the hole. x is the bits a form saves given its reader. A label is described by its sites, the atoms and columns that hold it. Binder marks (`*`, `^`) are no part of a hole, a sketch or a reader here: they are written facts, and which atom binds a label follows from the order a walk draws. Other terms are those of `work/measures.md`. Source tags in square brackets are listed at the end.

## Decision

The draw split can't pay, so don't build it. Ground truth forms supply the readers below, so every number is an upper bound.

1. A task has a median of 13 right goals open at once (10 to 19), and that count stays flat through a run [N]. An even split at 13 costs 3.70 bits per form. The gross saving is +.26 on RULE, +.28 on DET and +2.11 on INIT [H].
2. A search can't tell right goals from junk. To hold 47% of right goals, M is about 170 [R: Cost once the read forms exist; C].
3. One bit saved buys less than one log2 proposal. The fitted slope is .30 on RULE, .50 on DET and .12 on INIT, so the gross saving is .08, .14 and .25 log2 proposals [R: Where the base of the proposal cost goes; F]. A split costs its full log2 M in proposals.
4. Expected table recall at 13 right goals is +1.1 to +2.4 non-DET forms at 600 s, with draws for other goals taken at the base chance. The noise bound is 12. Under "subtract log2 M" it's -65 to -50 [V].
5. Links 3 and 4 don't move. With x free on every form, 0 of 37 tasks reach a worst form under 25 bits, and the median worst form goes from 118 to 114 bits [N].

One path avoids the split: a find at the pick (see that section). Its census read is large, and it carries assumptions that failed on earlier steers. It needs one read and no search run. The decision: close the sketch search, and say whether to pay for that one read.

## Cost estimate

Forms at 25 bits or more on 37 held-out tasks, mean bits per form, 95% task bootstrap, ground truth readers [H, F]. The medians of the first row are +.25, +.33 and +.65: forms of 60 bits or more give 47% of the RULE saving and 34% of the INIT saving, and those forms stay out of reach.

| Step | RULE, 180 forms | DET, 27 | INIT, 140 | Assumes |
|---|---|---|---|---|
| Gross, reader free, M = 1 | +.26 (+.07 to +.45) | +.28 (-.65 to +1.15) | +2.11 (+.65 to +3.55) | The primary number |
| Even split, M = 13, all right, reader free | -3.44 | -3.42 | -1.59 | A draw for another goal has no chance at the form |
| Share of forms with a reader under 18 bits | .36 | .26 | .33 | 18 bits is the horizon [R: Oracle context] |
| Net: M = 13, all right, reader under 18, else no goal | -1.05 (-1.39 to -.78) | -.66 (-1.36 to -.03) | -.59 (-1.14 to -.08) | A form with no goal counts 0, which favors the design |
| Net: M = 170, same | -2.39 | -1.62 | -1.81 | The same |
| Net, generous end: M = 13, reader under 18 | +.05 (+.03 to +.08) | +.11 (+.02 to +.25) | +.53 (+.29 to +.79) | A draw for another goal keeps the form's base chance |
| Net, generous end: M = 170 | 0 | +.01 | +.21 | The same |
| Generous end at M = 13, in log2 proposals | .02 to .04 | .06 to .09 | .06 to .14 | Slopes .30, .50, .12 to .78, .78, .26 |

The generous end is above the truth. A mix of tilts over situations drawn from their prior returns the prior, since the sum over S of P(S) q(F | S) is q(F). So gain tends to 0 as M grows.

Expected table recall, non-DET forms over 37 tasks at 4,522 proposals, the median of a 600 s run. Each range runs from the fitted slopes to the right cell slopes, .78 on RULE and DET and .26 on INIT, with cost at 12 bits held [V, X].

| Arm | Change |
|---|---|
| Every form has its goal at a full share, which no task can do | +13.5 to +24.2 |
| One goal per task, the best in hindsight, every proposal tilted | +5.3 to +10.5 |
| 13 right goals, generous end | +1.1 to +2.4 |
| 13 right goals, generous end, reader under 18 bits | +.7 to +1.5 |
| 13 right goals, generous end, kind pick and head columns added at +1.84 | +3.0 to +7.5 |
| 13 right goals, 80% of proposals on the current path, no chance from other goals | -11.8 to -7.5 |

The primary leaves out the kind pick (+.42) and head columns (+1.42) [H]. The column figure is a change on a marginal, not an exact change of census bits, so that row is generous [B]. As a check, base reads 73.4 and 66.2 on the two slopes, against 70 and 71 measured on the cheapest text [R: Extended cut text]. DET reads 63.7 against 52 and 54, so DET is over by about 10. No 60 s row is given, since the fit doesn't carry to another budget [M: Fitted proposal cost]. Break-even: under "subtract log2 M", a net above 0 needs a mean x above 3.7 bits at 13 goals. At the generous end, a gain past the noise bound needs M at about 2 on the right cell slopes and about 1 on the fitted slopes.

## Where a sketch comes from, and its test

Reader first or form first gives the same joint bits under one model, since -log p(F, R) has one value. Order matters only where a check between the two steps prunes. So a sketch source is judged by its check.

- OUT is a free sketch: 0 bits, 1 goal, hole type Position and Color. It holds 33 forms at 25 bits or more, x +1.29 (+1.00 to +1.61) [H]. No form that OUT reads was reached, 0 of 80 [R: Gold helper rank], and the table recall estimate is +.01 [X].
- Every other sketch is a kept prefix of a draw. `Run.body` makes a prefix with a table at each atom of a RULE or DET, and `SEARCH_FREE_STOP` gives each prefix as a clause. A sketch costs no extra proposal for that reason.

Bits to draw a form's primary reader with its read left open: the census total, less the pick of the read form, plus the choice of a derived relation at that pick. It reads one written order [E]. It's a floor, as the hole atom's site bits stay as the census paid them with the relation known.

| Read form, 25 bits or more | Forms with a reader | Median | Quartiles | Under 18 bits |
|---|---|---|---|---|
| RULE | 175 | 31.2 | 11.3 to 77.6 | 65, with 33 from OUT |
| DET | 27 | 29.2 | 16.6 to 60.4 | 7 |
| INIT | 117 | 20.5 | 14.7 to 38.9 | 46 |

Opening a read takes 4.5 bits off a reader and adds back .28 [E]. In proposals, a body at 12 bits needs about 570 in the right cell and one at 18 bits about 15,000, against 4,522 in a run [R: Where the base of the proposal cost goes]. A proposal costs .113 CPU s on EPYC 9654 [C], and .20 to .27 CPU s by the Kaggle estimate [R: Proposal rate on Kaggle]. Sketch bodies past 2 atoms are out of reach. Of 286 reader edges at 25 bits or more, the body holds 0 atoms on 21, 1 on 78, 2 on 57, 3 on 40 and 4 or more on 90 [X]. A free-stop search reached 21 of 21 ground truth prefixes of 1 atom, 8 of 18 of 2 atoms and 0 of 16 of 3 atoms at 60 CPU s on a Mac [R: Reach of gold's prefixes].

A sketch is tested before the fill, on the task's data, in one way: its body's table must be non-empty on every input, and the clause must be safe to close. `Run.body` already gates these (`try:empty`, `can_end`). The body is the only part with a table. The engine gives no table inside a port, and the decoder admits no read of an undeclared relation, so a partial clause isn't a program the engine can run. So a partial reader is checkable for being non-empty, and for nothing else. Only a fill and the OUT test after it say a reader is right.

- That test exists on 162 of 286 edges, 57%. The others are 51 INIT readers, 63 holes inside an OR, 21 empty bodies and 12 bodies that share no label with the hole, with overlap [N].
- The test has almost no power. A value join with the labels already in the body keeps 55 of 70 relations and saves .05 bits per pick, at a mean of 827 ms a pick [R: Value join set]. Table content adds +.006 at a relation pick [R: Relation pick rank]. Output need adds +.03 once the reader is known [H]. A keep score held the ground truth prefix in the top 16 on 4 of 19 reached cases and in the top 3 on 3 of 19 [R: Keep score fit on live rows].

## What a hole is

A sketch is held as text and facts, outside the engine.

- `Hole`: `sites`, a (label, type) per open column, the type from the lib signature or the body's table; `shared`, labels that also occur in the body; `own`, labels that occur in the hole only; `carried`, labels that carry OUT's Position or Color; `place`, body, OR or port.
- `Sketch`: kind, context form ids, atoms as a set with marks stripped, its `Hole`, a stable key over those atoms with labels renamed by the sharing graph, so that two atom orders give one sketch, the shared labels' values per example from the body's table, facts, and a count of draws.

A drawn form may use these facts, in terms of what the read used [H, `keys-*.json`]:

- From the read atom: its sites as labels of the reader, and the types those labels force. A filler must give those types, so `Run.body(need=...)` can bar a stop until they are present. The bar holds for the read's own types only, as a filter on relations would refuse ground truth at 198 of 1,959 picks [R: Relation pick: where the bits sit].
- From the reader, as a set: `b_role`, `b_jpair`, `b_htypes`, `b_hcoarse`, `b_rcomp`, `c_htypes`, `c_hcoarse`, `c_rcols`, `c_hknown`. The masked atom's relation, port and column names aren't facts, as they are the read form's own text. A label in `own` isn't known at a draw, so `c_` keys read less in a live sketch than in the read, which gave them the whole reader.

Those facts tilt the kind, component and relation picks of the drawn form. They read no lexical order: no atom index, no first or last atom, no binder mark. `backward_edges.py` strips the marks from labels, and no fact reads them. The census bits they are read against stay in written order, and that total holds the walk's own label choices [H: `manifest.json`].

## How goals are held and picked

M decides the result, so an arm caps it.

- Store: at most 2,000 sketches per task. Open goals: at most 4, a hard cost of 2 bits.
- Pick: by the entropy drop of the hole's content against the marginal, which is known before a draw. A `Dir` hole gives `DirDomain` .89 against .05 [H].
- Split: 80% of proposals stay on the current path, which bounds the loss on all forms at .32 bits. The other 20% go to goals in proportion to the entropy drop. An even split isn't used.
- Retire: a goal leaves after 8 proposals in a row with no new node, the visit's patience, or when a filled clause gives a new node.

Behavior of M. Right goals hold at 13 from a tenth of the proposals to the end [N], since 91% of forms at 25 bits or more stay blocked, so few goals close [B]. Junk grows with kept forms, 1,722 per 600 s task [C], so without a cap M grows with the run. A cap trades the split for recall, and both ends lose: at M = 4 the split costs 2 bits and a top 3 holds a ground truth prefix 3 of 19 times; at M = 170 recall is .47 and the split costs 7.4 bits.

## How a filled hole becomes a pool form

- The filler is a plain form. It comes through `visit`, `try_clause`, `Pool.take` and `add_form`, with the goal's tilt on its proposal, so its cover event is the normal one.
- The reader needs no forced walk. `Pool.fill(sketch, node)` writes the read atom on the node's head, with columns mapped by type, and adds the clause by the steps of `Pool.seed`: `run.collect`, `run.scope(texts)`, `relation_tables`, `table_key`, `add_form`. The decoder's text form needs marks, so that step writes them from any valid atom order, and no fact, key or tilt reads them. It counts one proposal in `pool.draws`, with `seeded=False`. The cover check is the one inside `add_form`, on the merge key. `Pool.test` then runs on the decoder at the end of that scope, and `out_search` tests a replayed scope's last form.
- ONE stays outside the search. `one_repair.repairs` runs from `Run.search` on a finished program. A hole isn't a ONE mark, and a filled reader reaches that repair through `Pool.test` as any form does. A failed fill raises `M.Fail` or `Drop`, is counted as in `try_clause`, and changes no state.

A fill try costs one to two proposals: 60 ms for a context replay, 47 ms for `take`, 93 ms for the OUT test of a kept form [C]. So testing each new table against waiting sketches is priced like drawing. With the sketch in a top 170 and the table in a top 170, a try finds a form at about 1e-5. With a top 16 and a top 5, as the keep read and the which-table read give, it finds one at about 2e-3 [R: Keep score fit on live rows; H]. The current search finds about 8e-4 per proposal [R: Extended cut text; C].

## What changes in the search

| File | Function | Change |
|---|---|---|
| `poolsearch/superdag_search.py` | `patch_search_run` (`stop_barred_`) | Offer each RULE or DET prefix with a table to the store |
| | `Slot`, `next_slot`, `visit`, `try_clause` | A slot holds a goal key; at the goal share the next slot is a goal's; `s.run.goal` is set; a kept form tries `Pool.fill` on goals it fits |
| | `after_bank`, `read_slots`, `load_rule`, `install` | `.sketches` beside the bank, so renewal keeps them; `SEARCH_HOLD=FILE`, in the pattern of `SEARCH_SCOPE_RULE` |
| `poolsearch/superdag.py` | `Pool.fill`, new | As above |
| `model/study/sampler/live.py` | `Sampler.search`, `LiveDrawer.weights`, `Run.init` | `goal=None` argument; tilt on relation and component picks |
| `model/study/sampler/search.py` | `Manager.get`, `Disk` key | Goal key in the search key, so a tilted frontier isn't reused |
| `poolsearch/hold_sketch.py`, new | `Hole`, `Sketch`, store, `facts`, `tilt` | The tables per situation of `next_form_model.py`, as a file |

These stay: `Pool.take`, `add_form`, `merge`, `test`, `table_key`, `gold_keys`, `policy.scope`, `Run.out_search`, `one_repair.py`, and the gates of `Run.body`. With `SEARCH_HOLD` unset, `install` patches nothing and search keys and state files stay as they are.

## Comparison at equal CPU

Arm against control, same priors, same pods, on the 37 held-out tasks, through the supervisor and worker. Two seeds launched together, 0 and 1000, at 60 s and 600 s. The arm changes proposal throughput, so table recall over the CPU budget decides, with paired table recall at k and `cpu seconds grow` beside it. A fill counts as a proposal. A pass is the acceptance criterion for a pool arm in `work/measures.md` as it stands: at 60 s, non-DET higher past 14 forms, wins at least twice losses, DET lower by at most 2; at 600 s, not lower, and a gain counts past 12. The two-seed bands are 9.9 and 8.5. If the first fill comes after 60 s at the median, the late lever clause applies. Beside it, report table recall by depth band with non-DET apart from DET, M through time, the share of proposals under a goal, fills tried and kept, forms found through a goal, whole covers and candidates. A gain that doesn't move whole covers is a finding, not a pass.

If the estimate is doubted, the cheapest test is an oracle context arm: ground truth readers as goals, M = right goals, no store. It reads ground truth, so it isn't a search result. If it gives under +12 non-DET at 600 s, the sketch search closes. This estimate says +1.1 to +2.4.

## Find at the pick

This is a tilt on a reader's own pick of a derived relation, with the rest of the body in hand. No goal crosses proposals, so M is 1 and no store is needed. It is a steer in `LiveDrawer.weights`. The census read at 25 bits or more, bits per form, with expected non-DET table recall at 600 s [H, V]:

| Arm | RULE | DET | INIT | Table recall |
|---|---|---|---|---|
| Hole types from the lib signature, no reader columns | +1.67 | -.29 | +2.58 | +8.1 to +13.8 |
| Hole with the reader's columns | +3.75 | -.27 | +4.40 | +23.2 to +46.1 |
| With output cover too | +4.00 | -.36 | +4.33 | +24.0 to +49.1 |

The first row is what a forward draw has. These numbers assume that the pick is known to be a derived one, that options are ground truth tables with no junk, and that the rest of the body is known. They read a written-order walk, and the tilt has no shuffled control [H]. A forward draw has only the atoms before the pick unless it holds the read back to last, and a read drawn last gives earlier atoms none of its labels to join on. Earlier steers lost most of such a gain. A model at +.39 on census picks read -.07 on pool contexts, and +.32 after a refit on pool rows. A refit at +.42 in written order read +.04 in random valid order [R: Per-relation models on pool scopes]. A rank model with prefix content saves +.37 at a derived pick [R: Relation pick rank]. If 0% to 20% of the first row carries, it gives 0 to +.5 bits.

The read: refit the which-table logit on pool rows and read it on real visit contexts, in random valid order, with junk options and no reader columns, in the harness of `features-relation-pick-per-relation-pool-scope-heldout37`. Bars as in the read it follows: under .5 bits per form at 25 bits or more closes it, and 2 bits sends it to a steer.

## What the design doesn't help

- Blocked forms. At the end of a 600 s base arm, of 411 forms at 25 bits or more, 376 have a read not found, 30 are ready and 5 are found [B]. Reads not covered is the largest term of RULE's base, 4.2 bits [R: Where the base of the proposal cost goes]. A hole gives its filler no reads.
- The context pick. A fill draws in a context the policy picks, so the wait of 3.1 bits after reads exist stays [R: Cost once the read forms exist].
- INIT's fitted base of 11.9 and slope of .12: the largest saving sits where bits buy least. Repeated tables, 1.3 bits on every kind, also stay [R: Where the base of the proposal cost goes].
- 53 of 1,011 forms have no primary edge [H: `partial.md`]. A task's worst form: INIT on 22 tasks, RULE on 13, DET on 2. Its reader is under 18 bits on 8 tasks [N].

## Sources

Paths are under `work/lm/data-study/`. Local files are in this folder; `net-read.json` counts task goals on `sampler/sampler-worker/sampler-base-cost-read-heldout37/form-rows.tsv`.

- H: `features-worker/results/features-backward-from-out-content-heldout37/`: `read-held.md`, `partial.md`, `manifest.json`, `per-form-held.jsonl`, `per-form-candidate-held.jsonl`.
- R: a named section of `work/results.md`. M: a named entry of `work/measures.md`. E: `edge-rows.jsonl`. N: `net-read.json`. F: `final-read.json`. V: `cover-read.json`. B: `blocked-read.json`. X: `final-read.json` at `cover_extra`, and `cover-read.json` at `rest_atoms_at25`.
- C: `features_holding_reader_counts.py` over the logs of `sampler/sampler-worker/sampler-pool-extended-text-pass1-600s/out-all37/base_s0`, EPYC 9654, medians over 37 tasks: 4,522 proposals, 509 CPU s, 176 visits, 1,722 kept forms.
