# Per-table feature inventory

Every per-table feature that the sampler kit and the features-worker fits compute today. This record comes from reading the code: each fact cites file:line.

## Paths

- `KIT` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943/`
- `KS` = `KIT/model/study/sampler/`
- `FW` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/`
- `M2D` = `FW/features-derived-pick-model-heldout37/` (the scratchpad copy `records/features-derived-pick-model-heldout37/` has the same `feats.py`, `m2_export.py`, `m2-facts.md` and `design.md`, byte for byte)
- `RL` = `FW/features-node-score-refit-loop/`
- `RB` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-search-finds-kinds/`

## Marks

Each row has one mark. Where a feature is computed from more than one kind of input, the first mark that applies in this list is used:

- **vs gold**: it is computed from gold. Barred from the model and from every other learned function.
- **order**: it is computed from the order of a written body or binder marks (atom index, position in a body, slot or token numbers, `*`, `^`, label names). Barred from the model and from every other learned function.
- **vs tables**: it is computed from the table and other tables (ancestors, parents, the pool, the scope, the options of one pick, the atoms drawn so far in a body).
- **with the base tables**: it is computed from the table together with the base tables.
- **alone**: it is computed from the table alone.

Terms used below:

- A **constraint model** is one choice at each factor that a parameterized table uses on one example, a factor being a ONE pick, the rows of a CHOOSE, an open parameter, a DEMONSTRATED key or an Unfold tie. A **TableRows** is a set of rows; here, the TableRows that one constraint model gives a table on one example under one assignment.
- The **model** is the learned writer of query bodies. The scorers below (the hand model, M2 and the node rank models) are other learned functions.
- Today's code parses a parameterized table into one TableRows for each example, assignment and constraint model (`KS/sample2_col.py:1249`, `parse_table`, which gives each TableRows its constraint model).
- `read_table` keys the TableRows of one assignment together by `_world_key` (`RL/features_node_read.py:39`).
- A **query feature** is computed from the text of the query that computes the table, not from the table. It is listed where it sits in a source's feature set, and is marked by what it is computed from.
- **Paint** is the operation of `KIT/policy/outfeat.py:1-5`: each row of a Position column and a Color column sets one cell on a copy of the train input (or on a blank grid of the output's size and background where the sizes differ), and the result is compared with the train output.
- The [sample contract](contract.md) writes a parameterized table as (`QueryHash`, `Name`), and it maps each `Assignment` over the DETs it depends on to a table, a Type and a set of TableRows, one per constraint model on each example; the engine keeps the first 256 assignments of each parameterized table. A `TableVector` is per (parameterized table, `Assignment`). In today's code, one parameterized table holds the TableRows of every assignment of its query. A note at the top of a section marks the features of that section that are computed across the assignments of one parameterized table, and those whose code takes one TableRows per example or merges the TableRows of constraint models. The rows state today's code.

## The scope pick's node score (the hand model)

Note: `rows_mean`, `rows_min` and `rows_max` take each train example's row count as the largest over assignments, and `same_hash` and `test_same` use the row hashes of `table_key`, which are sets over assignments (section "The union TableHash"). Under the contract's types, each is computed per (parameterized table, assignment).

Note: the table's `rows` come from `rows_with_models`, one `x_rows` item per example, assignment and constraint model. `nodefeat.features` and `outfeat.table` keep one item per example, the last in `x_rows` order (`KIT/policy/nodefeat.py:90-92`, `KIT/policy/outfeat.py:48-53`). So each feature computed from `rows` takes one TableRows per example. Under the contract's types, each is computed per TableRows and averaged over the example's TableRows (contract, `TableVector`, "Several TableRows per example").

The scope pick scores each new pool table once (`KIT/policy/policy.py:66-80`). With `NODE_SCORE` unset, as in this kit (`KIT/manifest.json`, "commit"), the score is the hand model `KIT/policy/policy_model.pkl`. Its features are `nodefeat.features` plus `outfeat.out_features` plus `outfeat.link_one` (`KIT/policy/policy.py:58-65`).

Count: the hand model has 87 features. The brief's "62 value and 22 schema features" is in no file that the search for this record found (searched: the kit, `work/lm/data-study/` records, the scratchpad records). The count 87 is in the M-H and C-shuffle model cards (`FW/features-node-rank-model-train-read-hour13-heldout37/final-models/mh.json`, `"n_features": 87`, with the names listed) and in `RL/features_node_data.py:4`. Those 87 names are the hand policy's own names (`RL/features_node_rebuild.py:116-120`, `HN = hp.names`). By mark, the 87 are 37 alone, 36 with the base tables, 13 vs tables, 1 order, 0 vs gold.

Inputs that the pool table gives (`KS/superdag.py:269-274`): `table_types` (column types in column order), `types` (sorted declared types), `arity`, `depth`, parent table ids, `examples` (per example: kind, index, row count, row hash; from `table_key`, `KS/superdag.py:108-114`), `rows` (`rows_with_models` at cap 2000, `KS/sample2_col.py:1363`), `clause` (the query's text). `policy.row` passes these (`KIT/policy/policy.py:54-56`). The train pairs come from the task (`KIT/policy/policy.py:49`).

| Feature | Computed from | Where | Mark |
|---|---|---|---|
| `arity` | count of distinct column slots of the table | `KIT/policy/nodefeat.py:84`; slots `KS/live.py:848-849`, `KS/superdag.py:273` | alone |
| `depth` | the query's DAG depth: 1 + the largest depth of the queries it uses; lowered when an equal table merges in | `KIT/policy/nodefeat.py:84`; `KS/superdag.py:247`, `KS/superdag.py:316-319` | vs tables |
| `n_parents` | count of tables of the queries the query uses | `KIT/policy/nodefeat.py:84`; `KS/superdag.py:272` | vs tables |
| `n_clauses` | set to 1 on every live call | `KIT/policy/nodefeat.py:85`; `KIT/policy/policy.py:56` | alone |
| `clause_len` (query feature) | count of `(:` in the query text: explicit sites, which a query writes where a label differs from the column name or a column holds a record (`docs/arclog/arclog.md:25-30`) | `KIT/policy/nodefeat.py:85` | order |
| `clause_atoms` (query feature) | count of `(&` and `(input` in the query text | `KIT/policy/nodefeat.py:86` | alone |
| `t_<type>`, one per column type (18 in the model: Axis, Axis4, Box, C4, Color, D4, DiagAxis, DiagDir, Dir, Dir8, Example, Ident, Int, Nat, Offset, Position, Sense, Sym) | column type list, as counts | `KIT/policy/nodefeat.py:87-88` | alone |
| `n_train` | count of train examples with a TableRows | `KIT/policy/nodefeat.py:94-97` | alone |
| `rows_mean`, `rows_min`, `rows_max` | row count per train example (the largest over assignments, `KS/superdag.py:108-110`) | `KIT/policy/nodefeat.py:100-101` | alone |
| `empty_any` | a train example with 0 rows | `KIT/policy/nodefeat.py:102` | alone |
| `one_row` | every train example has at most 1 row | `KIT/policy/nodefeat.py:103` | alone |
| `same_hash` | every train example has the same row-hash set | `KIT/policy/nodefeat.py:104`; hash `KS/superdag.py:113` | alone |
| `test_same` | a test example's row hash equals the first train example's | `KIT/policy/nodefeat.py:105` | alone |
| `test_empty` | a test example with 0 rows | `KIT/policy/nodefeat.py:106` | alone |
| `capped` | the kept rows (cap 2000) are fewer than the row count | `KIT/policy/nodefeat.py:107-108` | alone |
| `const_cols`, `live_cols`, `distinct_min`, `distinct_max` | distinct values per column, over the train rows of all examples together | `KIT/policy/nodefeat.py:109-116` | alone |
| `row_distinct` | distinct rows over all rows, train examples together | `KIT/policy/nodefeat.py:117` | alone |
| `rows_per_area` | row count over the train input's area | `KIT/policy/nodefeat.py:128` | with the base tables |
| `rows_eq_changed`, `rows_eq_ofg` | distinct row count equals the count of changed cells, of output foreground cells | `KIT/policy/nodefeat.py:129-130`; grid facts `KIT/policy/nodefeat.py:31-57` | with the base tables |
| `color_in_out`, `color_new` | a Color column's values against the output's colors, against colors new in the output | `KIT/policy/nodefeat.py:131-134` | with the base tables |
| `color_one` | a Color column holds one value | `KIT/policy/nodefeat.py:135` | alone |
| `cover` | cells of the first-type Position column over the input area | `KIT/policy/nodefeat.py:136-140` | with the base tables |
| `fg_share`, `ofg_share` | share of the Position cells in input foreground, in output foreground | `KIT/policy/nodefeat.py:141-142` | with the base tables |
| `iou_changed`, `prec_changed`, `rec_changed`, `iou_ofg` | Position cells against changed cells and against output foreground | `KIT/policy/nodefeat.py:143-149` | with the base tables |
| `is_input_color` | the Position cell set equals the cells of one input color | `KIT/policy/nodefeat.py:150` | with the base tables |
| `shape_in`, `shape_out`, `shape_live`, `shape_both_live` | 8-connected parts of the Position cells (3 or more cells) as shapes, against input objects, output objects, and output objects that changed | `KIT/policy/nodefeat.py:151-155` | with the base tables |
| `out_err`, `out_gain`, `out_exact`, `out_rec`, `out_prec`, `out_broke`, `out_oob`, `out_conflict` | paint of the best Position and Color column pair against the train outputs: wrong cells, fixed, broken, out of bounds, conflicts | `KIT/policy/outfeat.py:68-97` | with the base tables |
| `out_pair_best`, `out_pair_worst`, `out_pairs_exact`, `out_pairs_fixed` | the same paint, per train pair | `KIT/policy/outfeat.py:98-100` | with the base tables |
| `near_only_missing`, `near_only_extra`, `near_remap` | the paint misses cells only, adds cells only, or matches the output under one color map | `KIT/policy/outfeat.py:101-103` | with the base tables |
| `fill_gain`, `fill_rec`, `fill_one_color`, `near_fill` | a Position column filled with the output's most common color in those cells | `KIT/policy/outfeat.py:106-124` | with the base tables |
| `link_np` | count of parent tables already scored | `KIT/policy/outfeat.py:135` | vs tables |
| `link_parent_gain`, `link_adds`, `link_better` | the parents' best paint or fill gain, and this table's gain against it | `KIT/policy/outfeat.py:139-143` | vs tables |
| `link_new_cells`, `link_new_count`, `link_pair_union` | cells this table fixes or covers that no parent does | `KIT/policy/outfeat.py:144-147` | vs tables |
| `link_filter`, `link_grow`, `link_disjoint` | this table's cell set is a proper subset, a proper superset, or disjoint from a parent's | `KIT/policy/outfeat.py:148-151` | vs tables |
| `link_row_ratio` | row count against the largest parent row count | `KIT/policy/outfeat.py:152-153` | vs tables |

`outfeat.link_features` also computes `kid_n`, `kid_best`, `kid_best_adds` (`KIT/policy/outfeat.py:156-170`). The live policy calls `link_one` only (`KIT/policy/policy.py:63`), and the 87 names have no `kid_*`.

The kit also holds the node score file path of `KIT/policy/nodescore.py`: with `NODE_SCORE` set and features `T`, it computes the M-T features below (`KIT/policy/nodescore.py:128`, `KIT/policy/fe/features_node_feats.py`, the same file as `RL/features_node_feats.py`, sha256 b81a558e), and with features `D` the three `dp_*` facts (`KIT/policy/nodescore.py:129`).

## M2, the derived-pick model

Note: `nrows` holds a row count for each assignment, and `lmean`, `lmax` and `share` are computed over those counts. Under the contract's types, `nrows` and these features are per (parameterized table, assignment).

M2 scores each computed table option at an atom start of a body (`M2D/m2-facts.md:9-17`). Its tables come from a replay of the scope's queries (`M2D/feats.py:238-258`). Per table, the replay keeps: the TableHash `table_key(tb)[0]` (`M2D/feats.py:256`, the hash of the section "The union TableHash" below), the column labels, the column types, and `nrows`, the row count of each TableRows, train and test examples and each assignment (`M2D/feats.py:257`). The scope graph comes from the `&fN` references in the query texts, which are used only as keys of queries (`M2D/feats.py:45-74`, `M2D/m2-facts.md:7`). Facts are built in `option_facts` (`M2D/feats.py:118-175`) and `Scope._mk` (`M2D/feats.py:84-96`).

The exported model has 74 option features (`M2D/fit-cal/model.json`, `names`; written to `m2-export.pkl` by `M2D/m2_export.py:13-20`) and 17 gate features (`M2D/fit-cal/gate.json`). The 12 column types are the 12 most common in the training rows (`M2D/fit.py:76`). `rec` and `newest` are computed and then left out (`M2D/fit-cal/model.json`, `"ignore": ["newest", "rec"]`; `M2D/fit2.py:39`). By mark, the 74 option features are 37 alone, 36 vs tables, 1 order.

| Feature | Computed from | Where | Mark |
|---|---|---|---|
| `ar1` .. `ar4` | arity: count of the table's columns, one-hot, 4 for 4 or more | `M2D/feats.py:93`, `M2D/feats.py:142-143` | alone |
| `lmean`, `lmax` | log1p of the mean and of the largest row count per TableRows | `M2D/feats.py:93`, `M2D/feats.py:144` | alone |
| `share` | share of TableRows with at least one row | `M2D/feats.py:94`, `M2D/feats.py:144` | alone |
| `ct:<type>`, one per column type (12 types and `ct:other`) | column type list, as counts | `M2D/feats.py:89`, `M2D/feats.py:145-146`; `M2D/feats.py:207-221` | alone |
| `blank` | a column has the label `''` | `M2D/feats.py:94`, `M2D/feats.py:147` | order |
| `notab` | the table did not parse (past the work cap), or the option has no query in the scope | `M2D/feats.py:92`, `M2D/feats.py:135-147`; `M2D/feats.py:253-254` | alone |
| `tin`, `tinf` | count of the table's column types that are among the label types in scope of the body being drawn, and that count over the arity | `M2D/feats.py:148-149` | vs tables |
| `nosc` | the body has no label types in scope yet (no table used) | `M2D/feats.py:150` | vs tables |
| `dupt` | log1p of the count of other derived options of the pick with the same sorted column type list | `M2D/feats.py:151-152` | vs tables |
| `dupk` | another derived option of the pick has an equal TableHash | `M2D/feats.py:153` | vs tables |
| `d1` .. `d4` | the query's depth in the scope graph, one-hot | `M2D/feats.py:56-62`, `M2D/feats.py:154` | vs tables |
| `dmax`, `deep` | the query's depth less the scope's largest depth; it is the deepest | `M2D/feats.py:155-156` | vs tables |
| `leaf`, `root`, `lread` | no scope query uses it; it uses no scope query; log1p of the count of scope queries that use it | `M2D/feats.py:74`, `M2D/feats.py:95`, `M2D/feats.py:157` | vs tables |
| `kk:<function kind>x<head kind>` (9) | the kind of the table's query (DET, INIT, RULE) crossed with the kind of the query being drawn | `M2D/feats.py:158` | alone |
| `sub` | the table is an INIT output or a method of its query | `M2D/feats.py:92`, `M2D/feats.py:159` | alone |
| `lnrel` | log of the count of tables its query computes | `M2D/feats.py:77`, `M2D/feats.py:96`, `M2D/feats.py:159` | alone |
| `rec`, `newest` (computed, not in the model) | rank of the query's number among the scope's query numbers; the newest query | `M2D/feats.py:90`, `M2D/feats.py:96`, `M2D/feats.py:160` | order |
| `dr_self`, `dr_sib` | the table is drawn already in the body; another table of its query is drawn | `M2D/feats.py:162-163` | vs tables |
| `dr_anc`, `dr_desc`, `dr_par` | its query is a proper ancestor, a proper descendant, or shares a parent with a drawn query | `M2D/feats.py:164-166` | vs tables |
| `dr_key` | its TableHash equals a drawn table's TableHash | `M2D/feats.py:167` | vs tables |
| `dr_type` | it shares a column type with a drawn derived table | `M2D/feats.py:126`, `M2D/feats.py:168` | vs tables |
| `x_nod_leaf`, `x_nod_deep`, `x_nod_tin` | `leaf`, `deep`, `tin` where no derived atom is drawn yet | `M2D/feats.py:169-170` | vs tables |
| `x_<place>_leaf`, `x_<place>_dmax` (place RULE, DET, port, key, other; 10) | `leaf`, `dmax` crossed with the place of the pick | `M2D/feats.py:171` | vs tables |
| `x_<place>_sub` (5) | `sub` crossed with the place of the pick | `M2D/feats.py:171` | alone |
| `x_r2_self`, `x_r2_leaf` | `dr_self`, `leaf` where the atom is under NOT | `M2D/feats.py:172-173` | vs tables |
| Gate (17, not per table): `hk:*` (3), `pl:*` (5), `r2`, `lnD`, `dd`, `bd`, `both`, `nosc`, `lnf`, `lse`, `mx` | head kind, place, atom under NOT, count of derived options, atoms drawn so far, count of scope queries, the option scores | `M2D/feats.py:178-183`, `M2D/feats.py:194-195`; `M2D/m2-facts.md:80-92` | vs tables |

## Node score refit round 1 (feature set T)

Note: these are computed across the assignments of one parameterized table: `tb_worlds` and `tb_alt`; the use of at most 8 assignments in `read_table`; and in each `_mean` and `_min` fact, the greatest over assignments. Under the contract's types, `tb_worlds` and `tb_alt` move to the `AssignmentVector` as the count of assignments, at most 256, and the others are per (parameterized table, assignment), with one assignment.

Note: `read_table` keys its groups by assignment only, so it concatenates the TableRows of an example's constraint models into one array (`RL/features_node_read.py:88`, `104`, `111`). Under the contract's types, each fact is computed per TableRows and averaged over the example's TableRows (contract, `TableVector`, "Several TableRows per example").

Round 1 fits feature set T: `RL/fit_round.py:7`, `RL/fit_round.py:56`, `RL/fit_round.py:66`. Its card `RL/final-models/r1.json` gives `"features": "T"`, `"n_features": 153`. T is every name of `RL/features_node_feats.py` except the `Form shape` group (`RL/features_node_feats.py:143-153`). That file is the same file, by sha256 b81a558e, as `KIT/policy/fe/features_node_feats.py` and `FW/features-node-rank-model-train-read-hour13-heldout37/features_node_feats.py`. So M-T (next section) has the same 153 features.

The table enters through `read_table` (`RL/features_node_read.py:56-122`). It splits rows by assignment and by example. It splits an `Example` column into its examples and drops that column (`RL/features_node_read.py:98-106`). It uses at most 8 assignments, the 8 with the least content hash, where that hash leaves Ident columns out (`RL/features_node_read.py:43-53`, `RL/features_node_read.py:114-121`). It takes Box height and width from the row extents (`RL/features_node_read.py:90-97`). It uses an Ident column only as which rows share a value (`RL/features_node_read.py:125-129`). Test outputs are dropped before any feature code (`RL/features_node_feats.py:100-107`).

A name ending `_mean`, `_min` is one fact given two ways (`RL/features_node_feats.py:114-129`): each fact is taken per assignment and per train example, then the mean over train examples and the least over train examples, each as the greatest over assignments. A column fact is per column of the type, and the greatest counts. Position, Color and Nat columns are capped at 4 per type, chosen by content (`RL/features_node_feats.py:233-245`, `RL/features_node_feats.py:262-264`). A Position cell is `(v[0], v[2])` of its 4 values (`RL/features_node_feats.py:168-171`).

By mark, the 153 are 52 alone, 100 with the base tables, 1 vs tables, 0 order, 0 vs gold.

| Feature | Computed from | Where | Mark |
|---|---|---|---|
| `tb_t_<type>`, one per type (19 types and `other`; 20) | column type list, as counts | `RL/features_node_feats.py:19`, `RL/features_node_feats.py:253-255`, `RL/features_node_feats.py:477-479` | alone |
| `tb_n_cols` | count of columns | `RL/features_node_feats.py:256` | alone |
| `tb_worlds` | log1p of the count of assignments | `RL/features_node_feats.py:257` | alone |
| `tb_capped` | kept rows are fewer than the row count in some TableRows | `RL/features_node_feats.py:258`; `RL/features_node_read.py:84-85` | alone |
| `tb_has_example` | the table has an `Example` column | `RL/features_node_feats.py:259` | alone |
| `dp_form_depth` (query feature) | the query's DAG depth at birth | `RL/features_node_feats.py:260`; `KIT/policy/nodescore.py:128` | vs tables |
| `dp_form_reads`, `dp_kind` (query features) | count of the query's atoms that use a table, `input` included; the query's kind | `RL/features_node_feats.py:260`; `KS/superdag.py:131` | alone |
| `tb_logrows_*`, `tb_empty_*`, `tb_onerow_*` (6) | row count per train example | `RL/features_node_feats.py:285-288` | alone |
| `tb_const_*`, `tb_distinct_mean_*`, `tb_distinct_max_*` (6) | distinct values per column (Ident left out) over the row count | `RL/features_node_feats.py:289-294` | alone |
| `tb_ident_classes_*`, `tb_ident_maxshare_*` (4) | per Ident column: count of groups of rows that share a value; the largest group over the row count | `RL/features_node_feats.py:295-298` | alone |
| `tb_pos_key_*` (2) | a Position column has a distinct cell per row | `RL/features_node_feats.py:329-333` | alone |
| `tb_pos_det_color_*` (2) | a Position column determines a Color column | `RL/features_node_feats.py:334-337` | alone |
| `tb_empty_any`, `tb_empty_all` | some train example, every train example, has 0 rows | `RL/features_node_feats.py:272-275`, `RL/features_node_feats.py:426` | alone |
| `tb_rows_equal` | the train examples have equal TableRows, under a comparison that ignores row order, same-type column order and Ident cells | `RL/features_node_feats.py:276-277`; `RL/features_node_feats.py:219-230` | alone |
| `tb_alt` | count of distinct per-assignment tuples of train TableRows | `RL/features_node_feats.py:278`, `RL/features_node_feats.py:427` | alone |
| `ti_logrows` | log1p of the row count on a test example (the largest) | `RL/features_node_feats.py:444`, `RL/features_node_feats.py:462` | alone |
| `ti_empty_with_train_rows` | 0 rows on a test example and rows on some train example | `RL/features_node_feats.py:446`, `RL/features_node_feats.py:464` | alone |
| `oc_nat_in_dims_*`, `oc_nat_dims_out_*` (4) | share of a Nat column's values among the train input and output heights, widths, color counts and output object count | `RL/features_node_feats.py:299-304` | with the base tables |
| `oc_color_in_out_*`, `oc_color_new_*`, `oc_color_obg_*` (6) | a Color column's values against the output colors, the colors new in the output, the output background | `RL/features_node_feats.py:305-311` | with the base tables |
| `oc_hist_out_*`, `oc_hist_changed_*` (4) | a Color column's value histogram against the output's and the changed cells' color histogram | `RL/features_node_feats.py:312-316` | with the base tables |
| `oc_rows_eq_ofg_*`, `oc_ratio_ofg_*`, `oc_rows_eq_changed_*`, `oc_ratio_changed_*` (8) | row count against the output foreground count and the changed count | `RL/features_node_feats.py:317-321` | with the base tables |
| `oc_box_eq_out_*`, `oc_box_eq_in_*` (4) | every Box extent equals the output size, the input size | `RL/features_node_feats.py:322-328` | with the base tables |
| `oc_fits_out_*` (2) | the Position cells' span fits in the output | `RL/features_node_feats.py:370` | with the base tables |
| `pr_cover_*`, `pr_in_fg_*`, `pr_out_fg_*`, `pr_oob_*`, `pr_rec_ofg_*`, `pr_iou_ofg_*`, `pr_rec_ifg_*`, `pr_iou_ifg_*` (16) | a Position column's cells against the input area, input foreground, output foreground, the output bounds | `RL/features_node_feats.py:338-349` | with the base tables |
| `pr_prec_ch_*`, `pr_rec_ch_*`, `pr_iou_ch_*`, `pr_unchanged_*` (8) | Position cells against the changed cells | `RL/features_node_feats.py:350-355` | with the base tables |
| `pr_class_in_*`, `pr_class_out_*`, `pr_one_color_out_*` (6) | the Position cells equal the cells of one input color, of one output color; they lie in one output color | `RL/features_node_feats.py:356-361` | with the base tables |
| `pr_parts_*` (2) | 8-connected parts of the Position cells inside the input grid, over the cell count | `RL/features_node_feats.py:362-364` | with the base tables |
| `pr_shape_in_*`, `pr_shape_out_*`, `pr_shape_moved_*` (6) | shapes of those parts against input objects, output objects, output objects not in the input | `RL/features_node_feats.py:365-369`; `RL/features_node_feats.py:27-38` | with the base tables |
| `pr_fill_gain_*`, `pr_fill_rec_*`, `pr_fill_one_*` (6) | Position cells filled with the output's most common color in them | `RL/features_node_feats.py:371-380` | with the base tables |
| `pr_paint_gain_*`, `pr_paint_exact_*`, `pr_paint_rec_*`, `pr_paint_prec_*`, `pr_paint_broke_*`, `pr_paint_stale_*`, `pr_paint_wrong_*`, `pr_paint_oob_*`, `pr_paint_conflict_*` (18) | paint of the best Position and Color pair, over all train examples, per assignment | `RL/features_node_feats.py:189-216`, `RL/features_node_feats.py:381-418` | with the base tables |
| `pr_paint_best_pair`, `pr_paint_worst_pair`, `pr_paint_pairs_exact`, `pr_paint_remap` | that paint per train pair; a color map that would make it match the output | `RL/features_node_feats.py:419-431` | with the base tables |
| `ti_rows_per_area_in_range` | rows over the test input area lie in the train range | `RL/features_node_feats.py:436-445` | with the base tables |
| `ti_colors_inside` | a Color column's test values lie in the test input's colors | `RL/features_node_feats.py:448-450`, `RL/features_node_feats.py:465` | with the base tables |
| `ti_oob`, `ti_fg_share_delta`, `ti_class`, `ti_shape_in` | Position cells on the test input: out of bounds; foreground share less the train share; one input color's cells; a shape among test input objects | `RL/features_node_feats.py:451-461`, `RL/features_node_feats.py:466-469` | with the base tables |

The labels of the fit are computed from gold (a pool table is positive when it equals a table of a query of a program that solves). They are labels, not features.

## The node rank models (M-T, M-H, and their controls)

`RK` = `FW/features-node-rank-model-train-read-hour13-heldout37/`. The design is `FW/features-node-rank-model-design/design.md` (feature groups at lines 151-166). The arms are in `RK/final_arms.py:11-15`; the feature sets are selected in `RK/features_node_data.py:34-39` and `RK/features_node_data.py:67-73`. The counts come from the model cards in `RK/final-models/`.

| Model | Feature set | Count | Features |
|---|---|---|---|
| M-T (`mt.json`) | T | 153 | as the refit round 1 section above (same `features_node_feats.py`, sha256 b81a558e) |
| M-H (`mh.json`) | H | 87 | the hand model's features, as the scope pick's node score section above, computed by the hand policy (`RK/features_node_final.py:99-108`) |
| C-shuffle (`cshuf.json`) | H | 87 | as M-H, fit on shuffled labels |
| C-depth (`cdepth.json`) | D | 3 | `dp_form_depth`, `dp_form_reads`, `dp_kind` (`RL/features_node_feats.py:156-157`) |
| M-TS (`mts.json`) | TS | 319 | T and the 166 `Form shape` features below |

The `Form shape` group is in M-TS only. Each of its features is computed from the query's text, not from the table, except `sh_head_cols`. The file says it uses no `*`, `^`, label names, query numbers or order (`RL/features_node_shape.py:1`). Its vocabulary (`RL/vocab.json`, the same file as `RK/vocab.json`) has 78 relations, 20 port names and 40 op names (`RL/features_node_vocab.py:39`). The 20 port names are the column names of computed tables that queries use (for example `P`, `C`, `Col2`, `t`), and a computed table's column names are the labels of its body as written (`docs/arclog/arclog.md:31`). So the `sh_rport_*` features are computed from label names.

| Feature | Computed from | Where | Mark |
|---|---|---|---|
| `sh_atoms`, `sh_neg_atoms`, `sh_or_branches`, `sh_n_or`, `sh_cmp`, `sh_all`, `sh_if` (query features) | counts of atoms, NOT atoms, OR branches, ORs, comparisons, ALL, IF | `RL/features_node_shape.py:150-153` | alone |
| `sh_labels`, `sh_labels_multi` (query features) | count of labels; count of labels with 2 or more sites | `RL/features_node_shape.py:154-158`, `RL/features_node_shape.py:171-172` | alone |
| `sh_head_cols` | count of the table's columns | `RL/features_node_shape.py:173` | alone |
| `sh_n_input`, `sh_n_ex_input`, `sh_n_ex_output`, `sh_form_reads`, `sh_form_reads_distinct` (query features) | counts of uses of the base tables and of queries | `RL/features_node_shape.py:159-165`, `RL/features_node_shape.py:174-175` | alone |
| `sh_rport_<port>` (20 and `other`; query features) | count of uses of a query's column, by the column's name | `RL/features_node_shape.py:165-167`, `RL/features_node_shape.py:138` | order |
| `sh_op_<op>` (40, `other`, `body`; query features) | the INIT pattern or DET op name | `RL/features_node_shape.py:176-180`, `RL/features_node_shape.py:139` | alone |
| `sh_rel_<relation>` (78 and `other`; query features) | count of atoms of each lib relation | `RL/features_node_shape.py:168-170`, `RL/features_node_shape.py:140` | alone |
| `ce_reads`, `ce_distinct`, `ce_fixed`, `ce_negated`, `ce_union` (query features) | uses of tables, distinct tables used, other atoms, negated uses, an OR | `RL/features_node_shape.py:181-186` | alone |
| `ce_src_none`, `ce_src_shape`, `ce_src_colors`, `ce_src_output` (query features) | which base tables the query uses, and whether it uses the input's `Col` column | `RL/features_node_shape.py:114-125`, `RL/features_node_shape.py:187-190` | alone |

By mark, the 166 `Form shape` features are 145 alone and 21 order. M-TS's 319 are 197 alone, 100 with the base tables, 1 vs tables, 21 order.

All five fits use gold only in their labels (`FW/features-node-rank-model-design/design.md:13`, "Labels may read gold"). `RK/features_node_final.py:21` lists words barred from feature names, `link_` among them. M-H still uses the 11 hand `link_*` features: `mh.json` lists them in `banned_in_names`.

## The union TableHash (`superdag.table_key`)

Note: `table_key` takes each example's TableRows over every assignment and every constraint model as one set, and its per-example row count is the largest over those TableRows. Under the contract's types, the TableHash is per (parameterized table, assignment), with no set over assignments. Per example it covers the set of TableRows of the constraint models, and its per-example list gives the count of TableRows and the most rows over them (contract, `TableHash`; spec, "The TableHash").

`table_key(tb)` is at `KS/superdag.py:83-114`. It takes a parsed table (`KS/sample2_col.py:1249`, `parse_table`), whose items are (example kind and index, assignment, rows, extents, constraint model) (`KS/sample2_col.py:1320`). It gives two things: the TableHash, and a per-example list.

What the TableHash is computed from:

- **Column types**: the sorted list of `str(type)` of the columns (`KS/superdag.py:95`, `KS/superdag.py:114`).
- **Cell values per column**: for each column, per example, the set of that column's values over the rows (`KS/superdag.py:94-95`). This hash orders the columns and finds the columns that tie on type and values.
- **TableRows**: per item, the set of rows (no row order, no repeated rows), with the columns in the sorted order (`KS/superdag.py:102-106`). Where columns tie, it tries each order of the tied columns (at most 720 orders and 1,400,000 cells, `KS/superdag.py:50-51`, `KS/superdag.py:98-100`) and keeps the least hash (`KS/superdag.py:112`).
- **Examples**: per example, given as (example kind, example index), the set of its items' row hashes (`KS/superdag.py:103-105`, `KS/superdag.py:112`). The items of different assignments and constraint models of one example go into one set, so the hash does not use which assignment or which constraint model gave which rows.

It does not use column labels, frames, row extents, the items' constraint model numbers, or the query. The hashes are Python `hash` values, which compare only within one session (`KS/superdag.py:84`); an Ident value is the same across sessions only with `ARCLOG_IDENT_SOURCE=value` (`KS/pool_rows.py:41`).

The per-example list is `[example kind, example index, row count, row hash]`, where the row count is the largest over the example's items (`KS/superdag.py:107-110`, `KS/superdag.py:114`). The pool stores it as a pool table's `examples` (`KS/superdag.py:273`), which the hand node score uses (`n_train`, `rows_*`, `same_hash`, `test_same`, `test_empty`).

Where the key is used:

- the pool merges tables with equal keys (`KS/superdag.py:251-258`);
- M2's `dupk` and `dr_key` (`M2D/feats.py:153`, `M2D/feats.py:167`, key from `M2D/feats.py:256`);
- the union gold tables of the task-difficulty measurement read B, one per key, and their shape (`RB/outcomes.py:142-143`, `RB/outcomes.py:123-125`).

Other order-free TableHashes in the fits, for comparison:

| Key | Computed from | Where |
|---|---|---|
| `content_key` | as `table_key`, from stored rows, with each Ident value first replaced by the hash of the set of its rows without Ident columns; past 720 orders it does not permute | `RL/features_node_key.py:22-65` |
| `plain_sig` | per assignment: the column types and rows after Example, Ident, constant and repeated columns are dropped, rows and same-type columns unordered, per example index | `RL/features_node_feats.py:487-514`; stored as `plain` (`RL/features_node_data.py:54`) |
| assignment content hash | per assignment, per example, the rows sorted, Ident columns left out; picks the 8 assignments used | `RL/features_node_read.py:43-53` |

## The task-difficulty measurement read B: table facts

Note: `rows_per_ex` takes each example's row count as the largest over assignments, from `table_key`. Under the contract's types, it is per (parameterized table, assignment).

The unit of read B is one gold table of a task in one run, reached or not (`RB/fit/readb.py:1-10`). Its 15 table facts are `TABLE_COLS` (`RB/fit/readb.py:28`). They are built per gold table in `RB/fit/common.py:206-246` (`table_facts`, `pin_table_facts`), from the records of `RB/outcomes.py:181-215` (`pin_record`, the pinned program) and `RB/outcomes.py:308-385` (`union_record`, the union gold, one table per TableHash). The table shape is `shape_of(key[0], examples)` from `table_key` (`RB/outcomes.py:123-125`, `RB/outcomes.py:142-143`). Every unit is a gold table, so every fact is computed on gold's tables. The mark below is what the fact itself is computed from. By mark, the 15 are 3 alone and 12 vs gold.

| Feature | Computed from | Where | Mark |
|---|---|---|---|
| `cols` | count of columns | `RB/outcomes.py:213`, `RB/outcomes.py:383`; `RB/fit/common.py:222` | alone |
| `ident_cols` | count of Ident columns | `RB/outcomes.py:213`, `RB/outcomes.py:383`; `RB/fit/common.py:222` | alone |
| `rows_per_ex` | median over examples of the row count per example (the largest over assignments, from `table_key`) | `RB/fit/common.py:218`, `RB/fit/common.py:223` | alone |
| `n_forms` | pin: count of the pinned program's queries that make the table; union: count of union tables with its key | `RB/outcomes.py:212`, `RB/outcomes.py:382`; `RB/fit/common.py:221` | vs gold |
| `reads_forms` | count of gold queries that its queries use directly (pin only; null on union) | `RB/outcomes.py:214`; `RB/fit/common.py:221`, `RB/fit/common.py:243` | vs gold |
| `reads_tables` | count of gold tables used directly | `RB/outcomes.py:209-214`, `RB/outcomes.py:370`; `RB/fit/common.py:221` | vs gold |
| `only_roots` | every table it uses directly has depth 0 | `RB/fit/common.py:222`, `RB/fit/common.py:244` | vs gold |
| `below` | count of gold tables below it, directly or through others | `RB/outcomes.py:197-210`, `RB/outcomes.py:371-379`; `RB/fit/common.py:222` | vs gold |
| `atoms` | atoms of the pinned program's queries that make the table (null where the pinned program does not make it) | `RB/fit/common.py:159-188`, `RB/fit/common.py:238`, `RB/fit/common.py:223` | vs gold |
| `cases` | count of union cases whose program makes the key (union only; null on pin) | `RB/outcomes.py:368`, `RB/outcomes.py:382`; `RB/fit/common.py:223` | vs gold |
| `depth` | the gold query's depth from 0 (pin: largest over its queries; union: least over its union tables) | `RB/outcomes.py:169-174`, `RB/outcomes.py:193`, `RB/outcomes.py:363-364` | vs gold |
| `k_RULE`, `k_INIT`, `k_DET`, `k_other` | kinds of the gold queries that make the table | `RB/fit/readb.py:77-82`; `RB/outcomes.py:194`, `RB/outcomes.py:365` | vs gold |

The table facts also hold `bits` (`RB/fit/common.py:223`, `RB/fit/common.py:239-241`), which is not in `TABLE_COLS`.

## Other per-table features in the kit

These are the features of the kit's steers and pick fits that are computed from something of a table. Each is computed only from the table's column type list, never from its rows or the base tables (`KS/relfeat.py:3-8`, `KS/choicefeat.py:39-40`, `KS/plugins/dag/features/rk2f.py:3-5`). In the relation pick, the table is a computed table option. In the column and value picks, the table is the table or lib relation of the atom being drawn. The "label types in scope" are the types of the labels that the atoms drawn so far in the body bind.

No feature named `ti_forms` exists in the kit, in `FW/`, in `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/`, or in the scratchpad records (grep). No Ident or column type classifier was found in the kit. The kit takes an Ident column's source from the engine (`KS/sample2_col.py:191`, `KS/sample2_col.py:1574-1589`); that is a decoder rule, not a feature.

| Feature | Computed from | Where | Mark |
|---|---|---|---|
| relfeat `arity`, `no_types` | count of the option's column types; it has none | `KS/relfeat.py:132-141` | alone |
| relfeat `in_scope`, `in_scope_frac` | count and share of the option's column types among the label types in scope | `KS/relfeat.py:135-140` | vs tables |
| relfeat `none_in_scope` | none of its types is in scope, and the atom is not the first (`k == 1` is the atom index) | `KS/relfeat.py:129`, `KS/relfeat.py:140` | order |
| relfeat `x:ts:<type>\|<scope type>` | each option column type crossed with each label type in scope | `KS/relfeat.py:204-206` | vs tables |
| relfeat `t_<type>`, `c_arity` | the option's column types as a set; their count | `KS/relfeat.py:210-216` | alone |
| relfeat `b_fits_enum` | the option's types fit the column types that the last atom of the prefix bound with `*` | `KS/relfeat.py:151-156`, `KS/relfeat.py:171-172` | order |
| choicefeat `arity`, `a_arity` | count of the columns of the atom's table or lib relation | `KS/choicefeat.py:205`, `KS/choicefeat.py:281` | alone |
| choicefeat `a_frac`, `a_known` | columns the atom names over the arity; the arity is known | `KS/choicefeat.py:281-282` | vs tables |
| choicefeat `rc_<type>` | the type of the column a value fills | `KS/choicefeat.py:208-209` | alone |
| choicefeat `rc_in_scope` | that type is among the label types in scope | `KS/choicefeat.py:210` | vs tables |
| choicefeat `left`, `left_known`, `left_in_scope` | columns of the atom's table or lib relation not yet named, by column position, and their types against scope | `KS/choicefeat.py:218-221` | order |
| choicefeat `oc_<type>`, `oc_unknown` | the type of a column option | `KS/choicefeat.py:227-240` | alone |
| choicefeat `oc_in_scope`, `oc_exact` | that type against the label types in scope | `KS/choicefeat.py:236-237` | vs tables |
| choicefeat `oc_named` | that type against the types of the columns already named, by position | `KS/choicefeat.py:238` | order |
| choicefeat `tmatch`, `tcompat` | a label's type against the column's type | `KS/choicefeat.py:257-259` | vs tables |
| colfit `type_in_scope`, `type_count_log`, `type_unknown`, `stop_left_in_scope` | the column's type against the label types in scope; the types come from the gold table in the relation-pick rows | `KS/colfit.py:1-4`, `KS/colfit.py:24-29`, `KS/colfit.py:37-48` | vs gold |
| colfit `col0`, `pos_log`, `back`, `after_gap` | the column's position, and its place against the last column named | `KS/colfit.py:32-45` | order |
| valfit `type_same`, `type_differs` | a label's type against the column's type, from the gold table's types | `KS/valfit.py:1-4`, `KS/valfit.py:24-30`, `KS/valfit.py:36`, `KS/valfit.py:47` | vs gold |
| dag plugin `f3_*` | counts of grid, color, Ident, enumerable and numeric columns of the option, and how many no label in scope can fill | `KS/plugins/dag/features/rk2f.py:10-11`, `KS/plugins/dag/features/rk2f.py:331-340` | vs tables |
| dag plugin `f4_arity_pct`, `f4_depth_pct`, `f4_depth_rel` | the option's arity and DAG depth as a percentile among the pick's options | `KS/plugins/dag/features/rk2f.py:13`, `KS/plugins/dag/features/rk2f.py:407-415` | vs tables |
| dag plugin `a6_open_hit`, `a6_open_frac` | the option's types against the types of labels with one site in the prefix | `KS/plugins/dag/features/rk4o.py:11-20` | vs tables |
| `COL_TYPE` rate | the chance that an atom of a computed table names a column, by place, column type and whether the type is in scope; counted from gold state sequences (`KS/col_type_counts.py:1-12`). Used only with `ORDER_FREE` holding `col`, which this kit's arm does not set (`KIT/manifest.json`, "what") | `KS/sample2_col.py:293-294`, `KS/sample2_col.py:2097-2106` | vs tables |

## Counts by mark

Features, not rows, except where the unit says rows. Query features are counted under the mark of what they are computed from.

| Source | Unit | alone | with the base tables | vs tables | order | vs gold | Total |
|---|---|---|---|---|---|---|---|
| Scope pick's node score (hand model) | features | 37 | 36 | 13 | 1 | 0 | 87 |
| M2 option facts, in the model | features | 37 | 0 | 36 | 1 | 0 | 74 |
| M2 option facts, computed and left out (`rec`, `newest`) | features | 0 | 0 | 0 | 2 | 0 | 2 |
| M2 gate facts (not per table) | features | 0 | 0 | 17 | 0 | 0 | 17 |
| Node score refit round 1 (set T) | features | 52 | 100 | 1 | 0 | 0 | 153 |
| M-T (set T) | features | 52 | 100 | 1 | 0 | 0 | 153 |
| M-H, C-shuffle (set H) | features | 37 | 36 | 13 | 1 | 0 | 87 |
| C-depth (set D) | features | 2 | 0 | 1 | 0 | 0 | 3 |
| M-TS (set TS) | features | 197 | 100 | 1 | 21 | 0 | 319 |
| Table facts of the measurement read B | features | 3 | 0 | 0 | 0 | 12 | 15 |
| Other kit features | rows | 5 | 0 | 10 | 5 | 2 | 22 |

## What the features are computed from

Note: the row count per assignment, the count of assignments, and the equality between the assignments' train TableRows are computed across the assignments of one parameterized table. Under the contract's types, the row count is per (parameterized table, assignment), and the other two move to the `AssignmentVector` as the count of assignments, at most 256. The hand model keeps one TableRows per example and set T concatenates them (the notes of those sections). Under the contract's types, each per-example part is computed per TableRows and averaged over the example's TableRows.

The parts of a table that the features above are computed from. A per-table compression that keeps these keeps what every listed feature is computed from in the table. The parts marked "with the base tables" need the base tables too, and the parts marked "with other tables" need other tables or the query graph.

Of the table alone:

- Column type list, as a multiset; whether an Example column is present.
- Row count per example, train and test, per assignment; count of assignments.
- Whether the kept rows are fewer than the row count (the 2000-row cap); whether the table parsed at all.
- Per column: count of distinct values; constant or not (Ident columns left out).
- Share of distinct rows.
- TableRows equality between examples, and between the assignments' train TableRows (under row order, same-type column order and Ident values left out).
- Per Ident column: sizes of the groups of rows that share a value (never the values).
- Per Position column: the set of cells per example; whether each row has a distinct cell; whether it determines a Color column.
- Per Color column: the value set and the value histogram per example.
- Per Nat column: the value set per example.
- Per Box column: the height and width extents per row.
- Column labels: only whether the blank label `''` is present (marked order).

With the base tables:

- Row count against the input area, the changed-cell count and the output foreground count.
- Position cells against the base tables: bounds, input foreground, output foreground, changed cells, the cells of one input or output color, one output color, 8-connected parts and their shapes against input, output and moved objects.
- Paint of a Position column with a Color column onto the train inputs against the train outputs: fixed, broken, stale, out of bounds, conflicts, per pair, a color map; fill of a Position column with one color.
- Color values against output colors, new colors and the output background; Color histogram against the output's and the changed cells'.
- Nat values against the grid heights and widths, the count of colors and of output objects.
- Box extents against the input and output sizes.
- Test input: rows per test input area against the train range; Color values inside the test input's colors; Position cells against the test input.

With other tables:

- Equality of TableHashes (`table_key`) with other tables: the pick's other options, the tables drawn in the body, the pool.
- Column type list against other tables: the label types in scope of the body, the other options' type lists, the drawn tables' types.
- Against the parent tables: their cell sets (subset, superset, disjoint, new cells), their paint gain, their row counts.
- Place in the dependency graph: depth, count of parents, count of the queries that use the table, leaf, root, ancestor, descendant, shared parent with a drawn table, depth against the scope's largest.

Of the query that computes the table, not the table: its kind, its count of atoms that use a parameterized table, the count of parameterized tables it computes, whether the parameterized table is an INIT output or a method, and the `Form shape` counts of M-TS.
