# Sample data build: spec

Status: record. Nothing here is built or run. This spec serves the item "The sample data build" of the [redesign proposal](../proposals/redesign-proposal.md) ("Code changes in build"), with the [sample schema](schema.md) and the [per-table feature inventory](inventory.md) as its inputs. The schema's sections "Settled" and "The canonical text" are fixed here.

The spec proposes the code that the job needs. It moves code out of record folders into a study package where that makes the build simpler, and it changes `gold_union_walks.py` and the map mode of the kit-union-read worker.

Each fact cites file:line. Each estimate says "est." and gives its basis.

## Paths

- `GU/` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/`
- `UN/` = `/Users/davidlu/code/arc-workspace/model/study/gold/reads/union/`
- `KIT/` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943/`; `KS/` = `KIT/model/study/sampler/`; `POL/` = `KIT/policy/`
- `SW/` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/`
- `KUR/` = `/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read/` (the replay that writes the merge maps)
- `RL/` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/` (set T)
- `M2D/` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-derived-pick-model-heldout37/`
- `SAM/` = `/Users/davidlu/code/arc-workspace/model/study/sampler/` (the repo copy of `form_orders.py` and `or_q.py`)
- `NEW/` = `/Users/davidlu/code/arc-workspace/model/study/samples/`, a new package for the modules this spec adds
- `OUTD/` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/samples/`, a new folder for the build's outputs
- `POD` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-cover-refit-heldout37/pod-rows/MANIFEST.md`

## Terms

- A **graph table** is one line of `GU/graph-tables-SET.jsonl`, named by its field `table`. A **graph query** is one line of `GU/graph-prods-SET.jsonl`.
- A parameterized table is written as (`QueryHash`, `Name`), and a base table by its name (the contract, `ParameterizedTable`). A parameterized table maps each `Assignment` over the DETs it depends on to a table (its Type and a set of TableRows), and the engine keeps the first 256 assignments of each parameterized table. A table is keyed by (parameterized table, `Assignment`) and holds the set of TableRows, with the Example column in each row. The `Assignment` is written as a sorted tuple of (DET `QueryHash`, value hash). There are no assignment columns. A DET with several values has one key for each value. For each (parameterized table, `Assignment`), the engine's export writes the TableHash and plain row counts, and the `TableVector` once the export computes features. The new export has no count cap, and no table is counts-only at any assignment: the hash, the counts and the `TableVector` come from the full rows of every table at every assignment. An export for feature development also writes the full set of TableRows as the row store record. Until the switch, the `TableVector` and the `QueryVector` are computed in the Python feature build, over the row store (the contract, `RowStore` and `TableVector`).
- The **TableHash** of the contract, as part 2 computes it, is a hash of one table at one assignment, its types and its set of TableRows (one TableRows per constraint model on each example, the Example column in each row), that compares across sessions. It is a measurement, never an identity. Its string is written `table_hash`.
- A **table instance** is one table of one query of one program at one assignment, that is, one (parameterized table, `Assignment`) of that query, as one replay computes it.
- A **header-only table** exists only in the old export layout, behind its flag, during the switch. Under the new export every table has its full rows. In the old layout, it is a table whose replay gives no rows: the engine exports it as counts (a table at an assignment with more than 10,000 rows, proposal, "Measured"), or the replay does not finish it. `parse_table` raises `M.Fail` for it; for a table exported as counts the error holds the table's labels and types (`KS/sample2_col.py:1283-1291`).
- The **base tables** are input, ex_input and ex_output (proposal, "The objects and the signature"). The lib's relations and components are operators in a body, and none is in the state.
- The **export** computes each parameterized table at each `Assignment`, in the engine. Until the switch, it is the current replay (part 2). Under the new export, it writes for the model and the state search the `TableVector`, the TableHash and plain row counts of each (parameterized table, `Assignment`), all from the full rows, with no rows in the output.
- The **row store** is, per (parameterized table, `Assignment`), the TableHash, the full set of TableRows, and plain counts (the contract, `RowStore`). The old layout's row store keeps the count cap of the current replay (part 2). An export for feature development writes it once per run.
- The **feature build** is the Python code that reads the row store and writes vectors (part 1). It is the development path: a feature change runs it and does not run the export.
- The **switch** is the change from the current replay to the new export. Until it, the sample build takes vectors from the feature build. After it, the sample build takes TableVectors from the export. The split and the state-sequence generator do not depend on it.

## Part 1. The per-table feature function

### What it computes

A feature is written once, in the crate `engine/arclog-features`, which has no engine dependency. Its inputs are the column types as codes, the cells as i32 in the export's encoding, the rows grouped on the Example column, and the train grids. The export calls the crate. The crate exists, with 12 row-count features, in a worktree that is still being edited. A small separate Python module, `NEW/features_py.py`, calls the same functions over the row store. Its rebuild takes about 5 to 15 s (est., Sampler-worker). The full wheel is rebuilt only when a feature set is adopted. The first features in the crate are the row-count ones: the log mean and max of rows over the train examples, the share of train examples with rows, the empty flags, the mean, min and max of rows, `one_row`, and the mean and max of TableRows per example. The rest of the feature table goes in as Features-worker develops it in Python.

The rest of part 1 is that Python development path. It runs over the row store (part 2), so a feature change does not run the export. A feature that settles moves into the crate. Under the new export, the export computes the `TableVector` of each (parameterized table, `Assignment`), and the sample build takes the vectors from the export (the contract, `TableVector`).

`table_vec(types, x_rows, ctx) -> dict[name, float]`, NaN where a fact has no value.

- `types`: the column types, in the column order of the TableHash (part 2). The function takes no labels.
- `x_rows`: one item for each TableRows, `[[example kind, index], rows, row count, {DET slot: rows}, constraint model, extents]`, the format of `rows_with_models` (`KS/sample2_col.py:1363-1371`). Set T used it at cap 2000 (inventory, "The scope pick's node score", `rows_with_models` at cap 2000); that cap is the old layout's. Under the new export the items hold the full rows. The items of one table at one assignment: the train and test examples at that assignment, one item per constraint model on an example, built from the table's row store record. `table_vec` groups the items on the example and takes an example's items as its set of TableRows, with equal TableRows being one, and applies the contract's rule (contract, `TableVector`, "Several TableRows per example").
- `ctx`: the base tables of the task, as `TaskCtx` builds them (`RL/features_node_feats.py:100-107`): the train pairs and the test inputs. `TaskCtx` drops each test output before any feature code gets the task, so the function cannot use a test output.
- For a header-only table (old layout only), the row store record has plain counts and no TableRows, `x_rows` is None, and the function gives the type facts and `counts_only` = 1, with every other fact NaN.

It takes no query body, no depth, no parents and no labels, so it uses no label, no mark and no order of a query. Column order is the one fixed by the TableHash, which depends only on content (part 2).

### Coverage of "What the features are computed from"

Each row of the inventory's section "What the features are computed from" (inventory lines 294-330), with its source in the vector:

| Inventory row | In the vector | Source |
|---|---|---|
| column type multiset; Example column present | `tb_t_*`, `tb_n_cols`, `tb_has_example` | set T (`RL/features_node_feats.py:253-259`) |
| row count per example, train and test, per assignment; count of assignments | `tb_logrows_*`, `tb_empty_*`, `tb_onerow_*`, `ti_logrows`; new `all_logrows_mean`, `all_logrows_max`, `nonempty_share` (M2's `lmean`, `lmax`, `share` over every TableRows of the table, `M2D/feats.py:93-94`, `144`). `tb_worlds` is not in the vector: the count of assignments, at most 256, is a feature of the `AssignmentVector` (the contract, `AssignmentVector`) | set T and new |
| kept rows fewer than the row count; whether the table parsed | `tb_capped`; new `counts_only` (M2's `notab`, `M2D/feats.py:92`). Both are for the old layout; under the new export each is 0 for every table | set T and new |
| per column: distinct values, constant (Ident left out) | `tb_const_*`, `tb_distinct_*` | set T (`RL/features_node_feats.py:289-294`) |
| share of distinct rows | new `row_distinct` (hand `row_distinct`, `POL/nodefeat.py:117`) | new |
| TableRows equality between examples and between assignments | `tb_rows_equal`; new `test_same` (a test example's TableRows equals the first train example's, `POL/nodefeat.py:105`), on the stable per-example digest of part 2. Equality between assignments is not in the vector: `tb_alt` moves to the `AssignmentVector` as the count of assignments | set T and new |
| per Ident column: group sizes | `tb_ident_classes_*`, `tb_ident_maxshare_*` | set T |
| per Position column: cells, a distinct cell per row, determines a Color column | `pr_*`, `tb_pos_key_*`, `tb_pos_det_color_*` | set T |
| per Color column: value set and histogram | `oc_color_*`, `oc_hist_*`; new `color_one` (`POL/nodefeat.py:135`) | set T and new |
| per Nat column: value set | `oc_nat_*` | set T |
| per Box column: extents | `oc_box_eq_*` | set T |
| column label `''` | left out: marked order | settled call |
| with the base tables: row count against input area, changed count, output foreground count | `oc_rows_eq_*`, `oc_ratio_*`; new `rows_per_area_mean`, `rows_per_area_min` (hand `rows_per_area`, `POL/nodefeat.py:128`) | set T and new |
| Position cells against the base tables (bounds, foreground, changed cells, color classes, parts, shapes) | `pr_*` | set T |
| paint and fill | `pr_paint_*`, `pr_fill_*`; new `near_only_missing`, `near_only_extra`, `near_fill`, `out_gain` from `outfeat.out_features` (`POL/outfeat.py:58-124`) | set T and kit |
| Color values against output colors, new colors, background, histograms | `oc_color_*`, `oc_hist_*` | set T |
| Nat values against grid sizes, color counts, object counts | `oc_nat_*` | set T |
| Box extents against sizes | `oc_box_eq_*` | set T |
| the test input | `ti_*` | set T |
| with other tables | not in the vector. Use edges and depth are state fields (part 4); the link facts are per graph query (below); `kid_*` are computed when a sample loads | part 2, part 4 |
| of the computing query (kind, atom counts, count of parameterized tables it computes, whether the parameterized table is an INIT output or a method, `Form shape`) | left out: these go with the target | settled call |

Several TableRows per example: each per-example fact is computed per TableRows and averaged over the example's TableRows, and two new names give the mean and the max over examples of the count of TableRows per example (contract, `TableVector`, "Several TableRows per example"). Set T's `read_table` concatenates an example's TableRows, and the hand facts and `outfeat` keep one TableRows per example (inventory, the notes of "The scope pick's node score" and "Node score refit round 1"). So `NEW/tread.py` keeps each TableRows apart, and `NEW/tfacts.py` and `NEW/tablevec.py` compute each per-example fact per TableRows.

Set T's `dp_form_depth`, `dp_form_reads` and `dp_kind` (`RL/features_node_feats.py:260`) are left out: the first is a state field, the other two are computed from the query's body. The vector is the 150 names of set T less those 3, less `tb_worlds` and `tb_alt`, plus about 16 new names: about 164 in all (est., from the table above and the two counts of TableRows). The build writes the exact name list and its sha into the manifest (part 7).

### The link facts

`link_*` (`POL/outfeat.py:131-153`) are computed from a parameterized table and the parameterized tables its computing query uses. On a state, a parameterized table's computing query is fixed (part 3), so the link facts are a value per graph query. They are computed per assignment, against the tables of the used parameterized tables at that assignment, restricted to the DETs each depends on. Where an example has several TableRows, they are computed per pair of TableRows on that example and averaged over the pairs (contract, `QueryVector`). They combine over the query's assignments, at most 256, by the aggregates of the contract ("Assignments"). The feature build computes them per graph query, from the paint state that `outfeat.out_features` returns for each TableRows of each table at each assignment (gain, fixed cells, cells, rows). It takes a query's used parameterized tables from the `reads` of its graph query, `graph-keys.parquet` and the `instance` records (part 2). `kid_*` (`POL/outfeat.py:156-170`) depend on which parameterized tables of the state use the parameterized table, so the loader computes them from the `out_gain` of those parameterized tables (part 4).

### Code

| File | Change | Lines |
|---|---|---|
| `NEW/tread.py` | copy of `RL/features_node_read.py` (129 lines), with the rows taken from the row store record. `read_table` keeps one array per (example, TableRows), where the copy concatenates them (`RL/features_node_read.py:104`, `111`); equal TableRows are one. It uses no Python `hash` (the assignment order uses `zlib.crc32`, `RL/features_node_read.py:43-53`) | 129 copied, 15 changed (est.) |
| `NEW/tfacts.py` | copy of `RL/features_node_feats.py` (514 lines) less the `Form shape` import and `with_shape`, line 260 (`dp_*`) and `plain_sig` (487-514). `node_features` becomes `t_facts(types, x_rows, ctx)`. Each per-example fact is the mean over the example's TableRows | about 450 copied, 40 changed (est.) |
| `NEW/tablevec.py` | `table_vec`; the new facts above, with the two counts of TableRows; calls `outfeat.out_features` once per TableRows, with a dict `{table_types, x_rows}` that holds one item per example, and the train pairs (`POL/nodefeat.py:60-62` loads train pairs only), then averages per example; the header-only path; `NAMES` | 180 new (est.) |
| `NEW/linkfacts.py` | `link_vec(state, parent_states)`, a call of `outfeat.link_one` (`POL/outfeat.py:131`) per pair of TableRows on one example, averaged over the pairs, with `link_np` taken out, since on a state it equals `n_parents` (schema, "State", `link_np` row) | 45 new (est.) |
| `NEW/feature_build.py` | the driver of the feature build: per task, it reads the `rows` and `instance` records (part 2), calls `table_vec` once per `table_hash` with its columns in `col_order`, `link_vec` once per new identity, and the same for the base tables, and writes the task's feature file (part 2) | 70 new (est.) |
| `engine/arclog-features` | the crate of part 1, with the row-count features first | not estimated |
| `NEW/features_py.py` | the small Python module that calls the crate's functions over the row store | not estimated |

The copies leave the files in `RL/` as the record of the fit. `NEW/` imports `POL/outfeat.py` and `POL/nodefeat.py` from `KIT/` by path, and the manifest records their sha.

Not reused: `nodefeat.features` (`POL/nodefeat.py:82`) as a whole. It needs `depth`, `parents`, the query text and session row hashes (`examples`), so a call needs a table record made up for it. The 5 hand facts that set T lacks are about 25 lines in `NEW/tablevec.py`.

## Part 2. The export of the union replay

### The replays that compute tables today

| Replay | What it does | Source |
|---|---|---|
| the union run's table compare | `gold_union.one` replays the task's whole union text once, in a `Bar` session, through `find_pairs` and `form_tables`. Past 400 identities it does not replay and merges by identity | `UN/gold_union.py:166-173`, `UN/gold_union.py:19`; `gold_final_dedup.py:90`, `131-134` (in `work/lm/data-study/gold/gold-v3-combined-cut/dedup-final/`) |
| `Bar.walk` | steps a program's tokens and calls `arclog.step_tables` after each, to get the OUT rows | `model/study/gold/cover_forms/gold_cheapest_common.py:70-86` |
| `reach2.key_tables` | per case, a fresh session (the comment at line 46 says a case replayed after another in one session loses the tables of its later queries), `Run.scope` over the case's queries with `collect`, then `parse_table` and `table_key` of each table, keyed `"<union key>:<output>"` | `SW/runs/search-union-reach-ramp22-heldout37/reach2.py:42-64` (`SW/` = `work/lm/data-study/sampler/search-worker/`) |
| the map mode of the kit-union-read worker | per task, one worker process; `union_keys` replays each distinct program with `run.scope` and `collect`, and for each table writes `table_key(...)[0]` with (union key, output, engine index) | `KUR/build.py:27-58`, `60-71`; run by `KUR/build_map.py:15-38` |

The graph table names come from the map mode: `gold_union_graph.py` takes each `table_key` value of `maps-SET.jsonl` as the name `m` followed by that value (`UN/gold_union_graph.py:327-335`; docstring line 7). The merged training graph does the same: its first lines name `m-8482916480805934741` and `m6232436497628105190` (`GU/walk-states-training.jsonl`, lines 2-3), and 23,166 of its 23,817 graph tables have an `m` name (grep of `GU/graph-tables-training.jsonl`). The other 651 keep the union key, or `key.port` for an INIT output.

So the export goes into the map mode: until the switch, the export is the map mode with `TableSink`, and it writes the row store and the `instance` records. Then a table's TableHash and its graph name come from one table instance, and a replay that the map lost is a table that has no key (the check below finds it). The map mode sets `ARCLOG_IDENT_SOURCE=value` (`KUR/build_map.py:12`), as `reach2.py` does through `job.py` (`work/lm/data-study/features-worker/results/features-scope-loss-c-read-heldout37-ramp22/job.py:58`). The union run's `Bar` session does not set it (`gold_cheapest_common.py:62-63`), and its table compare is not the kit's `table_key`, so it is not used.

`parse_table` and `table_key` of the map mode's kit (`KUR/kit-union-read-79af0a4f2/model/study/sampler/`) equal those of `KS/`: a `diff` of the two function bodies in both kits prints nothing.

### The TableHash

`table_hash(tb) -> (table_hash, example_keys, col_order)`, in `NEW/table_hash.py`. It hashes one table at one assignment: its types and its set of TableRows. It takes no set over assignments. It groups the items on the Example column: an example's items at that assignment, one per constraint model, are its TableRows. The grouping key (kind, index) is hashed in step 5, so the hash covers the Example column. It follows the steps of `table_key` (`KS/superdag.py:83-114`), with BLAKE2b (`hashlib.blake2b`, 16-byte digest) over a fixed byte encoding in place of Python `hash`:

1. Each cell is a signed 64-bit little-endian int. The cell values are the `int32` values that `parse_table` gives (`KS/sample2_col.py`, `V = memoryview(...).cast('i')` in `parse_table`).
2. A column's digest: H(`col`, the type's `str`, then for each example in sorted (kind, index) order the digest of the sorted set of that column's values over the rows of the example's TableRows).
3. Column order: sorted by (type, column digest). Columns that tie on both form groups. Where the count of orders of the groups is over 1 and at most `KEY_ORDERS` 720, and the cells to hash are at most `KEY_CELLS` 1,400,000 (`KS/superdag.py:50-51`, `97-100`), each order is tried; else the sorted order alone.
4. For one column order, the digest of one TableRows is H(the sorted set of its rows, each row in that order), and an example's digest is H(the sorted set of the digests of its TableRows at that assignment). Equal TableRows are one.
5. body = the least, over the tried orders, of H(the sorted list of (example kind, index, example digest)).
6. `table_hash` = `"s1:"` + hex of H(the sorted type list, body). `s1` is the version of this definition.
7. `example_keys`, grouped on the Example column, one item per example = `[kind, index, the count of the example's distinct TableRows, the most rows over them, example digest]`, in the layout of `table_key`'s second part (`KS/superdag.py:107-114`) with the count of TableRows added. `col_order` = the column indices in the order that gave the least body.

So two tables have one `table_hash` exactly when they have equal types and equal sets of TableRows, less hash collisions. `table_key` takes each example's items, over every assignment and every constraint model of the query, as one set of row hashes (`KS/superdag.py:103-105`). So for a query with one assignment, two tables have one `table_hash` exactly when `table_key` gives them one key in one session, less Python `hash` collisions. Ident cells are the same across sessions only where `ARCLOG_IDENT_SOURCE=value` (`KS/pool_rows.py:41`). The export refuses to start where that variable is not `value`.

In the old layout, a header-only table gets `table_hash` = `"h1:"` + hex of H(task, the sorted type list, the sorted member names of its graph table). This key has no content, so it compares only within the task. The member names are union keys, which serve here as row identifiers only (schema, "Target queries", last list).

### The base tables

The state holds the base tables (input, ex_input, ex_output), so each gets a vector. Per task, the export replays one probe program of three queries that copy them, with the fields that case texts write for them (grep of `GU/union-keys-37.jsonl`):

```
(RULE &g0 (input (:P *P) (:Col *Col)))
(RULE &g1 (ex_input (:E *E) (:P *P) (:Col *Col)))
(RULE &g2 (ex_output (:E *E) (:P *P) (:Col *Col)))
```

Each table gets a `table_hash` and a `rows` record from the export, and a vector from the feature build, under the names `input`, `ex_input` and `ex_output`.

### What the export writes and what the feature build writes

The export writes, per task, two record kinds, in `OUTD/side/SET/<task>.jsonl.zst` (one file per task, written whole: a temp file, then a rename). The `rows` records are the row store. The new export writes no `rows` records for the model and the state search.

| Record | Fields | One per |
|---|---|---|
| `rows` | task, `table_hash` (the TableHash), `counts_only`, `example_keys`, the column types and the full set of TableRows in the order of `col_order` (in the old layout, under the count cap, and absent where `counts_only`), plain counts (the rows of each TableRows and the count of TableRows of each example) | distinct `table_hash` in the task |
| `instance` | task, program sha, query index, output index, union key, engine index name (as the map writes them, `KUR/build.py:47-50`), query identity (`forms_of`, `UN/gold_union.py:47-60`), `QueryHash`, `name` (the output `Name`), kit name `m<table_key(tb)[0][1]>`, the `Assignment`, `table_hash`, `labels` (the column labels in `col_order`) | table instance, that is, (parameterized table, `Assignment`); at most 256 per parameterized table |

The `instance` record holds the query identity, so a change of union key order needs no new replay (part 7). `labels` in `col_order` give each column's place in the content order, for the canonical text (part 3).

The feature build reads a task's `rows` and `instance` records, `graph-keys.parquet` and the `reads` of the task's graph queries (`GU/graph-prods-SET.jsonl`). It writes, per task, two record kinds in `OUTD/feat/SET/<task>.jsonl.zst` (a temp file, then a rename):

| Record | Fields | One per |
|---|---|---|
| `table` | task, `table_hash`, `counts_only` (old layout; 0 for every table under the new export), `vec` (in the order of `NAMES`), `paint` (per TableRows of each example, the state of `outfeat.out_features`: gain, fixed cells, cells, rows; for the link facts) | distinct `table_hash` in the task |
| `link` | task, query identity, link vector (part 1) | distinct query identity in the task |

### Mapping a TableHash to a graph table name

`NEW/graph_keys.py` joins the `instance` records to `GU/graph-tables-SET.jsonl` and writes `OUTD/SET/graph-keys.parquet` (task, graph table, query identity, `QueryHash`, `name`):

- A replayed parameterized table (`QueryHash`, `Name`) has a map {`Assignment` → `TableHash`}, from its `instance` records. A graph table joins to the replayed parameterized table whose map equals the graph table's map (the contract, `Sample`). The graph holds that map only after dataset-worker's rebuild of the union graph (the contract, a call for the director).
- A graph table's name is the union key, or `key.port` for an INIT output, by the rule of `UN/gold_union_graph.py:322-325`. That rule moves into a function `member_name` that both modules call.
- This holds on the ramp, the 37 and training alike, since the merged training graph uses the same names (above).

Checks, each a non-zero exit with the list of tables:

- Each graph table without `kit_unreachable` has a map equal to exactly one replayed parameterized table's map, or the build stops.
- In the old layout, every `kit_unreachable` graph table (0 on the ramp, 19 on the 37, 348 on training: grep of `GU/graph-tables-SET.jsonl`) has an `h1` key and a header-only vector. Under the new export each has its full rows, an `s1` key and a full vector.
- Two graph tables with one map are counted and written in the manifest. They are equal parameterized tables that the graph did not merge.

### The TableHash across sessions and machines

The check before the run replays 3 tasks twice, in two fresh processes, and compares every `table_hash` and vector. On a pod, it compares the pod's keys with keys written on the Mac (the method of `POD`, "Check (before the run)"). The two engine builds have one source (`POD`, "Engine").

### Code

| File | Change | Lines |
|---|---|---|
| `NEW/table_hash.py` | `table_hash`, as above | 90 (est.) |
| `NEW/side_tables.py` | `TableSink` (the old layout's export, until the switch): takes each table instance from the map mode (the `ct`, slot index, program, query index, output, union key, engine name), calls `parse_table`, `rows_with_models(tb, 2000)`, `table_hash` once per (parameterized table, `Assignment`) of the instance, for the parameterized table's first 256 assignments in the engine's order, and `table_key`; runs the base-table probe; writes the `rows` and `instance` records of the task file. It calls no feature code | 150 (est.) |
| `KUR/build.py`, the string `WORKER_UNION` | in `union_keys`, where `ARC_UNION_TABLES_OUT` is set, pass each table instance and each `M.Fail` to `TableSink` (lines 45-56); close the sink before `sys.exit(0)` (line 71). The patch imports `NEW/side_tables.py` by path | 15 changed (est.) |
| `KUR/build_map.py` | set `ARC_UNION_TABLES_OUT` and `PYTHONPATH` for `NEW/`; skip a task whose side file holds the sha of its record (`src`, as line 49 does for maps); print rate and ETA per task (line 59 prints the time so far only). Today a task whose record is text-level gets no map run (line 47, `r['merged'] != 'text'`); with the export set, those tasks run too and write a side file and no map line | 25 changed (est.) |
| `UN/gold_union_graph.py` | move lines 321-337 (the name and alias rule) into `member_name` and `aliases(SET)` | 15 changed (est.) |
| `NEW/graph_keys.py` | the join and its checks | 120 (est.) |

The replay itself does not change: the export only uses what `union_keys` already computes. The map mode then writes its map and the side files in one run.

## Part 3. The state-sequence generator and the canonical text

### State sequences

`UN/gold_union_walks.py` makes the state sequences. Each step adds the heads of one enabled graph query, chosen by the seed (`UN/gold_union_walks.py:27-40`). It writes the distinct states to `GU/walk-states-SET.jsonl` as (task, built, depth) (lines 90-92). It does not write which graph query computed each built table.

A state is a set of queries closed under inputs, and in a state each parameterized table is computed by one query (contract, "Settled calls"). The use edges and the depth of a state are those of its computing queries (schema, "Settled": depth over the state's own edges). So the sequence has to keep the computing query of each parameterized table.

Change to `UN/gold_union_walks.py`:

- `walk` keeps `made_by`, {graph table: identity of the graph query whose step added it}. An INIT query adds several heads in one step, and each takes its identity. A head that is already built keeps its first query. The random choice does not change (`rng.choice(pool)`, line 39), so the states and the counts of `GU/walks-SET.json` stay the same.
- A distinct state stays one row per (task, built set), as the schema settles. Its `made_by` is that of the first step that reached it, in the order the file is made (state-sequence type, task file order, seed, step). This is an open call (the list at the end).
- `walk-states-SET.jsonl` gains the field `made_by`.

About 15 changed lines (est.).

The counts the coordinator gave for the training sequences, from the merged training graph (`GU/graph-*-training.jsonl` of 10:57; `graph-prods-training.jsonl` sha256 begins `432f564b`): 924 of 988 tasks have state sequences; 97,571 distinct states (the line count of `GU/walk-states-training.jsonl`, sha256 begins `56db15aa`); 3,673,836 applicable queries, 1,822,694 applicable tables, 814,862 enabled queries, 432,790 enabled tables; the largest depth is 29. `GU/walks-training.json` sha256 begins `d0dcaf23`.

### The canonical text

The writer is `NEW/canon_text.py`. It makes one canonical text per graph query identity, from:

- the query's body as written: `GU/union-SET.jsonl`, `tables[].forms[].text` (`UN/gold_union.py:115`). It is one program's query after `Bar.normal`, with that program's labels;
- the reference map: the case's labels with `keys` give (union key, kind), and a reference to an INIT output gives the output after the dot (`UN/gold_union_graph.py:99-113`). The writer takes the first case line in `GU/union-keys-SET.jsonl` whose identity (`forms_of`, `UN/gold_union.py:47-60`) is the query's, and checks that the line's text equals the union text;
- the graph table names (`member_name` and `aliases`, part 2) and the parameterized table (`QueryHash`, `Name`) each joins to (`OUTD/SET/graph-keys.parquet`);
- the `instance` records of part 2, for each used parameterized table's column labels in content order.

The parser is `form_orders.parse` and `unparse` (`SAM/form_orders.py:38-53`), the tree parser that `or_q.sorted_fields` uses (`SAM/or_q.py:772`). The engine's own parser, `arclog.StudyProgram.from_sexp`, gives a token stream with paths, not a tree (`SAM/or_q.py:716`, `736`); the writer uses it through `or_q.decoder_check` for the decode check. The engine's canonical hash is not yet exposed (proposal, "Code changes in build"). `gold_union_canonical.py` has a second parser of its own (`UN/gold_union_canonical.py:23-34`); the writer does not use it.

Steps, per graph query, in the order of the schema's rules ("The canonical text"):

1. **Own label.** Dropped.
2. **References.** Each Reference becomes the parameterized table it uses: (`QueryHash`, `Name`) of the query that computes it, where the `Name` is the port's name in `engine/lib/registry.sexpr` for an INIT output, `slot <n>` for a RIGID_DET part, n the part's position in the form's canonical form (`slot <n>.<port>` for a part that reads an instance output), or `pose`, and the empty string for a RULE, DET or CHOOSE. A base table is written by its name (the contract, `ParameterizedTable` and `QueryHash`). A TableHash is never an identity, so no `table_hash` is written. The reference does not depend on the case, the session or the union key order.
3. **Derived fields.** A field of a computed parameterized table is written as the field it came from in the computing query. `with_fields` gives the origin per case: the field of the first atom that binds `*V`, followed through computed parameterized tables to a lib relation, a base table or an INIT output (`UN/gold_union_canonical.py:89-112`). The writer moves it to `NEW/canon_text.py` and resolves it per graph table: for each column (by its place in the content order of part 2), the origin over every computing query of that table. Where two columns of one parameterized table have one origin, or two computing queries give a column two origins, the column is written `:c<i>`, its place in the content order, and the manifest counts it. This is an open call.
4. **Ports in an atom.** For a computed parameterized table, in the content order of its columns. For a base table or a lib relation, in its declared order. Neither uses the written order.
5. **Variables.** Renamed by a labelling that depends only on the join structure: color refinement over labels, where a label's first color is the sorted multiset of its sites (the lib relation or `table_hash` of the atom, the field, and whether the site is under NOT, in an OR branch, in an ALL guard or in a key group), and each round adds the sorted colors of the labels that share an atom. Where classes tie when refinement ends, each order of the tied classes is tried, up to 720 orders (the `KEY_ORDERS` bound of `table_key`, `KS/superdag.py:50`), and the least text is kept; past that, the refinement order is kept and the query is flagged `canon_capped`. Names are `V0`, `V1`, ... in class order. `gold_union_canonical.canonical` numbers by first appearance in a sorted text and says that two queries with one join structure can get different numbers (`UN/gold_union_canonical.py:12`); this step replaces it.
6. **Marks.** `*` is dropped from the written text. `^` is kept in a key group, where it selects the key columns (`docs/arclog/arclog.md:61`). In an OUT, `^` is dropped. The graph queries hold no OUT: their kinds are DET, INIT, RULE and CHOOSE (grep of `GU/graph-prods-SET.jsonl`: training 4,672 DET, 12,823 INIT, 46,841 RULE, 45 CHOOSE). So the OUT rule applies only if OUT queries become targets. Both rules are the director's call (schema, "The canonical text").
7. **Order of sets.** The atoms of a body, the branches of an OR, the atoms of a branch, a NOT, an ALL's guard and conclusion, and a port's body are sets. `form_orders.Form` puts the items of each set in the order of their keys (`in_canonical_order`, `SAM/form_orders.py:109-118`), and a key depends on no order of a set (`make_key`, lines 94-102). The first order that `Form.orders()` yields (lines 285-303) is that sorted order, less the items that may not come yet: an item is a choice only when the labels it needs are bound (`choices`, lines 274-279). A NOT and a comparison need their labels; an ALL needs the labels it shares with the rest of the query (lines 11-13). So the first order puts each NOT and each ALL after the atoms that bind its labels. This is the director's rule. Sampler-worker's count on the ramp, as the coordinator gave it: 1,091 of 1,282 queries decode in the plain sorted order, and 178 of the 191 that do not have a NOT or an ALL before the atoms that bind its labels.
8. **Decode check and fallback.** The writer checks the first order with `or_q.decoder_check` (`SAM/or_q.py:707-729`) over the query's scope from `canonical_scope` (`SAM/or_q.py:811-813`). The check text is the canonical text with each query reference, field and port mapped back to the case's labels (a token map made in steps 2 to 4), with `*` on each label's first site, as `Form.tree` writes it (`SAM/form_orders.py:399-419`). Where the decoder refuses it, the writer runs the refusal search of `or_q.canonical_lines` (`SAM/or_q.py:799-806`): the next order of `Form.orders()`, and on a refusal in `RULE_REASONS`, `Form.refuse` learns the rule; up to `CANON_TRIES` 3000 orders (`SAM/or_q.py:704`). The coordinator says this search found a decodable order for every ramp query. A query with no decodable order in 3000 keeps the first order and is flagged `decode_failed`.
9. **CHOOSE.** `Form` takes no CHOOSE (`root` raises, `SAM/form_orders.py:163`) and `canonical_lines` keeps a CHOOSE's text (`SAM/or_q.py:794-796`). A CHOOSE gets steps 1 to 6 only.
10. **One text per `QueryHash`.** Equal canonical texts are one text, since they give one `QueryHash`.

`QueryHash` is the engine's canonical hash of the query's resolved content (the contract, `QueryHash`). Until the engine exposes it, the build writes in its place a hash of the canonical text of steps 1 to 10, under a version of its own, so that it compares with no engine hash.

What the writer reuses from `or_q`: `decoder_check`, `canonical_scope`, `CANON_TRIES` and the try and refuse loop. That loop is inside `canonical_lines`, which runs over a whole program's lines. It moves into `canonical_one(scope, text, kind, sess) -> (text, tries)`, and `canonical_lines` calls it. What it reuses from `form_orders`: `parse`, `unparse`, `Form`, `orders`, `refuse`, `text`. From `gold_union_canonical.py`: `with_fields`.

The writer keeps one engine session per task (`Bar(task).session()`, `gold_cheapest_common.py:62-63`) and caches the check by (task, canonical text).

Output: `OUTD/SET/texts.parquet`, one row per (task, graph query identity): `QueryHash`, kind, heads (graph table names), heads' `table_hash`, canonical text, `tries`, `fallback`, `decode_failed`, `canon_capped`, origin conflicts.

Size of the job: distinct canonical texts per task are 525 on the ramp, 1,533 on the 37 and 26,682 on training, under `gold_union_canonical.py`'s rules (`GU/canonical-SET.json`, field `task_canonical`). This spec's rules differ in steps 2, 3 and 5, so the counts will differ; they serve as the scale.

### The sample writer

`NEW/sample_write.py` reads `walk-states-SET.jsonl` (with `made_by`), `graph-prods-SET.jsonl`, `graph-keys.parquet` and `texts.parquet`, and writes the samples of part 4. Per state:

- the state's parameterized tables: the base tables, then each built graph table with its `table_hash`, its `made_by`, and its use edges: the graph tables in the `reads` field of its `made_by` query, and the base tables that query's body uses (an open call);
- `depth`: 0 for a parameterized table whose query uses no built parameterized table, else 1 + the greatest depth of the built parameterized tables it uses. The base tables have no depth;
- the targets: every graph query whose `reads` are all built (applicable), grouped by its heads; per group, the heads' `table_hash`, whether every head is built already (applicable but not enabled), and the row ids of its texts.

### Code

| File | Change | Lines |
|---|---|---|
| `UN/gold_union_walks.py` | `made_by` | 15 changed (est.) |
| `UN/gold_union_graph.py` | `graph()` also returns, per identity, the case and label map it took (lines 99-113) | 10 changed (est.) |
| `SAM/or_q.py` | `canonical_one` out of `canonical_lines` | 15 changed (est.) |
| `NEW/canon_text.py` | steps 1 to 10 | 260 (est.) |
| `NEW/sample_write.py` | states, edges, depth, targets, shards | 180 (est.) |

## Part 4. The sample file format

All files are Parquet with zstd compression. The Mac venv has pyarrow 26.0.0 (`POD`, "Environment"). One folder per set: `OUTD/ramp/`, `OUTD/37/`, `OUTD/training/`.

### Files per set

| File | One row per | Fields |
|---|---|---|
| `tables.parquet` | (task, `table_hash`) | task, `table_hash`, `base` (input, ex_input, ex_output, or null), `counts_only` (old layout; 0 for every table under the new export), `vec` (fixed-size list of float32 in the order of `NAMES`, NaN where empty), `out_gain` |
| `graph-keys.parquet` | (task, graph table) | task, graph table name, query identity, `QueryHash`, `name`, `kit_unreachable` |
| `links.parquet` | (task, graph query identity) | task, identity, `link` (fixed-size list of float32) |
| `texts.parquet` | (task, graph query identity) | as part 3 |
| `samples-<k>-of-<N>.parquet` | sample | below |
| `manifest.json` | the set | part 7 |

`vec` comes from the feature build until the switch, and from the export under the new export. `link` comes from the feature build.

### A sample row

| Field | Type | Content |
|---|---|---|
| `task` | string | the task id |
| `eval_only` | bool | true exactly where `split(task)` is `held` (part 5) |
| `sample` | string | hex of H(task, the sorted built graph table names): a row id that does not depend on file order |
| `frontier_depth` | int8 | the least depth among the state's enabled queries, as `walk-states-SET.jsonl` gives it (`UN/gold_union_walks.py:8`). It is gold's depth, so it serves only to split counts, never as an input |
| `tables` | list of struct | the base tables first (3 items), then the built tables, one item per (parameterized table, `Assignment`), at most 256 per parameterized table, sorted by (`depth`, `table_hash`). Per item: `table_hash`, `assignment` (the `Assignment`, null for a base table), `graph` (graph table name, null for a base table), `made_by` (identity, null for a base table), `uses` (list of int16: places in this list of the tables its `made_by` query uses), `depth` (int8, null for a base table) |
| `targets` | list of struct | one per distinct set of heads among the applicable queries. Per item: `heads` (list of graph table names), `head_table_hashes`, `built` (bool: every head is in the state, so the queries are applicable and not enabled), `texts` (list of int32: row numbers in `texts.parquet` of the distinct canonical texts of the group) |

The computed table of a target is `head_table_hashes`; its vector is a lookup in `tables.parquet`. Queries whose heads are equal are one target. An INIT query can have several heads, so `heads` is a list.

Fields that no input may use, kept as row ids only: `graph` (a union key on 651 training tables), `made_by` and the identity (a hash of text), `sample`.

The loader `NEW/samples_io.py` reads a shard and joins `tables.parquet` and `links.parquet`. It computes the state fields of the schema from `uses`: `n_parents`, `n_readers`, `ancestors`, `link_*` (by `made_by`), and `kid_n`, `kid_best`, `kid_best_adds` from the `out_gain` of the built parameterized tables that use the parameterized table (`POL/outfeat.py:156-170`). About 120 lines (est.).

### Sharding

The samples of one task go to one shard: shard = `crc32(task) % N`, the rule `reach2.py` uses (`reach2.py:162`). N is 16 on training and 1 on the ramp and the 37. Each task is first written to `OUTD/SET/parts/<task>.parquet`, and a merge step writes the shards (part 6).

### Sizes

Counts: samples, applicable queries and applicable tables from the schema ("Samples", ramp 1,561 / 42,726 / 18,962; the 37 6,434 / 288,888 / 176,756) and from the coordinator for training (97,571 / 3,673,836 / 1,822,694). Mean built tables per state, est. from the bytes per line of `GU/walk-states-SET.jsonl` (ramp 392,230 / 1,561 = 251; the 37 3,803,310 / 6,434 = 591; training 37,762,532 / 97,571 = 387) less about 45 bytes of other fields, at about 26 bytes a name: ramp about 8, the 37 about 21, training about 13.

Bytes per item before compression, est.: a state table item 20 (`table_hash` and `made_by` as dictionary ids, `uses`, `depth`); a target 13; a text id 4; a vector row 656 (164 float32); a link row 44 (11 float32); a canonical text 250 (mean 38 to 45 tokens, `GU/canonical-SET.json` field `tokens`, with each reference about 37 characters).

| Set | Samples: states | Samples: targets and text ids | `tables.parquet` | `texts.parquet` | `links.parquet` | All, before compression |
|---|---|---|---|---|---|---|
| ramp | 1,561 × 11 × 20 = 0.3 MB | 18,962 × 13 + 42,726 × 4 = 0.4 MB | (445 + 66) × 656 = 0.3 MB | 1,282 × 250 = 0.3 MB | 0.06 MB | about 1.4 MB |
| the 37 | 6,434 × 24 × 20 = 3.1 MB | 176,756 × 13 + 288,888 × 4 = 3.5 MB | (1,343 + 108) × 656 = 1.0 MB | 3,270 × 250 = 0.8 MB | 0.14 MB | about 8.5 MB |
| training | 97,571 × 16 × 20 = 31 MB | 1,822,694 × 13 + 3,673,836 × 4 = 38 MB | (23,817 + 2,964) × 656 = 18 MB | 64,381 × 250 = 16 MB | 2.8 MB | about 105 MB |

Vectors are per (parameterized table, `Assignment`), so their count is the sum over parameterized tables of each one's count of assignments. That count is not measured yet, so the `tables.parquet` column is a lower bound at one assignment per parameterized table: graph tables plus 3 base tables per task. The engine keeps at most 256 assignments per parameterized table, so the upper bound is 256 times the graph tables, plus the base tables: on training (23,817 × 256 + 2,964) × 656 bytes = about 4.0 GB (est.). The state table items of the samples scale by the same count of assignments per parameterized table, up to 256 times. Equal `table_hash` values merge, which lowers both. Zstd on dictionary-encoded ids typically gives 2 to 4 times less (est.), so training is about 25 to 55 MB on disk, 2 to 4 MB per shard.

The side files of part 2 hold every table instance. Est.: training about 32,641 programs (`POD` line 200) × about 15 tables each × 150 bytes = 75 MB of `instance` records, before zstd. The row store (the `rows` records) now holds the full rows of every table at every assignment, with no count cap, so it is larger than a row store under the cap of 2000 rows. Its size is not measured. The feature files hold each table's paint cell sets: about 27,000 tables × 2 KB = 54 MB, before zstd (est.).

## Part 5. The split by task

The rule that gives each task its split, `train`, `dev` or `held`, is in [the split design](split.md), Part 2. `NEW/split.py` holds it as `split(task) -> SplitName`.

- The data stages (the export, the feature build, the canonical text, the state sequences and the sample writer) process every task, whatever its split. The sample writer sets `eval_only` on each sample of a held task (part 4). No data stage guards.
- Only fit code guards. `samples_io.load(SET, role='fit')` returns no sample with `eval_only` set, and runs `split(task)` on every task it loads. A task that is `held` and has a sample without `eval_only` is an error, not a warning: it prints each bad id and exits with status 2.
- The build computes no statistic over tasks (no normalization, no vocabulary). Where the loader computes one, it takes it from fit rows only.
- Vectors, texts and samples are keyed by task, and no output pools rows of two tasks.

The test outputs are a second line of the split. `TaskCtx` drops them before feature code (`RL/features_node_feats.py:100-107`). The engine session reads the whole task file (`arclog.Task.from_json`, `gold_cheapest_common.py:62-63`), so the check before the run (part 2) also replays the 3 check tasks from a task file whose test outputs are replaced by other grids, and fails where any `table_hash` or vector changes.

About 30 lines for `NEW/split.py`, 5 in `sample_write.py` and 10 in `samples_io.py` (est.: the rule is a hash and a test on the task's source, and each guard is a call and a loop over task ids).

## Part 6. Where each part runs, with time and cost

### Measured rates

- The map mode replay, one process a task (`KUR/maps-SET.jsonl`; `seconds` is the replay, `wall` the whole worker process; sums over tasks by grep):

  | Set | Tasks | Replay, summed | Wall, summed | Longest task, wall |
  |---|---|---|---|---|
  | ramp | 22 | 51.7 s | 112.3 s | 28.0 s |
  | the 37 | 29 | 277.1 s | 341.5 s | 43.6 s |
  | training | 924 | 3,924.3 s | 5,397 s | 623.3 s |

- Set T's features: 259 tables a second in one process (`RL/rows-s120.log:39`, which prints "nodes/s 259").
- The union run on training (`GU/run-training-*.log`, file birth and change times): 17 shard logs from 07:54 to 09:41, at most 8 at once. The union key run (`GU/keys-training-0..3.log`): 4 shards from 09:33 to 09:39, and a second pass of 11 tasks at 09:41. Neither log prints a rate or a time per task; they give the scale of the union steps that come before this build, which this build does not repeat.
- The pod record names the machine: Linux x86_64 CPU pod, 16 vCPU, 128 GB (`POD` line 4). It states no price. It estimates a pod vCPU at 1.3 to 2 times slower than a Mac core (`POD` line 200; that line marks it as probable).

### Stages

| Stage | Where | Time, ramp / 37 / training | Basis |
|---|---|---|---|
| check before the run (3 tasks, 2 fresh replays each, and one with test outputs replaced) | Mac | about 2 min (est.) | ramp tasks take at most 28 s of wall each |
| export (map mode with `TableSink`, writes the row store), 4 processes | Mac | about 1 / 2 / 30 min (est.) | the wall sums above, plus 7% for the 64 training tasks that have no map today (988 against 924), plus the TableHash (est. 30% of the replay seconds, as it repeats `table_key`'s work) and the write of the row store (not measured; full rows under the new export): training about 7,000 s of CPU over 4 processes, before the row store write. The longest task alone is 623 s |
| join to graph names | Mac | seconds (est.) | joins of files of at most 75 MB |
| feature build (vectors and links), 4 processes | Mac | about seconds / seconds / 1 min (est.) | about 27,000 tables at 259 a second, twice for `outfeat`: 208 CPU-s on training, over 4 processes. The read of the row store is not measured |
| canonical text, 4 processes | Mac | about 1 / 3 / 25 min (est.) | 26,682 distinct texts on training at about 0.12 s a decode check (3,924 s over 32,641 programs, `POD` line 200, as the cost of one program's replay), about 53 CPU-min; about 15% of queries need the refusal search (191 of 1,282 on the ramp), at an est. 50 tries of 0.01 s each (a try steps only the query on a forked decoder, `SAM/or_q.py:718-727`), about 33 CPU-min |
| state sequences with `made_by` | Mac, 1 process | under 10 min on training (est.) | the same choices as the run that wrote `GU/walk-states-training.jsonl`; about 97,571 states × about 70 graph queries a task (64,381 / 924) |
| sample writer and shard merge | Mac, 1 process | under 10 min on training (est.) | the same applicable-query scan as `gold_union_walks.py:64`, and Parquet writes of at least about 105 MB |

In all: about 10 min for the ramp and the 37 together, and about 1.5 h of Mac wall time for training (est., the sum of the stages).

Under the new export, the export computes the vectors, the TableHash and plain row counts from the full rows of every table at every assignment, writes no rows to the model and the state search, and the sample build takes the vectors from the export. The feature build is then a stage of feature development only. The time of the new export is not measured.

### Mac or pod

Everything runs on the Mac. The map mode ran this way today: `KUR/maps-training.jsonl` (10:26) came from `KUR/build_training.sh`, which runs `build_map.py` under `scripts/run_heavy.py --cpus 4 --need soon`. Each worker has an RSS limit of 8,000 MiB (`KUR/build_map.py:30`); the map files do not record the peak. `POD` says the Mac has about 11 GiB free (line 8), so 4 workers stay under `run_heavy.py`'s control.

#### Prices

From "Runpod list-cpu-types and list-gpu-types, 2026-11-02", secure cloud, pods, per hour.

- A CPU pod is priced per vCPU-hour, with at most 32 vCPU a pod: cpu3c $0.03 (compute-optimized, 2 GB RAM a vCPU), cpu3g $0.04 (general purpose, 4 GB a vCPU), cpu3m $0.055 (memory-optimized, 8 GB a vCPU), cpu5c $0.035, cpu5g $0.046, cpu5m $0.065.
    - cpu3m, 16 vCPU, 128 GB: 16 × $0.055 = $0.88 an hour.
    - cpu3g, 32 vCPU, 128 GB: 32 × $0.04 = $1.28 an hour.
    - cpu3m, 32 vCPU, 256 GB: 32 × $0.055 = $1.76 an hour.
- GPU pods: RTX A5000 24 GB $0.27; A40 48 GB $0.59; L4 24 GB $0.59; RTX 4090 24 GB $0.89; L40S 48 GB $1.09; A100 80 GB $1.79; H100 PCIe $2.89; H100 SXM $3.99.

Stock in the EU data centers, from a catalog read at about 10:00 EST on 2026-11-02. Stock changes, so read it again before a pod is made.

- cpu3g 32 vCPU, 128 GB, $1.28 an hour: stock high.
- cpu3m 16 vCPU, 128 GB, $0.88 an hour: stock high.
- RTX 4090, secure cloud, $0.89 an hour: stock low, in EU-RO-1 only.
- H100: none in stock. H100 SXM is $3.99 an hour when it is in stock.
- RTX PRO 6000 96 GB, $2.49 an hour, and MI300X 192 GB, $2.39 an hour: in stock, both low.
- RTX A5000, A40, L4, L40S and A100: that read gives no stock for them.

#### Pod time and cost per stage

Bases of the table:

- A pod vCPU is about 1.3 to 2 times slower than a Mac core (`POD` line 200, which marks it as probable).
- Work that is parallel over tasks takes at least its longest task, on any count of processes. On training, the map mode's longest task is 623 s of wall (Measured rates). With the TableHash added, it is about 623 s × 1.3 = 810 s (est.: the 30% that the TableHash adds to the replay, applied to the wall). The feature build of that task adds about 2 s for each 259 tables of the task, at 259 a second, twice.
- **Start** is the pod's start, the environment of `POD` "Environment", the upload of the inputs and the download of the outputs: 15 to 30 min (est.). No record measures it. The inputs are under 1 GB (the largest, `GU/union-keys-training.jsonl`, is 170 MB), and the outputs are under 0.3 GB (part 4, "Sizes").
- When any stage runs on a pod, the check before the run runs on the pod too (part 2, "The TableHash across sessions and machines"). It is in the start time.
- Times are for training. Cost = hours × the hourly price.

| Stage | Parallel over tasks | Does a GPU help | Mac time | Pod: shape, processes, time | Pod cost | Verdict |
|---|---|---|---|---|---|---|
| check before the run | yes, but it has 3 tasks | no: engine replays and Python | about 2 min (est.) | on the pod only with another stage, in its start | in the start | Mac |
| export | yes, one process a task, the longest first | no: engine replays, hashing and writing rows | about 30 min, 4 processes (about 7,000 CPU-s) | cpu3m 16 vCPU 128 GB, 14 processes (14 × the 8,000 MiB RSS limit fits in 128 GB). The longest task: 810 s × 1.3 to 2 = 18 to 27 min. The sum: 7,000 s × 1.3 to 2 / 14 = 11 to 17 min, which is less, so the longest task sets the run: 18 to 27 min. With start: 33 to 57 min (est.). More vCPU do not shorten it | $0.88 × 0.55 h = $0.48 to $0.88 × 0.95 h = $0.84 | Mac |
| join to graph names | no: one join over the set | no: file joins | seconds | cpu3m 16 vCPU 128 GB, 1 process: seconds; with start 15 to 30 min (est.) | $0.88 × 0.25 h = $0.22 to $0.88 × 0.5 h = $0.44 | Mac |
| feature build | yes, one process a task | no: Python feature code over the row store | seconds on the ramp and the 37, about 1 min on training, 4 processes (208 CPU-s) | cpu3m 16 vCPU 128 GB, 14 processes: 208 s × 1.3 to 2 / 14 = 19 to 30 s, and at least the longest task, which no record measures. With start: 15 to 30 min (est.) | $0.88 × 0.25 h = $0.22 to $0.88 × 0.5 h = $0.44 | Mac |
| canonical text | yes, one engine session a task | no: decoder checks in the engine and text work in Python | about 25 min, 4 processes (about 86 CPU-min) | cpu3g 32 vCPU 128 GB, 30 processes: 86 CPU-min × 1.3 to 2 / 30 = 4 to 6 min, and at least the longest task, which no record measures. With start: 19 to 36 min (est.) | $1.28 × 0.32 h = $0.41 to $1.28 × 0.6 h = $0.77 | Mac |
| state sequences with `made_by` | yes in principle, since each task's state sequences are separate; it runs as 1 process | no: set operations in Python | under 10 min (est.) | cpu3m 16 vCPU 128 GB, 1 process: under 13 to 20 min; with start under 28 to 50 min (est.) | at most $0.88 × 0.47 h = $0.41 to $0.88 × 0.83 h = $0.73 | Mac |
| sample writer and shard merge | the per-task parts yes; the merge no | no: joins and Parquet writes | under 10 min (est.) | as the state sequences | as the state sequences | Mac |
| the whole build on one pod, one start | | | about 1.5 h (est.) | cpu3m 16 vCPU 128 GB, 14 processes: check about 3 min, export 18 to 27 min, feature build under 1 min, canonical text 86 CPU-min × 1.3 to 2 / 14 = 8 to 12 min, state sequences and sample writer under 26 to 40 min, start 15 to 30 min: under 71 to 113 min (est.) | $0.88 × 1.18 h = $1.04 to $0.88 × 1.88 h = $1.66 | Mac |

No stage of this build goes to a pod. Most of the build is CPU work in Python and in the engine: replays, hashing, feature code over rows, and decoder checks. No stage does the dense array math that a GPU speeds up; the vectors, the one part over numbers, take about 27,000 tables × 2 / 259 a second = 3.5 CPU-min. On a pod, the longest export task sets the time of that stage, and the start is about as long as the Mac's runs of the other stages, so the whole build on a pod takes about as long as on the Mac.

A pod is the fallback where a task passes the Mac's memory. That stage needs memory more than cores, so its shape is cpu3m 16 vCPU 128 GB.

#### Later stages where a pod and a GPU pay

Their size depends on the model, which is not specified yet, so they are not priced. Each has a first choice and a fallback, from the stock above.

- **Model training on the samples.** The forward and backward passes of the model are dense array math, which a GPU speeds up many times over a CPU.
    - A model that fits in 24 GB: first choice RTX 4090 ($0.89 an hour); fallback RTX PRO 6000 96 GB ($2.49 an hour).
    - A larger model: first choice H100 SXM ($3.99 an hour); fallback RTX PRO 6000 96 GB, or MI300X 192 GB ($2.39 an hour), which is an AMD GPU, so the training code must run on ROCm.
- **Evaluation of a trained model on the held tasks.** The model writes a query body at each state, on a GPU; the engine checks each body, on CPU, parallel over tasks. First choice RTX 4090; fallback RTX PRO 6000 96 GB.

### Streaming and resume

Each slow stage writes each item when it is done, prints a rate and an ETA, and skips finished items on a restart:

| Stage | Item | Written as | Skip rule | Progress line |
|---|---|---|---|---|
| export | task | `OUTD/side/SET/<task>.jsonl.zst`, a temp file then a rename | the file holds the sha256 of the task's union record (`src`, as `KUR/build_map.py:46-49` does for maps) and of the code (part 7) | per task: `SET task k/n, tables, table_hashes, s, tasks/min, ETA` (ETA = summed wall so far / k × (n − k) / JOBS). The longest tasks go first (`KUR/build_map.py:51`) |
| feature build | task | `OUTD/feat/SET/<task>.jsonl.zst`, a temp file then a rename | the file holds the sha256 of the task's side file and of the feature code and `NAMES` (part 7) | per task: `SET task k/n, vectors, s, tasks/min, ETA` |
| canonical text | task | `OUTD/SET/parts/texts/<task>.parquet`, temp then rename | the part holds the sha256 of its inputs | per task, with queries per second and ETA |
| state sequences and sample writer | task | `OUTD/SET/parts/samples/<task>.parquet`, temp then rename | the same | per task, with states per second and ETA |
| merges (`tables`, `texts`, `links`, shards) | set | `.part` then rename, as `KUR/build_map.py:62-67` | the manifest's shas | one line per file |

`gold_union_walks.py` writes its outputs in place (`UN/gold_union_walks.py:90-93`); the change of part 3 writes them to a temp file and renames.

## Part 7. What goes stale when the union run changes

### What each output is keyed by

| Output | Keyed by | Depends on union key order? |
|---|---|---|
| `rows` records (the row store) | (task, `table_hash`): content only | no |
| `tables.parquet` (vectors) | (task, `table_hash`): content only | no |
| `links.parquet` | (task, query identity). An identity is the query's text with each use replaced by the identity of the query it uses (`UN/gold_union.py:47-60`) | no |
| side `instance` records | (task, program sha, query index, output), with union key, identity, kit name and `table_hash` | they hold the union key, but the join can use the identity |
| `graph-keys.parquet` | (task, graph table name) | yes, for the graph tables named by a union key (2 on the ramp, 25 on the 37, 651 on training: graph tables without an `m` name, grep of `GU/graph-tables-SET.jsonl`) |
| `texts.parquet` | (task, identity); the text writes each Reference as (`QueryHash`, `Name`) | the heads are graph table names |
| samples | (task, built graph table names) | yes, through the names |

### Changes and their effect

| Change | Files that change | Stale | Rebuild |
|---|---|---|---|
| a new union key order | `GU/union-SET.jsonl`, `GU/union-keys-SET.jsonl` | `graph-keys`, `texts` (heads), samples | the join, the canonical text and the samples. No replay: vectors and links are keyed by content and identity |
| a merge map change | `KUR/maps-SET.jsonl`, `SW/runs/search-union-reach-ramp22-heldout37/outmap-SET.jsonl` | `graph-keys`, `texts`, samples; the side files of the tasks whose map run changed | the export runs in the map run, so a task with a new map gets a new side file (with its row store); then join, feature build, texts, samples |
| an addendum | `GU/union-SET-addendum.jsonl` (a later row for a task, `UN/gold_union.py:32-40`) | everything of that task | that task only: its union record's sha changes, so the skip rule of part 6 runs it again |
| a graph rebuild (as the merged training graph of 10:57) | `GU/graph-tables-SET.jsonl`, `graph-prods-SET.jsonl`, `graph-tasks-SET.jsonl` | `graph-keys`, `texts` (heads and the origin per graph table), the state sequences, samples | join, texts, state sequences, samples. Side files stay where the maps stay |
| new state sequences | `GU/walk-states-SET.jsonl`, `GU/walks-SET.json` | samples | samples |
| the kit's `parse_table` or `table_key`, the engine build, `ARCLOG_IDENT_SOURCE`, the export code (`NEW/side_tables.py`, `KUR/build.py`'s `WORKER_UNION`) | kit code, the arclog library, the export code | the row store, so all outputs | the whole build |
| the feature code or `NAMES` | `NEW/tread.py`, `NEW/tfacts.py`, `NEW/tablevec.py`, `POL/outfeat.py`, `POL/nodefeat.py`, `engine/arclog-features` | vectors, links; not the row store | the feature build, over the row store: no replay. Under the new export, the export runs again, since it computes the TableVectors |
| the TableHash definition | `NEW/table_hash.py` (its version, `s1`) | all | the whole build |
| the canonical text code | `NEW/canon_text.py`, `SAM/form_orders.py`, `SAM/or_q.py`, `UN/gold_union_canonical.py` | `texts`, samples (text row ids) | texts, samples |
| a task file | `data/tasks/<task>.json` (regenerated from patches by `scripts/materialize.py`) | everything of that task | that task |
| the split rule | `NEW/split.py` | `eval_only` of the samples | the sample writer; `samples_io.load` fails until then (part 5) |

### How the build finds what is stale

`NEW/manifest.py` writes `OUTD/SET/manifest.json`. The file `GU/union-37.manifest.json` already records a union file's sha256, its tasks and its addendum's sha256; this manifest does the same for every input of the build:

- each input file of the table above: path, size, sha256 (where a `.sha256` file exists beside it, as for `GU/union-SET.jsonl.sha256`, the build checks it and uses it);
- each code file of the build, by sha256, and the kit's tree digest (the method of `POD`, `sampler-kit/model/study/` row);
- the arclog library's sha256, `ARCLOG_IDENT_SOURCE`, the `s1` version, the sha256 of `NAMES`;
- per task, the sha256 of its union record, its task file and its graph rows, in each part file, and in a feature file the sha256 of the task's side file;
- per output file, its sha256 and the input shas it was made from.

Each stage, before it reads an upstream output, compares the shas that output records with the files on disk. A difference stops the stage with status 3 and a list of the changed inputs. `python3 -m samples.manifest check SET` prints every stale output and exits 1 where there is one. Hashing the inputs takes seconds: the largest is `GU/union-keys-training.jsonl` at 170 MB (`ls -l`).

About 100 lines (est.).

## Code, in all

| Part | New modules (`NEW/`) | Changed files | Lines, est. |
|---|---|---|---|
| 1 | `tread.py` (copy), `tfacts.py` (copy, trimmed), `tablevec.py`, `linkfacts.py`, `feature_build.py`, `features_py.py`; the crate `engine/arclog-features` | | 295 new, 55 changed, about 580 copied; the crate and `features_py.py` are not estimated |
| 2 | `table_hash.py`, `side_tables.py`, `graph_keys.py` | `KUR/build.py` (`WORKER_UNION`), `KUR/build_map.py`, `UN/gold_union_graph.py` | 360 new, 55 changed |
| 3 | `canon_text.py`, `sample_write.py` | `UN/gold_union_walks.py`, `UN/gold_union_graph.py`, `SAM/or_q.py` | 440 new, 40 changed |
| 4 | `samples_io.py` | | 120 new |
| 5 | `split.py` | `sample_write.py`, `samples_io.py` | 30 new, 15 changed |
| 7 | `manifest.py` | each stage | 100 new, 20 changed |
| all | | | about 1,345 new, 185 changed, 580 copied |

## Open calls for the director

Each has a default, which the spec above uses.

1. **The computing queries of a distinct state.** Settled by the agreed definition: a state is a set of `QueryHash`es, so two state sequences that reach one set of built tables through different queries reach two states.
2. **Derived fields with no single origin.** Where two columns of a parameterized table have one origin field, or two computing queries of a parameterized table give a column two origins. Default: write that column as `:c<i>`, its place in the content order, and count it.
3. **Use edges to the base tables.** Default: the state's use edges include the base tables that a computing query uses. Other: edges among built tables only, as the schema gives its `edges` field.
4. **Header-only tables** (old layout only: tables exported as counts, and the 348 `kit_unreachable` tables on training). Under the new export there are none. Default for the old layout: an `h1` key, the type facts and `counts_only` = 1, the rest NaN. Other: leave out the states that hold one.
5. **Where the features are written.** Settled: each feature is written once, in the crate `engine/arclog-features` (part 1). The export calls it, and the small Python module calls it over the row store. The row store serves feature development only; it holds full rows, so its size grows, and it is not measured.
6. **OUT queries as targets.** The graph holds none. Default: no. The `^` rule for OUT then has no effect in this build.
7. **A pod.** Default: the Mac for every stage. A pod only for a task past the Mac's memory, with the shape and cost of Part 6, "Pod time and cost per stage".
8. **A graph table whose map equals no replayed parameterized table's map, or more than one.** Default: the join stops with status 2 and lists them.

## Settled

The director approved the defaults of open calls 2 to 4, 6 and 7. Open call 5 is settled by the user's ruling that the model takes features (the export computes the `TableVector`) and by Sampler-worker's answer on the crate. The user's ruling: the new export has no count cap and no table is counts-only at any assignment, and the counts-only kind stays only in the old layout, behind its flag. The cap of 256 assignments for each parameterized table's walk is not part of the ruling and stays. Open call 1 is settled by the agreed state definition. The director accepted the default of open call 8. The rebuild of the union graph with a map {`Assignment` → `TableHash`} per parameterized table waits on the engine's export change (contract, the target-query rule). The build waits on the user's word.
